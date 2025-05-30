"""Common mixins for views that deal with UserCreatedObject models."""

from django.core.exceptions import ImproperlyConfigured
from django.contrib.auth.mixins import UserPassesTestMixin


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
        missing = [f for f in (self.publication_status_field, self.owner_field)
                   if not hasattr(obj, f)]
        if missing:
            raise ImproperlyConfigured(
                f"{obj.__class__.__name__} must have fields: {', '.join(missing)}"
            )

    def _can_read(self):
        obj, user = self.get_object(), self.request.user
        self._ensure_fields(obj)
        status = getattr(obj, self.publication_status_field)
        if status == self.published_status:
            return True
        return user.is_authenticated and (user.is_staff or obj.owner == user)

    def _can_write(self):
        obj, user = self.get_object(), self.request.user
        self._ensure_fields(obj)
        if not user.is_authenticated:
            return False
        if user.is_staff:
            return True
        status = getattr(obj, self.publication_status_field)
        if status == self.published_status:
            return False
        return obj.owner == user


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
        user = self.request.user
        return user.is_authenticated and self.get_object().owner == user


class CreateUserObjectMixin:
    """Assign the current user as the owner of a newly created object."""
    def form_valid(self, form):
        obj = form.save(commit=False)
        if hasattr(obj, 'owner'):
            obj.owner = self.request.user
        obj.save()
        return super().form_valid(form)
