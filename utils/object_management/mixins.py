"""Common mixins for views that deal with UserCreatedObject models."""

from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import ImproperlyConfigured

from .permissions import get_object_policy


class AppendTemplateMixin:
    """Append extra_template_names onto whatever parent get_template_names() returns."""

    extra_template_names: list[str] = []

    def get_template_names(self):
        try:
            base = super().get_template_names()
        except ImproperlyConfigured:
            base = []
        return base + list(self.extra_template_names)


class _BaseUserCreatedObjectAccessMixin(UserPassesTestMixin):
    publication_status_field = "publication_status"
    owner_field = "owner"
    published_status = "published"

    def _ensure_fields(self, obj):
        missing = [
            f
            for f in (self.publication_status_field, self.owner_field)
            if not hasattr(obj, f)
        ]
        if missing:
            raise ImproperlyConfigured(
                f"{obj.__class__.__name__} must have fields: {', '.join(missing)}"
            )

    def _get_policy(self, obj=None):
        obj = obj or self.get_object()
        self._ensure_fields(obj)
        return get_object_policy(self.request.user, obj, request=self.request)

    def _can_read(self):
        policy = self._get_policy()
        return (
            policy["is_published"]
            or policy["is_archived"]
            or policy["is_owner"]
            or policy["is_staff"]
        )

    def _can_write(self):
        policy = self._get_policy()
        if policy["can_edit"]:
            return True
        # Fallback for models without update URLs in the policy
        return (
            not policy["is_archived"]
            and (policy["is_staff"] or (policy["is_owner"] and not policy["is_published"]))
        )


class UserCreatedObjectReadAccessMixin(_BaseUserCreatedObjectAccessMixin):
    """Read if published, else only owner or staff."""

    def test_func(self):
        return self._can_read()


class UserCreatedObjectWriteAccessMixin(_BaseUserCreatedObjectAccessMixin):
    """Write if staff, or owner of non-published."""

    def test_func(self):
        return self._can_write()


class UserOwnsObjectMixin(UserPassesTestMixin):
    """Only allow the owner (and no publication logic)."""

    def test_func(self):
        policy = get_object_policy(self.request.user, self.get_object(), request=self.request)
        return policy["is_owner"]


class CreateUserObjectMixin:
    """Assign the current user as the owner of a newly created object."""

    def form_valid(self, form):
        obj = form.save(commit=False)
        if hasattr(obj, "owner"):
            obj.owner = self.request.user
        obj.save()
        return super().form_valid(form)


class PublishedAutocompleteMixin:
    """
    Provides get_queryset() for autocompletes that should only show published objects.
    Assumes self.model is set and model has 'publication_status'.
    """

    def get_queryset(self):
        qs = self.model.objects.all()
        return qs.filter(
            publication_status=getattr(self.model, "STATUS_PUBLISHED", "published")
        )


class PrivateAutocompleteMixin:
    """
    Provides get_queryset() for autocompletes that should only show objects owned by the request user.
    Assumes self.model is set and model has 'owner'.
    """

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return self.model.objects.none()
        return self.model.objects.filter(owner=user)
