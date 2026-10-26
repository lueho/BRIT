from __future__ import annotations

import logging
from typing import Any
from urllib.parse import unquote, urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
    UserPassesTestMixin,
)
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages.api import MessageFailure
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import (
    FieldDoesNotExist,
    FieldError,
    ImproperlyConfigured,
    ObjectDoesNotExist,
    PermissionDenied,
    ValidationError,
)
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.db.models import QuerySet
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotAllowed,
    HttpResponseRedirect,
)
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string, select_template
from django.urls import NoReverseMatch, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import capfirst
from django.views.generic import CreateView, DetailView, ListView, UpdateView, View
from django_filters import FilterSet
from django_filters.views import FilterView
from django_tomselect.autocompletes import AutocompleteModelView
from django_tomselect.constants import EXCLUDEBY_VAR, FILTERBY_VAR
from extra_views import CreateWithInlinesView, UpdateWithInlinesView

from utils.modal import (
    BSModalCreateView,
    BSModalDeleteView,
    BSModalReadView,
    BSModalUpdateView,
)
from utils.object_management.filters import ReviewDashboardFilterSet
from utils.object_management.helpers import (
    create_review_action,
    create_review_action_safely,
    invoke_cascade_handler,
)
from utils.object_management.models import (
    ReviewAction,
    ReviewNotificationMute,
    UserCreatedObject,
    populate_owner_review_feedback,
)
from utils.object_management.permissions import (
    UserCreatedObjectPermission,
    _resolve_status_value,
    apply_scope_filter,
    filter_queryset_for_user,
    get_object_policy,
    user_is_moderator_for_model,
)
from utils.object_management.review_hooks import get_breadcrumb_module
from utils.views import get_safe_next_url

from ..forms import (
    DynamicTableInlineFormSetHelper,
    SourcesFieldMixin,
    UserCreatedObjectFormMixin,
)
from ..views import (
    FilterDefaultsMixin,
    ModelSelectOptionsView,
    NextOrSuccessUrlMixin,
    NoFormTagMixin,
    build_breadcrumb_context,
)
from .access import (
    CreateUserObjectMixin,
    UserCreatedObjectReadAccessMixin,
    UserCreatedObjectWriteAccessMixin,
)
from .redirects import ReviewActionRedirectResolver
from .review_queue import ReviewItemCollector

logger = logging.getLogger(__name__)


DEFAULT_BREADCRUMB_MODULES = {
    "bibliography": {"label": "Bibliography", "url_name": "bibliography-explorer"},
    "inventories": {"label": "Inventories", "url_name": "inventories-explorer"},
    "maps": {"label": "Maps", "url_name": "maps-explorer"},
    "materials": {"label": "Materials", "url_name": "materials-explorer"},
    "processes": {"label": "Processes", "url_name": "processes:explorer"},
    "properties": {"label": "Properties", "url_name": "properties-explorer"},
    "sources": {"label": "Sources", "url_name": "sources-explorer"},
    "utils": {"label": "Utilities", "url_name": "utils-explorer"},
    "greenhouses": {
        "label": "Greenhouses",
        "url_name": None,
        "parent_label": "Sources",
        "parent_url_name": "sources-explorer",
    },
    "roadside_trees": {
        "label": "Roadside Trees",
        "url_name": None,
        "parent_label": "Sources",
        "parent_url_name": "sources-explorer",
    },
}


def _get_breadcrumb_model(view):
    model = getattr(view, "model", None)
    if model is not None:
        return model

    form_class = getattr(view, "form_class", None)
    form_meta = getattr(form_class, "_meta", None)
    return getattr(form_meta, "model", None)


def _get_default_breadcrumb_module_config(model):
    if model is None:
        return None
    config = DEFAULT_BREADCRUMB_MODULES.get(model._meta.app_label)
    if config is not None:
        return config
    registered_config = get_breadcrumb_module(model._meta.app_label)
    if registered_config is None:
        return None
    return {
        "label": registered_config.label,
        "url_name": registered_config.url_name,
        "parent_label": registered_config.parent_label,
        "parent_url_name": registered_config.parent_url_name,
    }


def _get_default_breadcrumb_module(model):
    config = _get_default_breadcrumb_module_config(model)
    if config is None:
        return None, None
    return config.get("label"), config.get("url_name")


def _reverse_or_none(route_name):
    if not route_name:
        return None
    try:
        return reverse(route_name)
    except NoReverseMatch:
        return None


def _get_default_breadcrumb_module_url(model):
    _, route_name = _get_default_breadcrumb_module(model)
    return _reverse_or_none(route_name)


def _get_default_breadcrumb_parent_module(model):
    config = _get_default_breadcrumb_module_config(model)
    if config is None:
        return None, None
    return config.get("parent_label"), config.get("parent_url_name")


def _get_default_breadcrumb_parent_module_url(model):
    _, route_name = _get_default_breadcrumb_parent_module(model)
    return _reverse_or_none(route_name)


def _get_default_breadcrumb_section_label(model):
    if model is None:
        return None

    getter = getattr(model, "get_breadcrumb_plural_label", None)
    label = (
        getter()
        if callable(getter)
        else getattr(model._meta, "verbose_name_plural", None)
    )
    if label is None:
        return None
    return capfirst(str(label))


def _get_default_breadcrumb_object_label(obj):
    if obj is None:
        return None

    getter = getattr(obj, "get_breadcrumb_object_label", None)
    label = getter() if callable(getter) else str(obj)
    if label is None:
        return None
    return str(label)


def _get_model_list_url(model):
    if model is None:
        return None

    getter = getattr(model, "public_list_url", None)
    if not callable(getter):
        getter = getattr(model, "list_url", None)
    if callable(getter):
        return getter()
    return getter


def _get_breadcrumb_singular_model_name(model):
    """Singular label for form titles and page titles; ``"Object"`` as fallback."""
    if model is None:
        return "Object"
    getter = getattr(model, "get_breadcrumb_singular_label", None)
    if callable(getter):
        return capfirst(str(getter()))
    return "Object"


def _build_object_form_breadcrumb_context(
    model, *, obj=None, action_label=None, page_title=None
):
    """Shared breadcrumb context for the object create/update form views."""
    module_label, _ = _get_default_breadcrumb_module(model)
    parent_label, _ = _get_default_breadcrumb_parent_module(model)
    return build_breadcrumb_context(
        parent_module_label=parent_label,
        parent_module_url=_get_default_breadcrumb_parent_module_url(model),
        module_label=module_label,
        module_url=_get_default_breadcrumb_module_url(model),
        section_label=_get_default_breadcrumb_section_label(model),
        section_url=_get_model_list_url(model),
        object_label=_get_default_breadcrumb_object_label(obj),
        object_url=getattr(obj, "detail_url", None) if obj is not None else None,
        action_label=action_label,
        page_title=page_title,
    )


def parse_tomselect_filter_expression(raw_expression):
    """Parse a TomSelect filter expression into a lookup/value pair.

    Supports expressions such as ``scope__name='published'``.
    Returns ``None`` for invalid/empty inputs.
    """
    if not raw_expression or not isinstance(raw_expression, str):
        return None

    cleaned = unquote(raw_expression).replace("'", "")
    if "=" not in cleaned:
        return None

    lookup, value = cleaned.split("=", 1)
    lookup = lookup.strip()
    value = value.strip()
    if not lookup:
        return None
    return lookup, value


def get_tomselect_filter_pairs(view, *, use_excludes=False):
    """Return parsed TomSelect filters for a view.

    Supports both:
    - legacy single-value attrs: ``filter_by`` / ``exclude_by``
    - list-based attrs: ``filters_by`` / ``excludes_by``
    """
    list_attr = "excludes_by" if use_excludes else "filters_by"
    single_attr = "exclude_by" if use_excludes else "filter_by"
    query_var = EXCLUDEBY_VAR if use_excludes else FILTERBY_VAR

    raw_values = []

    request = getattr(view, "request", None)
    if request is not None:
        try:
            request_values = request.GET.getlist(query_var)
        except Exception:
            request_values = []
        for raw in request_values:
            if raw and raw not in raw_values:
                raw_values.append(raw)

    list_values = getattr(view, list_attr, None) or []
    if isinstance(list_values, str):
        list_values = [list_values]

    for raw in list_values:
        if raw:
            raw_values.append(raw)

    single_value = getattr(view, single_attr, None)
    if single_value and single_value not in raw_values:
        raw_values.append(single_value)

    parsed = []
    for raw in raw_values:
        item = parse_tomselect_filter_expression(raw)
        if item is None:
            logger.warning("Skipping invalid TomSelect filter expression: %r", raw)
            continue
        parsed.append(item)

    return parsed


def _tomselect_lookup_name(raw_lookup):
    """Return the lookup portion of a TomSelect filter expression's left side.

    The widget sends ``<dependent_field>__<lookup>=<value>`` (and constant
    filters as ``__const__<lookup>=<value>``), so the parsed left side still
    carries the dependent-field prefix that must be stripped to match a bare
    lookup name.
    """
    if raw_lookup.startswith("__const__"):
        return raw_lookup[len("__const__") :]
    if "__" in raw_lookup:
        return raw_lookup.split("__", 1)[1]
    return raw_lookup


def get_tomselect_filter_value(view, *, use_excludes=False, lookup=None):
    """Return first matching TomSelect filter value for a view.

    If ``lookup`` is provided, returns the first value with that lookup.
    Otherwise returns the first parsed filter value.
    """
    for candidate_lookup, candidate_value in get_tomselect_filter_pairs(
        view, use_excludes=use_excludes
    ):
        if (
            lookup is None
            or candidate_lookup == lookup
            or _tomselect_lookup_name(candidate_lookup) == lookup
        ):
            return candidate_value or None
    return None


class ReviewDashboardView(LoginRequiredMixin, FilterDefaultsMixin, FilterView):
    """Dashboard showing all objects in review status that the user can moderate.

    Supports filtering by model type, owner, submission date, and search.
    Dynamically discovers all UserCreatedObject subclasses and shows items
    the current user has permission to moderate.

    The review-queue pipeline lives in ``ReviewItemCollector``; this view only
    wires up the filter form, pagination, and template context.
    """

    template_name = "object_management/review_dashboard.html"
    filterset_class = ReviewDashboardFilterSet
    context_object_name = "review_items"
    paginate_by = getattr(settings, "REVIEW_DASHBOARD_PAGE_SIZE", 20)
    breadcrumb_module_label = "Review"
    breadcrumb_page_title = "Content Review"

    @property
    def collector(self) -> ReviewItemCollector:
        """Return the per-request review-queue collector (created lazily)."""
        collector = getattr(self, "_collector", None)
        if collector is None:
            collector = ReviewItemCollector(
                self.request.user, self.request.GET, page_size=self.paginate_by
            )
            self._collector = collector
        return collector

    def get_available_models(self) -> list[type[UserCreatedObject]]:
        """Return models with review items the current user can moderate."""
        return self.collector.available_models()

    def collect_review_items(self) -> list[UserCreatedObject]:
        """Return the unpaginated review queue (used by the JSON endpoint)."""
        return self.collector.collect(self.get_available_models())

    def get_queryset(self) -> QuerySet[UserCreatedObject]:
        """Return a dummy queryset for FilterView compatibility.

        The actual items are collected in get_context_data().
        """
        available_models = self.get_available_models()
        if available_models:
            return available_models[0].objects.none()
        return self.collector.fallback_queryset()

    def get_filterset_kwargs(self, filterset_class: type[FilterSet]) -> dict[str, Any]:
        """Pass the dummy queryset and available models into the filterset."""
        kwargs = super().get_filterset_kwargs(filterset_class)
        kwargs["available_models"] = self.get_available_models()
        return kwargs

    def paginate_queryset(
        self, queryset: QuerySet[UserCreatedObject], page_size: int
    ) -> tuple[None, None, None, None]:
        """Disable FilterView pagination of the dummy queryset.

        The parent FilterView paginates get_queryset() (an empty queryset) and
        would 404 on page 2+. The review references are paginated in
        get_context_data() instead.
        """
        return (None, None, None, None)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        references, querysets = self.collector.references(self.get_available_models())
        paginator = Paginator(references, self.paginate_by)
        page_obj = paginator.get_page(self.request.GET.get("page"))
        page_obj.object_list = self.collector.hydrate(page_obj.object_list, querysets)

        context.update(
            {
                "title": "Content Review Dashboard",
                "list_type": "review",
                "header": "Content Review Dashboard",
                "review_items": page_obj.object_list,
                "object_list": page_obj.object_list,  # For template compatibility
                "page_obj": page_obj,
                "paginator": paginator,
                "is_paginated": page_obj.has_other_pages(),
            }
        )
        context.update(
            build_breadcrumb_context(
                module_label=self.breadcrumb_module_label,
                page_title=self.breadcrumb_page_title,
            )
        )
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
    redirect_handlers: dict = {}

    def get_object(self, request=None, *args, **kwargs):
        """Get the object being reviewed based on content type and ID.

        Accepts an optional request and varargs for compatibility with callers.
        Resolves IDs from self.kwargs so subclasses (including modal views)
        don't need to override this method.
        """
        cached_object = getattr(self, "object", None)
        if cached_object is not None:
            return cached_object

        content_type_id = self.kwargs.get("content_type_id")
        object_id = self.kwargs.get("object_id")

        content_type = get_object_or_404(ContentType, pk=content_type_id)
        model_class = content_type.model_class()
        obj = get_object_or_404(model_class, pk=object_id)
        self.object = obj
        return obj

    def get_success_url(self):
        """Resolve redirect target using the shared redirect resolver."""
        obj = self.get_object()
        next_url = self.request.POST.get("next") or self.request.GET.get("next")

        resolver = self.get_redirect_resolver(obj)
        default_url = obj.get_absolute_url()
        return resolver.resolve_action_redirect(
            self.review_action, next_url, default_url
        )

    def get_failure_url(self):
        obj = self.get_object()
        next_url = self.request.POST.get("next") or self.request.GET.get("next")
        default_url = obj.get_absolute_url()

        if next_url and self._is_review_detail_url(next_url, obj):
            return default_url

        return next_url or default_url

    def _is_review_detail_url(self, url, obj):
        try:
            review_path = reverse(
                "object_management:review_item_detail",
                kwargs={
                    "content_type_id": ContentType.objects.get_for_model(
                        obj.__class__
                    ).pk,
                    "object_id": obj.pk,
                },
            )
            return urlparse(url).path == review_path
        except (NoReverseMatch, ValueError):
            return False

    def _format_action_error(self, error):
        if isinstance(error, ValidationError):
            if hasattr(error, "message_dict"):
                return " ".join(
                    str(message)
                    for field_messages in error.message_dict.values()
                    for message in field_messages
                )
            if hasattr(error, "messages"):
                return " ".join(str(message) for message in error.messages)

        return str(error)

    def get_action_redirect_handlers(self):
        return dict(self.redirect_handlers)

    def get_redirect_resolver(self, obj):
        return ReviewActionRedirectResolver(
            self.request,
            obj,
            action_handlers=self.get_action_redirect_handlers(),
        )

    def has_action_permission(self, request, obj) -> bool:
        try:
            perm = UserCreatedObjectPermission()
            checker = getattr(perm, str(self.permission_method), None)
            return bool(checker(request, obj)) if callable(checker) else False
        except (AttributeError, TypeError, ObjectDoesNotExist):
            return False

    def test_func(self):  # type: ignore[override]
        try:
            obj = self.get_object()
        except (Http404, ValueError, TypeError, ValidationError):
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
        action_messages = {
            ReviewAction.ACTION_SUBMITTED: "submitted for review",
            ReviewAction.ACTION_APPROVED: "approved",
            ReviewAction.ACTION_REJECTED: "rejected",
            ReviewAction.ACTION_WITHDRAWN: "withdrawn from review",
        }
        action_message = action_messages.get(self.review_action)
        object_name = capfirst(obj._meta.verbose_name)
        if action_message:
            return f"{object_name} has been {action_message}."
        return f"{object_name} has been updated."

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

            # Log review action
            create_review_action_safely(
                self.object,
                request.user,
                self.review_action,
                comment,
                exceptions=DatabaseError,
            )

            # Success message
            try:
                messages.success(
                    request, self.get_success_message(self.object, previous_status)
                )
            except MessageFailure:
                pass

            # Hook for model-specific post-action behavior (e.g., cascading)
            self.post_action_hook(request, previous_status)

        except (ValidationError, ImproperlyConfigured) as e:
            messages.error(request, self._format_action_error(e))
            return HttpResponseRedirect(self.get_failure_url())

        return HttpResponseRedirect(self.get_success_url())

    def post_action_hook(self, request, previous_status=None):
        """
        Hook for subclasses to implement model-specific post-action behavior.

        Called after the main action succeeds and before redirecting.
        Subclasses can override this to add cascading, notifications, etc.

        Args:
            request: The HTTP request
            previous_status: The object's publication_status before the action
        """
        obj = getattr(self, "object", None)
        action_name = getattr(self, "action_attr_name", None)
        if not obj or not action_name:
            return

        invoke_cascade_handler(
            obj,
            action_name,
            actor=getattr(request, "user", None),
            previous_status=previous_status,
            exceptions=(AttributeError, TypeError, ValidationError, DatabaseError),
        )

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

    def post(self, request, *args, **kwargs):  # type: ignore[override]
        """Handle preflight AJAX from modal-forms so real POST carries checkbox."""
        try:
            is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
        except AttributeError:
            is_ajax = False
        if is_ajax:
            # Optional early permission check to fail fast within the modal
            try:
                self.object = self.get_object(request, *args, **kwargs)
                self.ensure_permission(request, self.object)
            except PermissionDenied:
                from django.http import HttpResponseForbidden

                return HttpResponseForbidden(self.permission_denied_message)
            from django.http import HttpResponse

            return HttpResponse(status=204)
        return super().post(request, *args, **kwargs)


# ... rest of the code remains the same ...
class WithdrawFromReviewView(BaseReviewActionView):
    """View to withdraw an item from review."""

    permission_method = "has_withdraw_permission"
    permission_denied_message = (
        "You don't have permission to withdraw this item from review."
    )
    action_attr_name = "withdraw_from_review"
    review_action = ReviewAction.ACTION_WITHDRAWN

    def get_success_url(self):
        obj = getattr(self, "object", None)
        next_url = self.request.POST.get("next") or self.request.GET.get("next")

        if obj and next_url:
            try:
                review_path = reverse(
                    "object_management:review_item_detail",
                    kwargs={
                        "content_type_id": ContentType.objects.get_for_model(
                            obj.__class__
                        ).pk,
                        "object_id": obj.pk,
                    },
                )
            except (NoReverseMatch, ValueError):
                review_path = None

            if review_path:
                parsed_next = urlparse(next_url)
                if parsed_next.path == review_path:
                    try:
                        return obj.get_absolute_url()
                    except (AttributeError, NoReverseMatch, TypeError):
                        pass

        return super().get_success_url()


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
        # If the object supports cascade review actions, expose the affected
        # author count so the modal can show a notice.
        obj = context.get("object")
        if obj is not None and hasattr(obj, "affected_author_count"):
            action = getattr(self, "action_attr_name", None)
            if action:
                try:
                    context["cascade_author_count"] = obj.affected_author_count(action)
                except (
                    AttributeError,
                    TypeError,
                    FieldDoesNotExist,
                    FieldError,
                    DatabaseError,
                ):
                    context["cascade_author_count"] = 0
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
        except AttributeError:
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

    def get_success_url(self):
        return self.object.get_absolute_url()


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


class BaseObjectAccessActionView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Base view for ownership transfer and shared edit access actions.

    Resolves the target object from ContentType and object ID, checks the
    configured permission method on UserCreatedObjectPermission, and redirects
    to 'next' or the object's detail page.
    """

    permission_method: str | None = None
    permission_denied_message: str = "You don't have permission to perform this action."

    def get_object(self):
        cached_object = getattr(self, "object", None)
        if cached_object is not None:
            return cached_object

        content_type = get_object_or_404(
            ContentType, pk=self.kwargs.get("content_type_id")
        )
        model_class = content_type.model_class()
        if model_class is None or not issubclass(model_class, UserCreatedObject):
            raise Http404("Unsupported object type.")
        obj = get_object_or_404(model_class, pk=self.kwargs.get("object_id"))
        self.object = obj
        return obj

    def test_func(self):
        try:
            obj = self.get_object()
        except Http404:
            raise
        except Exception:
            return False
        perm = UserCreatedObjectPermission()
        checker = getattr(perm, str(self.permission_method), None)
        if not callable(checker):
            return False
        try:
            return bool(checker(self.request, obj))
        except Exception:
            return False

    def get_success_url(self):
        next_url = self.request.POST.get("next") or self.request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            return next_url
        try:
            return self.object.get_absolute_url()
        except Exception:
            return "/"

    def _resolve_user(self, username):
        from django.contrib.auth.models import User

        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            return None

    def _resolve_group(self, name, *, trim=False):
        from django.contrib.auth.models import Group

        group = Group.objects.filter(name=name).first()
        if group is None and trim:
            group = Group.objects.filter(name=name.strip()).first()
        return group

    def _resolve_group_id(self, group_id):
        from django.contrib.auth.models import Group

        try:
            return Group.objects.filter(pk=group_id).first()
        except (TypeError, ValueError):
            return None


class TransferOwnershipView(BaseObjectAccessActionView):
    """Transfer ownership of a UserCreatedObject to another user."""

    permission_method = "has_transfer_ownership_permission"
    permission_denied_message = (
        "You don't have permission to transfer ownership of this item."
    )

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        new_owner = self._resolve_user((request.POST.get("new_owner") or "").strip())
        if new_owner is None:
            messages.error(request, "The specified user does not exist.")
            return HttpResponseRedirect(self.get_success_url())
        try:
            obj.transfer_ownership(new_owner, initiator=request.user)
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
            return HttpResponseRedirect(self.get_success_url())
        messages.success(
            request,
            f"Ownership of {capfirst(obj._meta.verbose_name)} has been transferred "
            f"to {new_owner.username}.",
        )
        success_url = self.get_success_url()
        policy = get_object_policy(request.user, obj, request=request)
        if not (
            policy["is_published"]
            or policy["is_owner"]
            or policy["is_editor"]
            or policy["is_staff"]
            or policy["is_moderator"]
        ):
            # The former owner may no longer read the object; avoid a 403 by
            # falling back to the model's private list, or the start page as
            # a last resort.
            try:
                if urlparse(success_url).path == urlparse(obj.get_absolute_url()).path:
                    success_url = self._unreadable_fallback_url(obj)
            except Exception:
                success_url = self._unreadable_fallback_url(obj)
        return HttpResponseRedirect(success_url)

    @staticmethod
    def _unreadable_fallback_url(obj):
        try:
            list_url = type(obj).private_list_url()
            if list_url:
                return f"{list_url}?scope=private"
        except Exception:
            pass
        return "/"


class AddEditorView(BaseObjectAccessActionView):
    """Grant another user edit access to a UserCreatedObject."""

    permission_method = "has_manage_editors_permission"
    permission_denied_message = (
        "You don't have permission to manage edit access for this item."
    )

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        user = self._resolve_user((request.POST.get("user") or "").strip())
        if user is None:
            messages.error(request, "The specified user does not exist.")
            return HttpResponseRedirect(self.get_success_url())
        try:
            obj.add_editor(user, granted_by=request.user)
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
            return HttpResponseRedirect(self.get_success_url())
        messages.success(
            request,
            f"Added a direct edit grant for {user.username} on this {obj._meta.verbose_name}.",
        )
        return HttpResponseRedirect(self.get_success_url())


class RemoveEditorView(BaseObjectAccessActionView):
    """Revoke a user's edit access to a UserCreatedObject."""

    permission_method = "has_manage_editors_permission"
    permission_denied_message = (
        "You don't have permission to manage edit access for this item."
    )

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        user = self._resolve_user((request.POST.get("user") or "").strip())
        if user is None:
            messages.error(request, "The specified user does not exist.")
            return HttpResponseRedirect(self.get_success_url())
        obj.remove_editor(user)
        messages.success(
            request,
            f"Removed the direct edit grant for {user.username} on this {obj._meta.verbose_name}.",
        )
        return HttpResponseRedirect(self.get_success_url())


class AddEditorGroupView(BaseObjectAccessActionView):
    permission_method = "has_manage_editors_permission"
    permission_denied_message = (
        "You don't have permission to manage group edit access for this item."
    )

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        group = self._resolve_group(request.POST.get("group") or "", trim=True)
        if group is None:
            messages.error(request, "The specified group does not exist.")
            return HttpResponseRedirect(self.get_success_url())
        obj.add_editor_group(group, granted_by=request.user)
        messages.success(
            request,
            f"Added an edit grant for group {group.name} on this {obj._meta.verbose_name}.",
        )
        return HttpResponseRedirect(self.get_success_url())


class RemoveEditorGroupView(BaseObjectAccessActionView):
    permission_method = "has_manage_editors_permission"
    permission_denied_message = (
        "You don't have permission to manage group edit access for this item."
    )

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        if "group_id" in request.POST:
            group = self._resolve_group_id(request.POST.get("group_id"))
        else:
            group = self._resolve_group(request.POST.get("group") or "")
        if group is None:
            messages.error(request, "The specified group does not exist.")
            return HttpResponseRedirect(self.get_success_url())
        obj.remove_editor_group(group)
        messages.success(
            request,
            f"Removed the edit grant for group {group.name} on this {obj._meta.verbose_name}.",
        )
        return HttpResponseRedirect(self.get_success_url())


class ManageAccessModalView(BaseObjectAccessActionView):
    """Modal to transfer ownership and manage shared edit access."""

    permission_method = "has_manage_editors_permission"
    permission_denied_message = (
        "You don't have permission to manage access for this item."
    )
    template_name = "object_management/manage_access_modal.html"

    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        context = {
            "object": obj,
            "modal_title": f"Manage access for {obj._meta.verbose_name}",
            "editors": obj.editors.order_by("username"),
            "editor_groups": obj.editor_groups.order_by("name"),
            "next_url": request.GET.get("next"),
            "content_type_id": self.kwargs.get("content_type_id"),
            "object_id": self.kwargs.get("object_id"),
        }
        return HttpResponse(render_to_string(self.template_name, context, request))

    def post(self, request, *args, **kwargs):
        """Preflight handling for django-bootstrap-modal-forms.

        The plugin sends an AJAX POST to the modal URL first; respond with 204
        so it proceeds with the real submit. Because it rewrites the form's
        action to the modal URL before submitting, the real transfer POST also
        arrives here and is dispatched to ``TransferOwnershipView``.
        """
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return HttpResponse(status=204)
        if "new_owner" in request.POST:
            return TransferOwnershipView.as_view()(request, *args, **kwargs)
        actions = {
            "add_editor": AddEditorView,
            "remove_editor": RemoveEditorView,
            "add_editor_group": AddEditorGroupView,
            "remove_editor_group": RemoveEditorGroupView,
        }
        action_view = actions.get(request.POST.get("access_action"))
        if action_view is not None:
            return action_view.as_view()(request, *args, **kwargs)
        return HttpResponseNotAllowed(["GET", "POST"])


class BulkManageAccessView(LoginRequiredMixin, View):
    """Apply an access-management action to multiple UserCreatedObjects.

    Accepts POST data:
    - ``bulk_action``: ``add_editor`` | ``remove_editor`` | ``transfer_ownership``
    - ``username``: the target user
    - ``items``: repeated ``<content_type_id>:<object_id>`` values, or
    - ``all_owned``: apply to every object owned by the requesting user
    - ``next``: optional safe redirect target

    Objects the requesting user may not manage are skipped; a summary
    message reports applied and skipped counts.
    """

    actions = {
        "add_editor": "has_manage_editors_permission",
        "remove_editor": "has_manage_editors_permission",
        "transfer_ownership": "has_transfer_ownership_permission",
    }

    def post(self, request, *args, **kwargs):
        action = request.POST.get("bulk_action")
        permission_method = self.actions.get(action)
        if permission_method is None:
            return HttpResponseBadRequest("Unknown bulk action.")

        from django.contrib.auth.models import User

        username = (request.POST.get("username") or "").strip()
        try:
            target_user = User.objects.get(username=username)
        except User.DoesNotExist:
            messages.error(request, "The specified user does not exist.")
            return HttpResponseRedirect(self._success_url(request))

        objects = self._resolve_objects(request)
        self._objects = objects
        perm = UserCreatedObjectPermission()
        checker = getattr(perm, permission_method)
        applied = skipped = 0
        for obj in objects:
            try:
                if not checker(request, obj):
                    skipped += 1
                    continue
                if action == "add_editor":
                    obj.add_editor(target_user, granted_by=request.user)
                elif action == "remove_editor":
                    obj.remove_editor(target_user)
                else:
                    obj.transfer_ownership(target_user, initiator=request.user)
                applied += 1
            except (ValidationError, PermissionDenied):
                skipped += 1

        label = {
            "add_editor": f"Added direct editor grants for {target_user.username}",
            "remove_editor": f"Removed direct editor grants for {target_user.username}",
            "transfer_ownership": f"Transferred ownership to {target_user.username}",
        }[action]
        if applied:
            messages.success(request, f"{label} for {applied} item(s).")
        if skipped:
            messages.warning(request, f"Skipped {skipped} item(s).")
        if not applied and not skipped:
            messages.info(request, "No items selected.")
        return HttpResponseRedirect(self._success_url(request))

    def _resolve_objects(self, request):
        if request.POST.get("all_owned"):
            from django.apps import apps

            objects = []
            for model in apps.get_models():
                if (
                    issubclass(model, UserCreatedObject)
                    and not model._meta.abstract
                    and not model._meta.proxy
                ):
                    objects.extend(model.objects.filter(owner=request.user))
            return objects

        objects = []
        for item in request.POST.getlist("items"):
            try:
                content_type_id, object_id = item.split(":", 1)
                content_type = ContentType.objects.get(pk=int(content_type_id))
                model_class = content_type.model_class()
                if model_class is None or not issubclass(
                    model_class, UserCreatedObject
                ):
                    continue
                objects.append(model_class.objects.get(pk=int(object_id)))
            except (
                ValueError,
                ContentType.DoesNotExist,
                ObjectDoesNotExist,
            ):
                continue
        return objects

    def _success_url(self, request):
        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return next_url
        for obj in getattr(self, "_objects", []):
            try:
                list_url = type(obj).private_list_url()
                if list_url:
                    return f"{list_url}?scope=private"
            except Exception:
                continue
        return "/"


class UserCreatedObjectListMixin:
    paginate_by = 10
    header = None
    list_type = None
    explorer_url = None
    breadcrumb_parent_module_label = None
    breadcrumb_parent_module_url = None
    breadcrumb_module_label = None
    breadcrumb_module_url = None
    breadcrumb_page_title = None
    breadcrumb_section_label = None
    model = None
    sortable_fields = {}
    sort_param = "ordering"

    def get_sortable_fields(self):
        """Whitelisted sort keys mapping to ORM field paths.

        ``sortable_fields`` may be set on the view or, more commonly, on the
        view's ``filterset_class`` so all scope variants share one definition.
        """
        filterset_class = getattr(self, "filterset_class", None)
        return getattr(filterset_class, "sortable_fields", None) or self.sortable_fields

    def get_current_sort(self):
        """Return the active sort key (e.g. ``name`` or ``-name``) or None.

        Only whitelisted keys from ``get_sortable_fields`` are honoured;
        anything else is ignored safely.
        """
        get_params = getattr(getattr(self, "request", None), "GET", {})
        raw = (get_params.get(self.sort_param) or "").strip()
        key = raw.lstrip("-")
        if key and key in self.get_sortable_fields():
            return ("-" if raw.startswith("-") else "") + key
        return None

    def get_queryset(self):
        queryset = super().get_queryset()
        # Some unit tests call view.get(request) directly without authentication middleware;
        # ensure we handle requests without a 'user' attribute gracefully.
        try:
            user = getattr(self.request, "user", None)
        except Exception:
            user = None

        if not hasattr(queryset.model, "publication_status"):
            raise ImproperlyConfigured(
                f"The model {queryset.model.__name__} must have a 'publication_status' field."
            )

        # List rows render the owner (status cells, policy checks), so pull it in
        # the same query to avoid one auth_user lookup per row.
        owner_field = next(
            (
                field
                for field in queryset.model._meta.fields
                if field.name == "owner" and field.is_relation
            ),
            None,
        )
        if owner_field is not None:
            queryset = queryset.select_related("owner")

        if self.list_type in {"published", "private", "review", "declined", "archived"}:
            queryset = apply_scope_filter(queryset, self.list_type, user=user)
        else:
            queryset = filter_queryset_for_user(queryset, user)

        # An explicitly requested, whitelisted sort takes precedence over the
        # default ordering.
        current_sort = self.get_current_sort()
        if current_sort:
            key = current_sort.lstrip("-")
            prefix = "-" if current_sort.startswith("-") else ""
            return queryset.order_by(f"{prefix}{self.get_sortable_fields()[key]}", "pk")

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

    def get_explorer_url(self):
        return self.explorer_url

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

    def _populate_review_feedback(self, context):
        """Annotate the current page's objects with owner-visible review feedback."""
        page_obj = context.get("page_obj")
        if (
            page_obj is not None
            and getattr(self, "representation_mode", "list") != "gallery"
        ):
            populate_owner_review_feedback(
                page_obj.object_list, getattr(self.request, "user", None)
            )

    def _get_breadcrumb_model(self, context):
        object_list = context.get("object_list")
        return getattr(object_list, "model", None) or getattr(self, "model", None)

    def _base_list_context(self):
        return {
            "header": self.get_header(),
            "create_url": self.get_create_url(),
            "create_url_text": self.get_create_url_text(),
            "create_permission": self.get_create_permission(),
            "list_type": self.get_list_type(),
            "private_list_owner": self.get_private_list_owner(),
            "explorer_url": self.get_explorer_url(),
            "sortable_fields": self.get_sortable_fields(),
            "current_sort": self.get_current_sort() or "",
        }

    def _breadcrumb_context(self, context):
        model = self._get_breadcrumb_model(context)
        default_module_label, _ = _get_default_breadcrumb_module(model)
        default_parent_label, _ = _get_default_breadcrumb_parent_module(model)
        section_label = (
            self.breadcrumb_section_label
            or _get_default_breadcrumb_section_label(model)
        )
        return build_breadcrumb_context(
            parent_module_label=self.breadcrumb_parent_module_label
            or default_parent_label,
            parent_module_url=(
                self.breadcrumb_parent_module_url
                or _get_default_breadcrumb_parent_module_url(model)
            ),
            module_label=self.breadcrumb_module_label or default_module_label,
            module_url=(
                self.breadcrumb_module_url
                or self.get_explorer_url()
                or _get_default_breadcrumb_module_url(model)
            ),
            section_label=section_label,
            page_title=(
                self.breadcrumb_page_title or self.get_header() or section_label
            ),
        )

    def _scope_model(self):
        """Return the model used for scope-switcher URL resolution."""
        try:
            return self.get_queryset().model
        except Exception:
            return getattr(self, "model", None)

    @staticmethod
    def _call_or_value(value):
        return value() if callable(value) else value

    @staticmethod
    def _map_url(model, attr):
        try:
            getter = getattr(model, attr, None)
            if callable(getter):
                return getter()
        except Exception:
            pass
        return None

    @staticmethod
    def _conventional_scope_url(model, suffix):
        """Try the conventional URL name ``<model_name>-<suffix>``."""
        model_name = getattr(getattr(model, "_meta", None), "model_name", None)
        if not model_name:
            return None
        try:
            return reverse(f"{model_name}-{suffix}")
        except Exception:
            return None

    def _scope_fallback_url(self, scope_value):
        """Current URL with the scope overridden and pagination reset."""
        params = self.request.GET.copy()
        params.pop("page", None)
        params["scope"] = scope_value
        encoded = params.urlencode()
        return f"{self.request.path}?{encoded}" if encoded else self.request.path

    def _scope_context(self):
        """Scope-switcher context: public/private/review, map, and gallery URLs."""
        model = self._scope_model()
        urls = {
            "public_url": self._call_or_value(getattr(model, "public_list_url", None)),
            "private_url": self._call_or_value(
                getattr(model, "private_list_url", None)
            ),
            "review_url": self._call_or_value(getattr(model, "review_list_url", None)),
        }
        # Conventional URL names: <model>-list, <model>-list-owned, <model>-list-review
        for key, suffix in (
            ("public_url", "list"),
            ("private_url", "list-owned"),
            ("review_url", "list-review"),
        ):
            if not urls[key]:
                urls[key] = self._conventional_scope_url(model, suffix)
        # Last resort: rebuild the current URL with a scope override
        try:
            for key, scope in (
                ("public_url", "published"),
                ("private_url", "private"),
                ("review_url", "review"),
            ):
                if not urls[key]:
                    urls[key] = self._scope_fallback_url(scope)
        except Exception:
            pass

        return {
            "active_scope": self.get_list_type(),
            "representation_mode": "list",
            "public_representation_url": urls["public_url"],
            "private_representation_url": urls["private_url"],
            "review_representation_url": urls["review_url"],
            "public_gallery_url": None,
            "private_gallery_url": None,
            "review_gallery_url": None,
            # Map URLs for header view toggle (may be None if model has no map views)
            "public_map_url": self._map_url(model, "public_map_url"),
            "private_map_url": self._map_url(model, "private_map_url"),
            "review_map_url": self._map_url(model, "review_map_url"),
            **urls,
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self._populate_review_feedback(context)
        context.update(self._base_list_context())
        context.update(self._breadcrumb_context(context))
        context.update(self._scope_context())
        return context


class PublishedObjectListMixin(UserCreatedObjectListMixin):
    list_type = "published"


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

    permission_method = "has_comment_permission"
    permission_denied_message = "You don't have permission to comment on this item."

    def post(self, request, *args, **kwargs):
        self.object = self.get_object(request, *args, **kwargs)
        self.ensure_permission(request, self.object)
        obj = self.object

        # Must be authenticated
        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required.")

        message = (request.POST.get("message") or "").strip()
        if not message:
            messages.error(request, "Comment cannot be empty.")
            return HttpResponseRedirect(self.get_success_url())

        create_review_action(obj, request.user, ReviewAction.ACTION_COMMENT, message)

        messages.success(request, "Comment added.")
        return HttpResponseRedirect(self.get_success_url())


class ReviewNotificationMuteView(BaseReviewActionView):
    """Toggle per-object review notification e-mails for the current user."""

    permission_method = "has_comment_permission"
    permission_denied_message = (
        "You don't have permission to change notifications for this item."
    )
    template_name = "object_management/review_notification_mute.html"

    def get_object(self, request=None, *args, **kwargs):
        content_type = get_object_or_404(
            ContentType, pk=self.kwargs.get("content_type_id")
        )
        model_class = content_type.model_class()
        if model_class is None or not issubclass(model_class, UserCreatedObject):
            raise Http404("Review notifications are not available for this item.")
        return super().get_object(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        obj = self.get_object(request, *args, **kwargs)
        self.ensure_permission(request, obj)
        return render(
            request,
            self.template_name,
            {
                "object": obj,
                "muted": self._is_muted(request.user, obj),
                "review_url": reverse(
                    "object_management:review_item_detail",
                    kwargs={
                        "content_type_id": self.kwargs["content_type_id"],
                        "object_id": obj.pk,
                    },
                ),
            },
        )

    def post(self, request, *args, **kwargs):
        obj = self.get_object(request, *args, **kwargs)
        self.ensure_permission(request, obj)
        mute, created = ReviewNotificationMute.objects.get_or_create(
            user=request.user,
            content_type_id=self.kwargs["content_type_id"],
            object_id=obj.pk,
        )
        if created:
            messages.success(request, "E-mail notifications for this item disabled.")
        else:
            mute.delete()
            messages.success(request, "E-mail notifications for this item enabled.")
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        next_url = self.request.POST.get("next") or self.request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            return next_url
        return self.get_object().get_absolute_url()

    def _is_muted(self, user, obj):
        return ReviewNotificationMute.objects.filter(
            user=user,
            content_type_id=self.kwargs["content_type_id"],
            object_id=obj.pk,
        ).exists()


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
        return user_is_moderator_for_model(user, model)

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


class ReviewObjectListView(ReviewObjectListMixin, ListView):
    """A view to display a list of objects under review for moderators/staff."""

    def get_template_names(self):
        template_names = super().get_template_names()
        template_names.append("simple_list_card.html")
        return template_names


class RequestAwareFormMixin:
    """Pass ``request`` to forms that are built to receive it.

    Forms mixing in ``UserCreatedObjectFormMixin`` or ``SourcesFieldMixin``
    accept a ``request`` keyword argument; other forms must not get it.
    Modal form views receive ``request`` unconditionally through
    ``PassRequestMixin`` instead.
    """

    request_form_mixins = (UserCreatedObjectFormMixin, SourcesFieldMixin)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if issubclass(self.get_form_class(), self.request_form_mixins):
            kwargs["request"] = self.request
        return kwargs


class UserCreatedObjectCreateView(
    RequestAwareFormMixin,
    CreateUserObjectMixin,
    NoFormTagMixin,
    SuccessMessageMixin,
    CreateView,
):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        model = _get_breadcrumb_model(self)
        model_name = _get_breadcrumb_singular_model_name(model)
        context.update(
            {
                "form_title": f"Create New {model_name}",
                "submit_button_text": "Save",
            }
        )
        context.update(
            _build_object_form_breadcrumb_context(
                model,
                action_label="Create",
                page_title=f"Create {model_name}",
            )
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

    def get_form_kwargs(self):
        """Pass request to form - required by bootstrap_modal_forms and our custom mixins."""
        kwargs = super().get_form_kwargs()
        # Always pass request for modal forms since PopRequestMixin expects it
        kwargs["request"] = self.request
        return kwargs

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
            {
                "modal_title": f"Create New {model_name}",
                "submit_button_text": "Save",
            }
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
        template_names.append("detail_with_options.html")
        return template_names

    def get_object(self, queryset=None):
        cached_object = getattr(self, "object", None)
        if cached_object is not None:
            return cached_object

        obj = super().get_object(queryset)
        self.object = obj
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.object
        request = self.request
        default_module_label, _ = _get_default_breadcrumb_module(obj.__class__)
        default_parent_label, _ = _get_default_breadcrumb_parent_module(obj.__class__)
        breadcrumb_section_label = _get_default_breadcrumb_section_label(obj.__class__)
        breadcrumb_object_label = _get_default_breadcrumb_object_label(obj)
        # Show review panel when explicitly requested via ?review=1 — but only
        # for users with a review relationship to the object. The panel exposes
        # moderation metadata (reviewer names, actions, comments) that must not
        # leak to arbitrary readers of a published object.
        policy = get_object_policy(request.user, obj, request=request)
        show_panel = request.GET.get("review") is not None and (
            policy["is_owner"] or policy["is_editor"] or policy["is_moderator"]
        )

        logs = []
        if show_panel:
            try:
                logs = list(ReviewAction.for_object(obj).select_related("user"))
            except (DatabaseError, FieldError, AttributeError):
                logs = []

        context.update(
            {
                "show_review_panel": show_panel,
                "review_logs": logs,
            }
        )
        context.update(
            build_breadcrumb_context(
                parent_module_label=default_parent_label,
                parent_module_url=_get_default_breadcrumb_parent_module_url(
                    obj.__class__
                ),
                module_label=default_module_label,
                module_url=_get_default_breadcrumb_module_url(obj.__class__),
                section_label=breadcrumb_section_label,
                section_url=getattr(obj, "list_url", None),
                object_label=breadcrumb_object_label,
                page_title=breadcrumb_object_label,
            )
        )
        return context


class ReviewItemDetailView(UserCreatedObjectDetailView):
    """
    Render the regular DetailView of an object, but inject a review action bar
    (available actions + optional reviewer comment field) at the top of the page.

    Implementation strategy:
    - Use a wrapper template that extends the object's normal detail template.
    - Determine the base detail template via Django's default naming convention
      (<app_label>/<model_name>_detail.html) and fall back to detail_with_options.html.
    - Provide the resolved base template to the wrapper via context as 'base_template'.
    - Support model-specific subclasses via registry pattern for specialized context.

    Routing and delegation model:
    - URLConf always points to this base class (`ReviewItemDetailView.as_view()`).
    - `dispatch()` resolves the target object and can delegate to a model-specific
      subclass registered via `register_for_model()`.
    - Observability tools may still report the base view as the routed endpoint,
      because delegation happens inside this class at runtime.

    Subclasses can register themselves for specific models and set
    ``detail_view_class`` to reuse that model's regular detail context.
    Subclasses with other review-specific context needs may override
    ``get_review_specific_context()``.
    """

    template_name = "object_management/review_detail_wrapper.html"
    detail_view_class = None
    permission_denied_message = (
        "You do not have permission to access the review details page."
    )
    _model_view_registry = {}

    @classmethod
    def register_for_model(cls, model_class):
        """
        Register this view class as the handler for a specific model.

        This updates the in-memory registry used by `ReviewItemDetailView.dispatch()`.
        It does not add or change URL patterns: requests still enter through the
        base `review_item_detail` route and are delegated after object resolution.

        Usage in subclass:
            class CollectionReviewItemDetailView(ReviewItemDetailView):
                model = Collection

            CollectionReviewItemDetailView.register_for_model(Collection)
        """
        ReviewItemDetailView._model_view_registry[model_class] = cls

    def test_func(self):
        """Allow access for staff, moderators, and owners.

        This overrides the default read-access mixin so that non-staff moderators who
        hold the dynamic per-model permission (can_moderate_<model>) may access the
        review detail view. Owners are permitted to access the review view for any
        of their objects to see review history and activity.
        """
        user = getattr(self, "request", None) and self.request.user
        if not user or not getattr(user, "is_authenticated", False):
            return False

        obj = self.get_object()
        policy = get_object_policy(user, obj, request=self.request)

        if policy["is_owner"]:
            return True

        return user_is_moderator_for_model(user, obj.__class__)

    def dispatch(self, request, *args, **kwargs):
        """
        Authorize review details for moderators/staff and for owners.

        Delegation order:
        1. Resolve object from content type/object id.
        2. Look up model class in `_model_view_registry`.
        3. If a specialized class is registered, call that class via `as_view()` and
           return its response.
        4. Otherwise execute base authorization and rendering.

        Owners can access the review page for any of their objects to see review
        history and activity, regardless of publication status.
        """
        obj = self.get_object()
        model_class = obj.__class__

        # Check if there's a specialized review view registered for this model
        specialized_view_class = self._model_view_registry.get(model_class)
        if specialized_view_class and specialized_view_class != self.__class__:
            # Create instance of specialized view and delegate
            specialized_view = specialized_view_class.as_view()
            return specialized_view(request, *args, **kwargs)

        # Standard authorization checks
        policy = get_object_policy(request.user, obj, request=request)

        if policy["is_owner"]:
            return super().dispatch(request, *args, **kwargs)

        if not user_is_moderator_for_model(request.user, obj.__class__):
            return self.handle_no_permission()
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
            "detail_with_options.html",
        ]

        # Select the first template that exists.
        chosen = select_template(candidates)
        return chosen.template.name

    def _resolve_model_class(self, content_type, object_id):
        model_class = content_type.model_class()
        if model_class in self._model_view_registry:
            return model_class

        for proxy_model in self._model_view_registry:
            if (
                proxy_model._meta.proxy
                and proxy_model._meta.concrete_model is model_class
                and proxy_model.objects.filter(pk=object_id).exists()
            ):
                return proxy_model

        return model_class

    def get_object(self, queryset=None):
        """
        Support generic routing by resolving the object from content type + object id
        if provided in URL kwargs. Fallback to the default DetailView behavior.

        Caches the result on self.object to avoid duplicate queries when called
        from test_func(), dispatch(), and get_context_data().
        """
        if hasattr(self, "object") and self.object is not None:
            return self.object

        content_type_id = self.kwargs.get("content_type_id")
        object_id = self.kwargs.get("object_id")
        if content_type_id and object_id:
            content_type = get_object_or_404(ContentType, pk=content_type_id)
            model_class = self._resolve_model_class(content_type, object_id)
            obj = get_object_or_404(model_class, pk=object_id)
        else:
            obj = super().get_object(queryset)

        self.object = obj
        return obj

    def get_review_specific_context(self, context):
        """
        Return context generated by the model's regular detail view.

        Subclasses may set ``detail_view_class`` to reuse model-specific detail
        context, or override this method for other review-specific context.

        Args:
            context: The context dict built so far

        Returns:
            dict: Additional context items to merge into the main context
        """
        if self.detail_view_class is None:
            return {}

        detail_view = self.detail_view_class()
        detail_view.request = self.request
        detail_view.args = self.args
        detail_view.kwargs = self.kwargs
        detail_view.object = self.object
        detail_context = detail_view.get_context_data(object=self.object)
        for review_key in ("review_logs", "review_mode", "show_review_panel"):
            detail_context.pop(review_key, None)
        return detail_context

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Resolve and pass the base template the wrapper should extend
        context["base_template"] = self._resolve_base_template()
        context["review_mode"] = True

        # Provide action history so reviewers can see prior comments and explanations
        try:
            obj = self.object
            ct = ContentType.objects.get_for_model(obj.__class__)
            actions = list(
                ReviewAction.objects.filter(content_type=ct, object_id=obj.pk)
                .select_related("user")
                .order_by("-created_at", "-id")
            )
        except (DatabaseError, FieldError, AttributeError):
            actions = []

        # Old variable used by wrapper; keep for compatibility
        context["review_actions"] = actions
        # Ensure the embedded review panel in the base detail template is shown
        context["show_review_panel"] = True
        # The review panel expects 'review_logs'
        context["review_logs"] = actions

        # Allow subclasses to add model-specific context
        model_specific_context = self.get_review_specific_context(context)
        if model_specific_context:
            context.update(model_specific_context)

        return context


class UserCreatedObjectModalDetailView(
    UserCreatedObjectReadAccessMixin, BSModalReadView
):
    template_name_suffix = "_detail_modal"

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return HttpResponse(
                render_to_string(
                    "modal_message.html",
                    {
                        "title": "Access restricted",
                        "message": self.get_permission_denied_message(),
                    },
                ),
                status=403,
            )
        html = render_to_string(
            "modal_message.html",
            {
                "title": "Access restricted",
                "message": "This content is not publicly available. Please log in if you are the owner.",
            },
        )
        return HttpResponse(html)

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
    RequestAwareFormMixin,
    UserCreatedObjectWriteAccessMixin,
    NextOrSuccessUrlMixin,
    UpdateView,
):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        verbose_name = self.object._meta.verbose_name
        context.update(
            {
                "form_title": f"Update {verbose_name}",
                "submit_button_text": "Save",
            }
        )
        context.update(
            _build_object_form_breadcrumb_context(
                self.object.__class__,
                obj=self.object,
                action_label="Update",
                page_title=f"Update {verbose_name}",
            )
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
    RequestAwareFormMixin, CreateUserObjectMixin, CreateWithInlinesView
):
    formset_helper_class = DynamicTableInlineFormSetHelper

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        model = _get_breadcrumb_model(self)
        model_name = _get_breadcrumb_singular_model_name(model)
        context.update(
            {
                "form_title": f"Create New {model_name}",
                "submit_button_text": "Save",
                "formset_helper": self.formset_helper_class(),
            }
        )
        context.update(
            _build_object_form_breadcrumb_context(
                model,
                action_label="Create",
                page_title=f"Create {model_name}",
            )
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
    RequestAwareFormMixin,
    UserCreatedObjectWriteAccessMixin,
    NextOrSuccessUrlMixin,
    UpdateWithInlinesView,
):
    formset_helper_class = DynamicTableInlineFormSetHelper

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        verbose_name = self.object._meta.verbose_name
        context.update(
            {
                "form_title": f"Update {verbose_name}",
                "submit_button_text": "Save",
                "formset_helper": self.formset_helper_class(),
            }
        )
        context.update(
            _build_object_form_breadcrumb_context(
                self.object.__class__,
                obj=self.object,
                action_label="Update",
                page_title=f"Update {verbose_name}",
            )
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
        except (Http404, AttributeError) as e:
            logger.debug(f"Could not get object for archive permission check: {e}")
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
    object_policy_action = "delete"
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
        # Respect a safe 'next' parameter from POST or GET first
        next_url = get_safe_next_url(self.request)
        if next_url:
            return next_url

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

    def __init_subclass__(cls, **kwargs):
        """Preserve inherited search_lookups/value_fields that the upstream
        ``AutocompleteModelView.__init_subclass__`` would reset to ``[]``."""
        # Save inherited values before super().__init_subclass__ resets them.
        saved = {}
        for attr in ("search_lookups", "value_fields"):
            if attr not in cls.__dict__:
                for base in cls.__mro__[1:]:
                    if attr in base.__dict__:
                        saved[attr] = list(base.__dict__[attr])
                        break
        super().__init_subclass__(**kwargs)
        for attr, value in saved.items():
            setattr(cls, attr, value)

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        # Widgets render preselected options through this view with the page
        # request; that page's own ``q`` must not filter the selected objects.
        match = getattr(request, "resolver_match", None)
        if getattr(getattr(match, "func", None), "view_class", None) is not type(self):
            self.query = ""

    def hook_queryset(self, queryset):
        qs = filter_queryset_for_user(queryset, self.request.user)
        try:
            archived_val = _resolve_status_value(queryset.model, "archived")
            return qs.exclude(publication_status=archived_val)
        except Exception:
            # If model has no publication_status or resolution fails, return filtered qs as-is
            return qs

    def apply_filters(self, queryset):
        filter_pairs = get_tomselect_filter_pairs(self)
        if not filter_pairs:
            return queryset

        for lookup, value in filter_pairs:
            if lookup == "scope__name":
                scope_value = value or "published"
                try:
                    queryset = apply_scope_filter(
                        queryset, scope_value, user=self.request.user
                    )
                except ImproperlyConfigured:
                    return queryset.none()
                continue

            if not value:
                continue

            # Generic guard: skip obviously invalid values (e.g. the language code accidentally
            # injected in the request) that would break lookups expecting an integer PK.
            # Fail closed to avoid unintentionally broadening results.
            if (
                value
                and isinstance(value, str)
                and value.lower() in {"en-us", "en", "de", "fr"}
            ):
                logger.debug(
                    "Invalid language code %s supplied for lookup %s – skipping this filter to "
                    "avoid EmptyQuerySet and widget validation errors.",
                    value,
                    lookup,
                )
                return queryset.none()

            # Additional guard for *_id style lookups that require an integer value.
            if lookup.endswith("_id") and value and not value.isdigit():
                logger.debug(
                    "Non-numeric value %s supplied for integer lookup %s – skipping filter.",
                    value,
                    lookup,
                )
                return queryset.none()

            try:
                queryset = self.filter_by_lookup(queryset, lookup, value)
            except Exception as e:
                logger.debug("Error applying filter %s=%r: %s", lookup, value, e)
                return queryset.none()

        return queryset

    def filter_by_lookup(self, queryset, lookup, value):
        return queryset.filter(**{lookup: value})
