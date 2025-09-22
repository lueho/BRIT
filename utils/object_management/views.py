import logging
from urllib.parse import unquote

from bootstrap_modal_forms.generic import (
    BSModalCreateView,
    BSModalDeleteView,
    BSModalReadView,
    BSModalUpdateView,
)
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
    UserPassesTestMixin,
)
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.loader import select_template
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, DetailView, ListView, UpdateView, View
from django_filters.views import FilterView
from django_tomselect.autocompletes import AutocompleteModelView
from extra_views import CreateWithInlinesView, UpdateWithInlinesView

from case_studies.soilcom.models import Collection
from utils.object_management.models import ReviewAction
from utils.object_management.permissions import UserCreatedObjectPermission

from ..forms import DynamicTableInlineFormSetHelper
from ..views import (
    FilterDefaultsMixin,
    ModelSelectOptionsView,
    NextOrSuccessUrlMixin,
    NoFormTagMixin,
)

logger = logging.getLogger(__name__)


class ReviewDashboardView(ListView):
    """Dashboard showing all objects in review status that the user can moderate."""

    template_name = "object_management/review_dashboard.html"
    context_object_name = "review_items"
    paginate_by = 20

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        # Start with an empty queryset
        review_items = []

        # Get all model classes that inherit from UserCreatedObject
        # For now, we'll just use Collection as an example
        model_classes = [Collection]

        for model_class in model_classes:
            # Check if user can moderate this model type
            ContentType.objects.get_for_model(model_class)
            perm_codename = f"can_moderate_{model_class._meta.model_name}"
            app_label = model_class._meta.app_label
            full_perm = f"{app_label}.{perm_codename}"

            if self.request.user.is_staff or self.request.user.has_perm(full_perm):
                # Get items in review for this model, excluding current user's own items
                try:
                    items = (
                        model_class.objects.in_review()
                        .exclude(owner=self.request.user)
                        .select_related("owner", "approved_by")
                    )
                except Exception:
                    # Fallback if owner field is absent or exclude fails
                    items = model_class.objects.in_review().select_related(
                        "owner", "approved_by"
                    )
                    # Filter out in Python as a last resort
                    items = [
                        i
                        for i in items
                        if getattr(i, "owner_id", None) != self.request.user.id
                    ]
                review_items.extend(items)

        # Sort by submitted_at date (newest first)
        review_items.sort(key=lambda x: x.submitted_at or timezone.now(), reverse=True)
        return review_items

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Content Review Dashboard"
        return context


class BaseReviewActionView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Base view for all review workflow actions.

    Provides common functionality for review actions including:
    - Permission checking
    - Object retrieval from ContentType and ID
    - Success URL determination (respecting 'next' parameter)
    """

    permission_method: str | None = None
    permission_denied_message: str = "You don't have permission to perform this action."

    def get_object(self, request=None, *args, **kwargs):
        """Get the object being reviewed based on content type and ID.

        Accepts an optional request and varargs for compatibility with callers.
        Resolves IDs from self.kwargs so subclasses (including modal views)
        don't need to override this method.
        """
        content_type_id = self.kwargs.get("content_type_id")
        object_id = self.kwargs.get("object_id")

        content_type = get_object_or_404(ContentType, pk=content_type_id)
        model_class = content_type.model_class()
        return get_object_or_404(model_class, pk=object_id)

    def get_success_url(self):
        """Override to support both 'next' parameter and fallback to object URL."""
        next_url = self.request.POST.get("next") or self.request.GET.get("next")
        if next_url:
            return next_url
        return self.object.get_absolute_url()

    def has_action_permission(self, request, obj) -> bool:
        try:
            perm = UserCreatedObjectPermission()
            checker = getattr(perm, str(self.permission_method), None)
            return bool(checker(request, obj)) if callable(checker) else False
        except Exception:
            return False

    def test_func(self):  # type: ignore[override]
        try:
            obj = self.get_object()
        except Exception:
            return False
        return self.has_action_permission(self.request, obj)

    def ensure_permission(self, request, obj):
        if not self.has_action_permission(request, obj):
            raise PermissionDenied(self.permission_denied_message)

    # ---- Generic review action helpers ----
    # Subclasses should set these and can override the hooks below
    action_attr_name: str | None = (
        None  # e.g., 'approve', 'reject', 'submit_for_review', 'withdraw_from_review'
    )
    review_action = None  # e.g., ReviewAction.ACTION_APPROVED

    def get_action_kwargs(self, request, obj) -> dict:
        """Hook to pass kwargs to the model action.

        Default: no kwargs. The approve flow receives the acting user via
        handle_review_action_post(), which injects user=request.user only when
        action_attr_name == 'approve'.
        """
        return {}

    def _get_comment(self, request) -> str:
        return (
            request.POST.get("comment") or request.POST.get("message") or ""
        ).strip()

    def get_success_message(self, obj, previous_status=None) -> str:
        """Hook to customize the success message after the action."""
        return f"{obj._meta.verbose_name} has been updated."

    def handle_review_action_post(self, request, *args, **kwargs):
        """Shared POST flow for all review actions."""
        # Resolve object for both modal and non-modal views
        try:
            self.object = self.get_object(request, *args, **kwargs)
        except TypeError:
            # Modal get_object may not accept request param
            self.object = self.get_object()

        # Centralized permission check
        self.ensure_permission(request, self.object)

        comment = self._get_comment(request)

        # Perform the model action
        try:
            previous_status = getattr(self.object, "publication_status", None)
            if not self.action_attr_name:
                raise ImproperlyConfigured("action_attr_name must be set on the view")
            action_callable = getattr(self.object, self.action_attr_name, None)
            if not callable(action_callable):
                raise ImproperlyConfigured(
                    f"Object has no callable '{self.action_attr_name}' method"
                )
            action_kwargs = dict(self.get_action_kwargs(request, self.object) or {})
            if self.action_attr_name == "approve" and "user" not in action_kwargs:
                action_kwargs["user"] = request.user
            action_callable(**action_kwargs)

            # Fallback: if approve() did not set approved_by for any reason, set it here
            if (
                self.action_attr_name == "approve"
                and getattr(self.object, "approved_by_id", None) is None
            ):
                try:
                    self.object.approved_by = request.user
                    self.object.save(update_fields=["approved_by"])
                except Exception:
                    pass

            # Log review action
            try:
                ReviewAction.objects.create(
                    content_type=ContentType.objects.get_for_model(
                        self.object.__class__
                    ),
                    object_id=self.object.pk,
                    user=request.user,
                    action=self.review_action,
                    comment=comment,
                )
            except Exception as e:
                logger.warning(
                    "Failed to create ReviewAction for %s: %s", self.action_attr_name, e
                )

            # Success message
            try:
                messages.success(
                    request, self.get_success_message(self.object, previous_status)
                )
            except Exception:
                pass
        except Exception as e:
            messages.error(request, f"Error performing action: {str(e)}")

        return HttpResponseRedirect(self.get_success_url())

    # Default POST handler for all review action views (modal and non‑modal)
    def post(self, request, *args, **kwargs):  # type: ignore[override]
        return self.handle_review_action_post(request, *args, **kwargs)


class SubmitForReviewView(BaseReviewActionView):
    """View to submit an item for review."""

    permission_method = "has_submit_permission"
    permission_denied_message = (
        "You don't have permission to submit this item for review."
    )
    action_attr_name = "submit_for_review"
    review_action = ReviewAction.ACTION_SUBMITTED


class WithdrawFromReviewView(BaseReviewActionView):
    """View to withdraw an item from review."""

    permission_method = "has_withdraw_permission"
    permission_denied_message = (
        "You don't have permission to withdraw this item from review."
    )
    action_attr_name = "withdraw_from_review"
    review_action = ReviewAction.ACTION_WITHDRAWN


class ApproveItemView(BaseReviewActionView):
    """View to approve an item that is in review."""

    permission_method = "has_approve_permission"
    permission_denied_message = "You don't have permission to approve this item."
    action_attr_name = "approve"
    review_action = ReviewAction.ACTION_APPROVED


class RejectItemView(BaseReviewActionView):
    """View to reject an item that is in review."""

    permission_method = "has_reject_permission"
    permission_denied_message = "You don't have permission to reject this item."
    action_attr_name = "reject"
    review_action = ReviewAction.ACTION_REJECTED


class BaseReviewActionModalView(BaseReviewActionView, BSModalReadView):
    """Base modal view to render confirmation dialogs for review actions.

    Uses the shared modal container (#modal) via django-bootstrap-modal-forms.
    Subclasses must set template_name and implement test_func() for permission checks.
    """

    template_name: str = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pass through 'next' if provided in the opener link; templates will append it to the form action
        context["next_url"] = self.request.GET.get("next")
        return context

    def post(self, request, *args, **kwargs):  # type: ignore[override]
        """Preflight handling for django-bootstrap-modal-forms.

        The plugin first sends an AJAX POST to validate the form. We must not
        perform the action on that request; instead, respond with 204 so the
        plugin submits the real (non-AJAX) POST, on which we execute the action
        and redirect to success_url/next.
        """
        # Detect AJAX request as used by the package (X-Requested-With)
        try:
            is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
        except Exception:
            is_ajax = False

        if is_ajax:
            # Optional: enforce permission early to fail fast in the modal
            try:
                obj = self.get_object()
                self.ensure_permission(request, obj)
            except PermissionDenied:
                # Return 403; the plugin will keep the modal open (no redirect)
                from django.http import HttpResponseForbidden

                return HttpResponseForbidden(self.permission_denied_message)
            # Valid preflight – let the plugin proceed with real submit
            from django.http import HttpResponse

            return HttpResponse(status=204)

        # Non-AJAX: perform the action and redirect
        return super().post(request, *args, **kwargs)


class SubmitForReviewModalView(BaseReviewActionModalView):
    template_name = "object_management/submit_for_review_modal.html"

    permission_method = "has_submit_permission"
    permission_denied_message = (
        "You don't have permission to submit this item for review."
    )
    action_attr_name = "submit_for_review"
    review_action = ReviewAction.ACTION_SUBMITTED


class WithdrawFromReviewModalView(BaseReviewActionModalView):
    template_name = "object_management/withdraw_from_review_modal.html"

    permission_method = "has_withdraw_permission"
    permission_denied_message = (
        "You don't have permission to withdraw this item from review."
    )
    action_attr_name = "withdraw_from_review"
    review_action = ReviewAction.ACTION_WITHDRAWN


class ApproveItemModalView(BaseReviewActionModalView):
    template_name = "object_management/approve_item_modal.html"

    permission_method = "has_approve_permission"
    permission_denied_message = "You don't have permission to approve this item."
    action_attr_name = "approve"
    review_action = ReviewAction.ACTION_APPROVED


class RejectItemModalView(BaseReviewActionModalView):
    template_name = "object_management/reject_item_modal.html"

    permission_method = "has_reject_permission"
    permission_denied_message = "You don't have permission to reject this item."
    action_attr_name = "reject"
    review_action = ReviewAction.ACTION_REJECTED


class UserOwnsObjectMixin(UserPassesTestMixin):
    """
    All models that have access restrictions specific to a user contain a field named 'owner'. This mixin prevents
    access to objects owned by other users.
    """

    def test_func(self):
        # If the user is not authenticated, fail the test
        if not self.request.user.is_authenticated:
            return False

        # Allow access only if the user owns the object
        return self.get_object().owner == self.request.user


class UserCreatedObjectListMixin:
    paginate_by = 10
    header = None
    list_type = None
    dashboard_url = None
    model = None

    def get_queryset(self):
        queryset = super().get_queryset()

        if not hasattr(queryset.model, "publication_status"):
            raise ImproperlyConfigured(
                f"The model {queryset.model.__name__} must have a 'publication_status' field."
            )

        query_params = {}
        if self.list_type == "public":
            query_params["publication_status"] = "published"
        elif self.list_type == "private":
            query_params["owner"] = self.request.user

        queryset = queryset.filter(**query_params)

        # If an OrderingFilter already set an explicit order, do not override it
        try:
            has_explicit_order = bool(queryset.query.order_by)
        except Exception:
            has_explicit_order = False

        if not has_explicit_order:
            if hasattr(queryset.model, "name"):
                return queryset.order_by("name")
            return queryset.order_by("id")

        return queryset

    def get_header(self):
        if self.header:
            return self.header
        else:
            return None

    def get_dashboard_url(self):
        return self.dashboard_url

    def get_create_url(self):
        return self.model.create_url

    def get_create_url_text(self):
        if self.model:
            return f"New {self.model._meta.verbose_name}"
        return None

    def get_create_permission(self):
        if self.model:
            return f"{self.model.__module__.split('.')[-2]}.add_{self.model.__name__.lower()}"
        return None

    def get_list_type(self):
        return self.list_type

    def get_private_list_owner(self):
        if self.list_type == "private":
            return self.request.user
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Base context
        context.update(
            {
                "header": self.get_header(),
                "create_url": self.get_create_url(),
                "create_url_text": self.get_create_url_text(),
                "create_permission": self.get_create_permission(),
                "list_type": self.get_list_type(),
                "private_list_owner": self.get_private_list_owner(),
                "dashboard_url": self.get_dashboard_url(),
            }
        )

        # Scope switcher context (urls, counts, active scope)
        try:
            queryset = self.get_queryset()
            model = queryset.model
        except Exception:
            model = getattr(self, "model", None)

        # Determine URLs from model helpers if available
        public_url = getattr(model, "public_list_url", None)
        private_url = getattr(model, "private_list_url", None)
        review_url = getattr(model, "review_list_url", None)
        if callable(public_url):
            public_url = public_url()
        if callable(private_url):
            private_url = private_url()
        if callable(review_url):
            review_url = review_url()

        # Map URLs (if provided by model as classmethods)
        public_map_url = None
        private_map_url = None
        review_map_url = None
        try:
            getter = getattr(model, "public_map_url", None)
            if callable(getter):
                public_map_url = getter()
        except Exception:
            public_map_url = None
        try:
            getter = getattr(model, "private_map_url", None)
            if callable(getter):
                private_map_url = getter()
        except Exception:
            private_map_url = None
        try:
            getter = getattr(model, "review_map_url", None)
            if callable(getter):
                review_map_url = getter()
        except Exception:
            review_map_url = None

        # Try conventional URL names: <model>-list, <model>-list-owned, <model>-list-review
        try:
            model_name = model._meta.model_name if model is not None else None
            if model_name:
                if not public_url:
                    try:
                        public_url = reverse(f"{model_name}-list")
                    except Exception:
                        pass
                if not private_url:
                    try:
                        private_url = reverse(f"{model_name}-list-owned")
                    except Exception:
                        pass
                if not review_url:
                    try:
                        review_url = reverse(f"{model_name}-list-review")
                    except Exception:
                        pass
        except Exception:
            pass

        # Fallbacks: build URLs from current path and query params with scope override
        try:
            req = self.request
            base_path = req.path

            def build_fallback_url(scope_value: str) -> str:
                params = req.GET.copy()
                # Reset pagination when switching scope
                if "page" in params:
                    del params["page"]
                params["scope"] = scope_value
                encoded = params.urlencode()
                return f"{base_path}?{encoded}" if encoded else base_path

            if not public_url:
                public_url = build_fallback_url("published")
            if not private_url:
                private_url = build_fallback_url("private")
            if not review_url:
                review_url = build_fallback_url("review")
        except Exception:
            # If anything goes wrong, keep URLs as-is (may be None)
            pass

        # Compute counts conservatively; fall back to 0 on errors
        public_count = 0
        private_count = 0
        review_count = 0
        try:
            if model is not None and hasattr(model, "objects"):
                # Public count
                try:
                    public_count = model.objects.filter(
                        publication_status="published"
                    ).count()
                except Exception:
                    public_count = 0

                # Private count (owned by current user)
                user = self.request.user
                try:
                    if user and user.is_authenticated and hasattr(model, "owner"):
                        private_count = model.objects.filter(owner=user).count()
                except Exception:
                    private_count = 0

                # Review count (items the user can moderate)
                try:
                    # Prefer a custom manager/queryset method if it exists
                    if hasattr(model.objects, "in_review"):
                        review_qs = model.objects.in_review()
                    else:
                        review_qs = model.objects.filter(publication_status="review")

                    # Exclude the current user's own objects from review count
                    user = self.request.user
                    if user and user.is_authenticated:
                        try:
                            review_qs = review_qs.exclude(owner=user)
                        except Exception:
                            pass

                    # Only count if the user is a moderator for this model
                    can_moderate = False
                    if self.request.user and self.request.user.is_authenticated:
                        perm_codename = f"can_moderate_{model._meta.model_name}"
                        app_label = model._meta.app_label
                        can_moderate = (
                            self.request.user.is_staff
                            or self.request.user.has_perm(
                                f"{app_label}.{perm_codename}"
                            )
                        )
                    review_count = review_qs.count() if can_moderate else 0
                except Exception:
                    review_count = 0
        except Exception:
            pass

        # Active scope from list_type (public/private/review)
        active_scope = self.get_list_type()

        context.update(
            {
                "active_scope": active_scope,
                "public_url": public_url,
                "private_url": private_url,
                "review_url": review_url,
                "public_count": public_count,
                "private_count": private_count,
                "review_count": review_count,
                # Map URLs for header view toggle (may be None if model has no map views)
                "public_map_url": public_map_url,
                "private_map_url": private_map_url,
                "review_map_url": review_map_url,
            }
        )
        return context


class PublishedObjectListMixin(UserCreatedObjectListMixin):
    list_type = "public"


class PrivateObjectListMixin(LoginRequiredMixin, UserCreatedObjectListMixin):
    list_type = "private"


class PublishedObjectFilterView(
    PublishedObjectListMixin, FilterDefaultsMixin, FilterView
):
    """
    A view to display a list of published objects with default filters applied.
    """

    def get_template_names(self):
        template_names = super().get_template_names()
        template_names.append("filtered_list.html")
        return template_names


class AddReviewCommentView(BaseReviewActionView):
    """Add a free-text review comment linked to an object."""

    def post(self, request, *args, **kwargs):
        self.object = self.get_object(request, *args, **kwargs)
        obj = self.object

        # Must be authenticated
        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required.")

        # Authorization: owners can always comment on their own objects; moderators too
        is_owner = obj.owner_id == request.user.id
        can_moderate = UserCreatedObjectPermission().is_moderator(request.user, obj)
        if not (is_owner or can_moderate or request.user.is_staff):
            raise PermissionDenied("You don't have permission to comment on this item.")

        message = (request.POST.get("message") or "").strip()
        if not message:
            messages.error(request, "Comment cannot be empty.")
            return HttpResponseRedirect(self.get_success_url())

        ReviewAction.objects.create(
            content_type=ContentType.objects.get_for_model(obj.__class__),
            object_id=obj.pk,
            action=ReviewAction.ACTION_COMMENT,
            comment=message,
            user=request.user,
        )

        messages.success(request, "Comment added.")
        return HttpResponseRedirect(self.get_success_url())


class ReviewObjectListMixin(
    LoginRequiredMixin, UserPassesTestMixin, UserCreatedObjectListMixin
):
    """List mixin to show objects under review to moderators/staff.

    - Restricts access to users who are staff or hold the per‑model
      `can_moderate_<modelname>` permission.
    - Sets `list_type` to 'review' for templates.
    - Filters queryset to only items reviewable by the user.
    """

    list_type = "review"

    def test_func(self):
        model = getattr(self, "model", None)
        if model is None:
            raise ImproperlyConfigured("ReviewObjectListMixin requires a 'model'.")
        user = self.request.user
        if not user.is_authenticated:
            return False
        app_label = model._meta.app_label
        model_name = model._meta.model_name
        perm_codename = f"can_moderate_{model_name}"
        return user.is_staff or user.has_perm(f"{app_label}.{perm_codename}")

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.reviewable_by_user(self.request.user)


class ReviewObjectFilterView(ReviewObjectListMixin, FilterDefaultsMixin, FilterView):
    """Filter view for review scope; applies default scope='review' and uses filtered_list template."""

    def get_default_filters(self):
        initial_values = super().get_default_filters()
        if "scope" in self.filterset_class.base_filters:
            initial_values["scope"] = "review"
        return initial_values

    def get_template_names(self):
        template_names = super().get_template_names()
        template_names.append("filtered_list.html")
        return template_names


class PrivateObjectFilterView(PrivateObjectListMixin, FilterDefaultsMixin, FilterView):
    """
    A view to display a list of objects owned by the currently logged-in user with default filters applied.
    """

    def get_default_filters(self):
        """Override to set scope to 'private' for private object views."""
        initial_values = super().get_default_filters()
        # Override scope to 'private' for private views
        if "scope" in self.filterset_class.base_filters:
            initial_values["scope"] = "private"
        return initial_values

    def get_template_names(self):
        template_names = super().get_template_names()
        template_names.append("filtered_list.html")
        return template_names


class PublishedObjectListView(PublishedObjectListMixin, ListView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "header": self.model._meta.verbose_name_plural.capitalize(),
                "create_url": self.model.create_url,
                "create_url_text": f"New {self.model._meta.verbose_name}",
                "create_permission": f"{self.model.__module__.split('.')[-2]}.add_{self.model.__name__.lower()}",
            }
        )
        return context

    def get_template_names(self):
        try:
            template_names = super().get_template_names()
        except ImproperlyConfigured:
            template_names = []
        template_names.append("simple_list_card.html")
        return template_names


class PrivateObjectListView(PrivateObjectListMixin, ListView):
    """
    A view to display a list of objects owned by the currently logged-in user.
    """

    def get_template_names(self):
        template_names = super().get_template_names()
        template_names.append("simple_list_card.html")
        return template_names


class UserCreatedObjectReadAccessMixin(UserPassesTestMixin):
    """
    A Mixin to control access to objects based on 'publication_status' and 'owner'.

    - Published objects ('publication_status' == 'published') are accessible to all users.
    - Unpublished objects are accessible to their owners, staff, or moderators
      (users with the per‑model permission `can_moderate_<model>`).
    """

    publication_status_field = "publication_status"
    owner_field = "owner"
    published_status = "published"
    permission_denied_message = "You do not have permission to access this object."

    def test_func(self):
        obj = self.get_object()

        # Ensure the object has the required fields
        if not hasattr(obj, self.publication_status_field) or not hasattr(
            obj, self.owner_field
        ):
            raise ImproperlyConfigured(
                f"The model {obj.__class__.__name__} must have '{self.publication_status_field}' and '{self.owner_field}' fields."
            )

        publication_status = getattr(obj, self.publication_status_field)
        owner = getattr(obj, self.owner_field)
        user = self.request.user

        # Published or Archived: accessible to all
        if (
            publication_status == self.published_status
            or getattr(obj, "is_archived", False)
            or publication_status == "archived"
        ):
            return True
        else:
            if user.is_authenticated:
                # Private/Review/Declined: accessible to owner, staff, or moderators
                try:
                    perm = UserCreatedObjectPermission()
                    is_moderator = perm.is_moderator(user, obj)
                except Exception:
                    is_moderator = False
                return owner == user or user.is_staff or is_moderator
            else:
                # Private: not accessible for unauthenticated users
                return False


class UserCreatedObjectWriteAccessMixin(UserPassesTestMixin):
    """
    A Mixin to control write access to objects based on 'publication_status' and 'owner'.

    - Published objects ('publication_status' == 'published') are accessible to all users.
    - Unpublished objects are only accessible to their owners.
    """

    publication_status_field = "publication_status"
    owner_field = "owner"
    published_status = "published"
    permission_denied_message = "You do not have permission to access this object."

    def test_func(self):
        user = self.request.user

        # Authentication is required for all write operations
        if not user.is_authenticated:
            return False

        obj = self.get_object()

        # Ensure the object has the required fields
        if not hasattr(obj, self.publication_status_field) or not hasattr(
            obj, self.owner_field
        ):
            raise ImproperlyConfigured(
                f"The model {obj.__class__.__name__} must have '{self.publication_status_field}' and '{self.owner_field}' fields."
            )

        publication_status = getattr(obj, self.publication_status_field)
        owner = getattr(obj, self.owner_field)

        # staff can change any object
        if user.is_staff:
            return True

        # published objects can only be changed by staff
        if publication_status == self.published_status:
            return False

        # owners can change their own objects if they are not published
        if publication_status in ("private", "review", "declined"):
            return owner == user


class CreateUserObjectMixin(PermissionRequiredMixin, NextOrSuccessUrlMixin):
    def has_permission(self):
        # Staff users can always create objects
        if self.request.user.is_staff:
            return True
        # For non-staff users, use the default permission check
        return super().has_permission()

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class UserCreatedObjectCreateView(
    CreateUserObjectMixin, NoFormTagMixin, SuccessMessageMixin, CreateView
):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        model_name = "Object"

        if hasattr(self, "model") and self.model:
            model = self.model
            if hasattr(model._meta, "verbose_name"):
                model_name = model._meta.verbose_name.capitalize()
        elif hasattr(self, "form_class") and self.form_class:
            form_meta = getattr(self.form_class, "_meta", None)
            if form_meta and hasattr(form_meta, "model"):
                model = form_meta.model
                if hasattr(model._meta, "verbose_name"):
                    model_name = model._meta.verbose_name.capitalize()

        context.update(
            {"form_title": f"Create New {model_name}", "submit_button_text": "Save"}
        )
        return context

    def get_success_message(self, cleaned_data):
        if hasattr(self, "object") and self.object:
            model_name = self.object._meta.verbose_name.capitalize()
            return f"{model_name} created successfully."
        return "Object created successfully."

    def get_template_names(self):
        try:
            template_names = super().get_template_names()
        except ImproperlyConfigured:
            template_names = []
        template_names.append("simple_form_card.html")
        return template_names


class UserCreatedObjectModalCreateView(PermissionRequiredMixin, BSModalCreateView):
    template_name = "modal_form.html"
    object = None

    def has_permission(self):
        # Staff users can always create objects
        if self.request.user.is_staff:
            return True
        # For non-staff users, use the default permission check
        return super().has_permission()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        model_name = "Object"
        model = None

        if hasattr(self, "model") and self.model:
            model = self.model

        elif hasattr(self, "form_class") and self.form_class:
            form_meta = getattr(self.form_class, "_meta", None)
            if form_meta and hasattr(form_meta, "model"):
                model = form_meta.model

        if model and hasattr(model._meta, "verbose_name"):
            model_name = model._meta.verbose_name.capitalize()

        context.update(
            {"modal_title": f"Create New {model_name}", "submit_button_text": "Save"}
        )
        return context

    def get_success_message(self):
        if hasattr(self, "object") and self.object:
            model_name = self.object._meta.verbose_name.capitalize()
            return f"{model_name} created successfully."
        return "Object created successfully."

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class UserCreatedObjectDetailView(UserCreatedObjectReadAccessMixin, DetailView):
    """
    A view to display the details of a user created object only if it is either published or owned by the currently
    logged-in user. Views that inherit from this view must use models that inherit from UserCreatedObject.
    """

    def get_template_names(self):
        try:
            template_names = super().get_template_names()
        except ImproperlyConfigured:
            template_names = []
        template_names.append("simple_detail_card.html")
        return template_names

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.object
        request = self.request
        # Show review panel when explicitly requested via ?review=1
        show_panel = request.GET.get("review") is not None

        logs = []
        if show_panel:
            try:
                logs = list(ReviewAction.for_object(obj).select_related("user"))
            except Exception:
                logs = []

        context.update(
            {
                "show_review_panel": show_panel,
                "review_logs": logs,
            }
        )
        return context


class ReviewItemDetailView(UserCreatedObjectDetailView):
    """
    Render the regular DetailView of an object, but inject a review action bar
    (available actions + optional reviewer comment field) at the top of the page.

    Implementation strategy:
    - Use a wrapper template that extends the object's normal detail template.
    - Determine the base detail template via Django's default naming convention
      (<app_label>/<model_name>_detail.html) and fall back to simple_detail_card.html.
     - Provide the resolved base template to the wrapper via context as 'base_template'.
    """

    template_name = "object_management/review_detail_wrapper.html"

    def test_func(self):
        """Allow access for staff and moderators; owners when in review or declined.

        This overrides the default read-access mixin so that non-staff moderators who
        hold the dynamic per-model permission (can_moderate_<model>) may access the
        review detail view. Owners are permitted to access the review view while their
        item is in review (to read and add comments) and when declined (to read feedback).
        """
        user = getattr(self, "request", None) and self.request.user
        if not user or not getattr(user, "is_authenticated", False):
            return False

        obj = self.get_object()
        # Owners: allowed when object is in review (to comment) or declined (to read feedback)
        if getattr(obj, "owner_id", None) == getattr(user, "id", None):
            return bool(
                getattr(obj, "is_in_review", False)
                or getattr(obj, "is_declined", False)
            )

        # Moderators/staff: allowed
        app_label = obj._meta.app_label
        perm_codename = f"can_moderate_{obj._meta.model_name}"
        return bool(
            getattr(user, "is_staff", False)
            or user.has_perm(f"{app_label}.{perm_codename}")
        )

    def dispatch(self, request, *args, **kwargs):
        """Authorize review details for moderators/staff and for owners in review/declined.

        Owners can access while the item is in review (for commenting) and when declined (to read feedback).
        """
        obj = self.get_object()
        model = obj.__class__
        app_label = model._meta.app_label
        perm_codename = f"can_moderate_{model._meta.model_name}"

        # If the current user is the owner
        if (
            request.user.is_authenticated
            and hasattr(obj, "owner")
            and obj.owner_id == request.user.id
        ):
            # Allow owners for objects in review (to comment) and declined (to read feedback)
            if bool(
                getattr(obj, "is_in_review", False)
                or getattr(obj, "is_declined", False)
            ):
                return super().dispatch(request, *args, **kwargs)
            # Otherwise, owners are blocked from the review details endpoint
            raise PermissionDenied(
                "Owners can only access review details while the item is in review or declined."
            )

        # For non-owners, require moderator permissions
        if not (
            request.user.is_authenticated
            and (
                request.user.is_staff
                or request.user.has_perm(f"{app_label}.{perm_codename}")
            )
        ):
            raise PermissionDenied(
                "You do not have permission to access the review details page."
            )
        return super().dispatch(request, *args, **kwargs)

    def _resolve_base_template(self):
        """Return the best matching base template for the object's detail view."""
        obj = getattr(self, "object", None) or super().get_object()
        model = obj.__class__
        app_label = model._meta.app_label
        model_name = model._meta.model_name

        # Candidate templates following Django's DetailView default convention.
        candidates = [
            f"{app_label}/{model_name}_detail.html",
            # Ultimate fallback to our generic detail card
            "simple_detail_card.html",
        ]

        # Select the first template that exists.
        chosen = select_template(candidates)
        return chosen.template.name

    def get_object(self, queryset=None):
        """
        Support generic routing by resolving the object from content type + object id
        if provided in URL kwargs. Fallback to the default DetailView behavior.
        """
        content_type_id = self.kwargs.get("content_type_id")
        object_id = self.kwargs.get("object_id")
        if content_type_id and object_id:
            content_type = get_object_or_404(ContentType, pk=content_type_id)
            model_class = content_type.model_class()
            return get_object_or_404(model_class, pk=object_id)
        return super().get_object(queryset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Resolve and pass the base template the wrapper should extend.
        context["base_template"] = self._resolve_base_template()
        context["review_mode"] = True
        # Provide action history so reviewers can see prior comments and explanations
        try:
            obj = self.object
            ct = ContentType.objects.get_for_model(obj.__class__)
            actions = ReviewAction.objects.filter(
                content_type=ct, object_id=obj.pk
            ).order_by("-created_at", "-id")
        except Exception:
            actions = []
        # Old variable used by wrapper; keep for compatibility
        context["review_actions"] = actions
        # Ensure the embedded review panel in the base detail template is shown
        context["show_review_panel"] = True
        # The review panel expects 'review_logs'
        context["review_logs"] = list(actions)
        return context


class UserCreatedObjectModalDetailView(
    UserCreatedObjectReadAccessMixin, BSModalReadView
):
    template_name_suffix = "_detail_modal"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "modal_title": f"Details of {self.object._meta.verbose_name}",
            }
        )
        return context

    def get_template_names(self):
        try:
            template_names = super().get_template_names()
        except ImproperlyConfigured:
            template_names = []
        template_names.append("modal_detail.html")
        return template_names


class UserCreatedObjectUpdateView(
    UserCreatedObjectWriteAccessMixin, NextOrSuccessUrlMixin, UpdateView
):
    # TODO: Implement permission flow for publication process and moderators.

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "form_title": f"Update {self.object._meta.verbose_name}",
                "submit_button_text": "Save",
            }
        )
        return context

    def get_template_names(self):
        try:
            template_names = super().get_template_names()
        except ImproperlyConfigured:
            template_names = []
        template_names.append("simple_form_card.html")
        return template_names


class UserCreatedObjectCreateWithInlinesView(
    CreateUserObjectMixin, CreateWithInlinesView
):
    formset_helper_class = DynamicTableInlineFormSetHelper

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "form_title": f"Create New {self.form_class._meta.model._meta.verbose_name}",
                "submit_button_text": "Save",
                "formset_helper": self.formset_helper_class(),
            }
        )
        return context

    def get_template_names(self):
        try:
            template_names = super().get_template_names()
        except ImproperlyConfigured:
            template_names = []
        template_names.append("formsets_card.html")
        return template_names


class UserCreatedObjectUpdateWithInlinesView(
    UserCreatedObjectWriteAccessMixin, NextOrSuccessUrlMixin, UpdateWithInlinesView
):
    formset_helper_class = DynamicTableInlineFormSetHelper

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "form_title": f"Update {self.object._meta.verbose_name}",
                "submit_button_text": "Save",
                "formset_helper": self.formset_helper_class(),
            }
        )
        return context

    def get_template_names(self):
        try:
            template_names = super().get_template_names()
        except ImproperlyConfigured:
            template_names = []
        template_names.append("formsets_card.html")
        return template_names


class UserCreatedObjectModalUpdateView(
    UserCreatedObjectWriteAccessMixin, NextOrSuccessUrlMixin, BSModalUpdateView
):
    template_name = "modal_form.html"
    success_message = "Successfully updated."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "modal_title": f"Update {self.object._meta.verbose_name}",
                "submit_button_text": "Save",
            }
        )
        return context


class UserCreatedObjectModalArchiveView(
    UserPassesTestMixin, NextOrSuccessUrlMixin, BSModalDeleteView
):
    """
    A repurposed update view that opens up a modal to ask for confirmation, similar to
    BSModalDeleteView. Instead of deleting the object, after confirmation only the archive method
    instead of the delete method of the object is called.
    """

    template_name = "modal_archive.html"
    success_message = "Successfully archived."

    def test_func(self):
        """Centralized permission check via UserCreatedObjectPermission.has_archive_permission."""
        try:
            obj = self.get_object()
        except Exception:
            return False
        perm = UserCreatedObjectPermission()
        return bool(perm.has_archive_permission(self.request, obj))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "modal_title": f"Archive {self.object._meta.verbose_name}",
                "submit_button_text": "Archive",
            }
        )
        return context

    def get_success_url(self):
        return self.object.get_absolute_url()

    def form_valid(self, form):
        success_url = self.get_success_url()
        self.object.archive()
        return HttpResponseRedirect(success_url)


class UserCreatedObjectModalDeleteView(
    UserCreatedObjectWriteAccessMixin, NextOrSuccessUrlMixin, BSModalDeleteView
):
    template_name = "modal_delete.html"
    success_message = "Successfully deleted."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "form_title": f"Delete {self.object._meta.verbose_name}",
                "submit_button_text": "Delete",
            }
        )
        return context

    def get_success_url(self):
        # Respect explicit 'next' parameter from POST or GET first
        try:
            next_url = self.request.POST.get("next") or self.request.GET.get("next")
            if next_url:
                return next_url
        except Exception:
            pass

        if self.success_url:
            return self.success_url

        if self.object:
            # Determine if this model should use scope parameters in redirect URLs
            # by checking if it's one of the models that have scope-filtered list views
            model_name = self.model.__name__
            # All UserCreatedObject models now have scope filters in their filtersets
            models_with_scope_filtering = [
                "Scenario",
                "Collection",
                "WasteFlyer",
                "Collector",
                "CollectionCatchment",
                "Catchment",
            ]

            if model_name in models_with_scope_filtering:
                # Add scope parameter for models that support scope filtering
                if self.object.publication_status == "published":
                    url = self.model.public_list_url()
                    return f"{url}?scope=published"
                elif self.object.publication_status == "private":
                    url = self.model.private_list_url()
                    return f"{url}?scope=private"
                elif self.object.publication_status == "review":
                    url = self.model.review_list_url()
                    return f"{url}?scope=review"
                elif self.object.publication_status == "declined":
                    url = self.model.private_list_url()
                    return f"{url}?scope=private"
            else:
                # For models without scope filtering, use standard URLs without scope params
                if self.object.publication_status == "published":
                    return self.model.public_list_url()
                elif self.object.publication_status == "private":
                    return self.model.private_list_url()
                elif self.object.publication_status == "review":
                    return self.model.review_list_url()
                elif self.object.publication_status == "declined":
                    return self.model.private_list_url()

        # Fallback to public list without scope
        return self.model.public_list_url()


class OwnedObjectModelSelectOptionsView(
    PermissionRequiredMixin, ModelSelectOptionsView
):
    pass


class UserCreatedObjectAutocompleteView(AutocompleteModelView):
    search_lookups = ["name__icontains"]
    value_fields = [
        "name",
    ]
    ordering = ["name"]
    allow_anonymous = True
    page_size = 15

    def hook_queryset(self, queryset):
        if self.request.user and self.request.user.is_authenticated:
            if self.request.user.is_staff:
                return queryset
            return queryset.filter(
                Q(owner=self.request.user) | Q(publication_status="published")
            )
        return queryset.filter(publication_status="published")

    def apply_filters(self, queryset):
        if not self.filter_by:
            return queryset

        try:
            unquoted = unquote(self.filter_by)
            cleaned = unquoted.replace("'", "")

            if "=" not in cleaned:
                logger.warning(
                    f"No '=' found in filter_by: {repr(cleaned)}, returning original queryset"
                )
                return queryset

            lookup, value = cleaned.split(
                "=", 1
            )  # Use maxsplit=1 to handle multiple '=' chars

        except Exception as e:
            logger.error(f"Error parsing filter_by '{self.filter_by}': {e}")
            return queryset

        if not value:
            value = "published"

        if lookup == "scope__name":
            if value == "private":
                if not self.request.user.is_authenticated:
                    queryset = queryset.none()
                else:
                    queryset = queryset.filter(owner=self.request.user)
            elif value == "published":
                queryset = queryset.filter(publication_status="published")
            else:
                logger.warning(
                    f"Unexpected scope value: {repr(value)}, expected 'private' or 'published'. Defaulting to 'published' behavior."
                )
                queryset = queryset.filter(publication_status="published")
        # Generic guard: skip obviously invalid values (e.g. the language code accidentally
        # injected in the request) that would break lookups expecting an integer PK.
        # Django would raise FieldError / ValueError when trying to cast the string to int.
        if (
            value
            and isinstance(value, str)
            and value.lower() in {"en-us", "en", "de", "fr"}
        ):
            logger.warning(
                "Invalid language code %s supplied for lookup %s – skipping this filter to "
                "avoid EmptyQuerySet and widget validation errors.",
                value,
                lookup,
            )
            return queryset

        # Additional guard for *_id style lookups that require an integer value.
        if lookup.endswith("_id") and value and not value.isdigit():
            logger.warning(
                "Non-numeric value %s supplied for integer lookup %s – skipping filter.",
                value,
                lookup,
            )
            return queryset
        else:
            return queryset
