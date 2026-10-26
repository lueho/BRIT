"""Collection of review-queue items across all UserCreatedObject models.

The review dashboard, the JSON queue endpoint, and the navigation badge all
draw from the same pipeline: discover models the user can moderate, filter each
model's in-review queryset in SQL, sort lightweight references in Python, and
hydrate only the objects that will actually be rendered.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime
from typing import NamedTuple

from django.apps import apps
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist, FieldError
from django.db.models import CharField, Q, QuerySet, Value
from django.http import QueryDict

from .models import ReviewAction, UserCreatedObject
from .policy import is_active_actor, is_admin, reviewable_queryset
from .registry import KIND_REVIEWABLE, model_policy
from .review_filtering import ReviewItemFilter
from .review_hooks import get_review_search_fields

logger = logging.getLogger(__name__)

# Errors a model's review queryset may raise when it does not support the
# review pipeline; such models are skipped rather than aborting the queue.
RECOVERABLE_MODEL_ERRORS = (
    AttributeError,
    FieldDoesNotExist,
    FieldError,
    TypeError,
    ValueError,
)


class ReviewItemReference(NamedTuple):
    """Lightweight stand-in for a reviewable object before hydration.

    The queue collects these per model from a single ``values_list`` query and
    hydrates only the paginated page's worth of objects.
    """

    model: type[UserCreatedObject]
    pk: int
    name: str | None
    submitted_at: datetime | None


class ReviewItemCollector:
    """Builds the review queue for a single user and set of filter params.

    ``params`` mirrors ``request.GET`` (search, model_type, owner,
    submitted_after, submitted_before, ordering). ``page_size`` bounds the
    per-model prefetch window used when no filters are active.
    """

    def __init__(
        self,
        user,
        params: QueryDict | None = None,
        page_size: int = 20,
    ) -> None:
        self.user = user
        self.params = params if params is not None else QueryDict("")
        self.page_size = page_size
        self._available_models_cache: list[type[UserCreatedObject]] | None = None

    # --- Model discovery -------------------------------------------------

    @staticmethod
    def in_review_queryset_for_model(
        model: type[UserCreatedObject],
    ) -> QuerySet[UserCreatedObject]:
        """Return a queryset containing review items for the provided model.

        Supports models whose manager either:
        - exposes ``in_review()`` directly,
        - exposes a queryset with ``in_review()``, or
        - only supports standard queryset filtering.
        """
        manager = model.objects
        if hasattr(manager, "in_review"):
            return manager.in_review()

        queryset = manager.get_queryset()
        if hasattr(queryset, "in_review"):
            return queryset.in_review()

        try:
            model._meta.get_field("publication_status")
        except FieldDoesNotExist as exc:
            raise AttributeError(
                f"{model.__name__} has no publication_status field for review filtering"
            ) from exc

        return queryset.filter(publication_status=UserCreatedObject.STATUS_REVIEW)

    @staticmethod
    def is_primary_model_module(model: type[UserCreatedObject]) -> bool:
        """Return whether a model is defined in the app's models module tree."""
        module_name = getattr(model, "__module__", "")
        app_config = getattr(model._meta, "app_config", None)
        app_name = getattr(app_config, "name", None) or model._meta.app_label
        expected_prefix = f"{app_name}.models"
        return module_name == expected_prefix or module_name.startswith(
            f"{expected_prefix}."
        )

    @staticmethod
    def _candidate_models() -> Iterable[type[UserCreatedObject]]:
        """Yield concrete UserCreatedObject subclasses registered as reviewable.

        Only models whose registry policy is ``KIND_REVIEWABLE`` are moderation
        targets; owned children and unregistered subclasses are never queued.
        """
        for model in apps.get_models():
            policy = model_policy(model)
            if (
                issubclass(model, UserCreatedObject)
                and not model._meta.abstract
                and policy is not None
                and policy.kind == KIND_REVIEWABLE
                and ReviewItemCollector.is_primary_model_module(model)
                and hasattr(model, "objects")
            ):
                yield model

    @staticmethod
    def _moderation_checker(user):
        """Return a predicate: can ``user`` moderate the given model class.

        Inactive actors can moderate nothing; administrators can moderate all
        registered models; everyone else needs the explicit
        ``<app_label>.can_moderate_<model>`` permission — staff status alone
        grants no moderation capability.
        """
        if not is_active_actor(user):
            return lambda model: False
        if is_admin(user):
            return lambda model: True
        return lambda model: user.has_perm(
            f"{model._meta.app_label}.can_moderate_{model._meta.model_name}"
        )

    @staticmethod
    def _priority_models() -> list[type[UserCreatedObject]]:
        """Return configured priority models that always sort first."""
        models = []
        for model_path in getattr(settings, "REVIEW_DASHBOARD_PRIORITY_MODELS", []):
            try:
                app_label, model_name = model_path.split(".")
                models.append(apps.get_model(app_label, model_name))
            except (ValueError, LookupError) as e:
                logger.warning("Could not load priority model '%s': %s", model_path, e)
        return models

    def _scoped_queryset_for_model(
        self, model: type[UserCreatedObject]
    ) -> QuerySet[UserCreatedObject]:
        """Return the policy-scoped queryset for the requested review scope.

        ``?scope=review`` (default) uses the model's in-review manager; any
        other scope (``declined``) starts from the full table and lets the
        policy apply the state filter. Unknown scopes fail closed inside
        ``reviewable_queryset`` — they never widen the base.
        """
        scope = self.params.get("scope", "review")
        base = (
            self.in_review_queryset_for_model(model)
            if scope == "review"
            else model.objects.all()
        )
        return reviewable_queryset(self.user, base, scope=scope)

    def _has_visible_review_items(self, model: type[UserCreatedObject]) -> bool:
        """Return whether the model has review items not owned by this user."""
        return self._scoped_queryset_for_model(model).exclude(owner=self.user).exists()

    def available_models(self) -> list[type[UserCreatedObject]]:
        """Discover all concrete UserCreatedObject subclasses that have items in review.

        Returns models that either:
        1. Have items currently in review, OR
        2. Are in the priority list and user has moderation permissions

        Optimized to avoid N+1 queries by pre-fetching all user permissions.
        Results are cached per collector instance.
        """
        if self._available_models_cache is not None:
            return self._available_models_cache

        if not is_active_actor(self.user):
            self._available_models_cache = []
            return self._available_models_cache

        priority_positions = {
            model: index for index, model in enumerate(self._priority_models())
        }
        can_moderate = self._moderation_checker(self.user)

        available_models = []
        for model in self._candidate_models():
            if model in available_models or not can_moderate(model):
                continue
            try:
                if self._has_visible_review_items(model):
                    available_models.append(model)
            except RECOVERABLE_MODEL_ERRORS as e:
                # Model may not have in_review() manager method or other issues
                logger.debug(
                    "Could not check review items for %s: %s",
                    model.__name__,
                    e,
                )

        available_models.sort(
            key=lambda model: (
                priority_positions.get(model, len(priority_positions)),
                model._meta.verbose_name,
            )
        )
        self._available_models_cache = available_models
        return available_models

    def has_review_items(self) -> bool:
        """Return whether the user can moderate any pending review item."""
        user = self.user
        if not user or not getattr(user, "is_authenticated", False):
            return False

        can_moderate = self._moderation_checker(user)
        for model in self._candidate_models():
            if not can_moderate(model):
                continue
            try:
                if self._has_visible_review_items(model):
                    return True
            except RECOVERABLE_MODEL_ERRORS as exc:
                logger.debug(
                    "Could not check review items for %s: %s",
                    model.__name__,
                    exc,
                )
        return False

    @staticmethod
    def fallback_queryset() -> QuerySet:
        """Return an empty queryset from a stable model for FilterView plumbing."""
        fallback_models = sorted(
            ReviewItemCollector._candidate_models(),
            key=lambda model: (model._meta.app_label, model._meta.model_name),
        )
        if fallback_models:
            return fallback_models[0].objects.none()
        return ReviewAction.objects.none()

    # --- SQL filtering ----------------------------------------------------

    def _has_active_query_filters(self) -> bool:
        """Return whether any non-ordering filters are active."""
        return bool(
            self.params.get("search", "").strip()
            or self.params.getlist("model_type")
            or self.params.get("owner")
            or self.params.get("submitted_after")
            or self.params.get("submitted_before")
        )

    def _selected_model_type_ids(self) -> set[int]:
        """Return valid selected content type IDs from the params."""
        return {
            int(model_type)
            for model_type in self.params.getlist("model_type")
            if model_type.isdigit()
        }

    def _parse_submitted_date(self, parameter_name: str) -> date | None:
        """Parse a submitted date filter, returning None for invalid values."""
        raw_value = (self.params.get(parameter_name) or "").strip()
        if not raw_value:
            return None
        try:
            return datetime.strptime(raw_value, "%Y-%m-%d").date()
        except ValueError as exc:
            logger.warning("Invalid date filter value '%s': %s", raw_value, exc)
            return None

    @staticmethod
    def _matches_selected_model_types(
        model_class: type[UserCreatedObject], selected_model_type_ids: set[int]
    ) -> bool:
        """Return whether a model is included by the selected model_type filter."""
        if not selected_model_type_ids:
            return True
        return (
            ContentType.objects.get_for_model(model_class).id in selected_model_type_ids
        )

    @staticmethod
    def _apply_search_filter(
        queryset: QuerySet[UserCreatedObject],
        model_class: type[UserCreatedObject],
        search: str,
    ) -> QuerySet[UserCreatedObject]:
        """Apply model-specific search filters at the database level."""
        search_filters = []

        try:
            model_class._meta.get_field("name")
            search_filters.append(Q(name__icontains=search))
        except FieldDoesNotExist:
            pass

        for field_name in get_review_search_fields(model_class):
            search_filters.append(Q(**{f"{field_name}__icontains": search}))

        if not search_filters:
            return queryset.none()

        combined_filter = search_filters[0]
        for search_filter in search_filters[1:]:
            combined_filter |= search_filter
        return queryset.filter(combined_filter)

    def _apply_database_review_filters(
        self,
        queryset: QuerySet[UserCreatedObject],
        model_class: type[UserCreatedObject],
    ) -> QuerySet[UserCreatedObject]:
        """Apply active dashboard filters directly to a model queryset."""
        queryset = queryset.exclude(owner=self.user)

        owner_id = (self.params.get("owner") or "").strip()
        if owner_id:
            if owner_id.isdigit():
                queryset = queryset.filter(owner_id=int(owner_id))
            else:
                logger.warning("Invalid owner_id filter value: %s", owner_id)

        submitted_after = self._parse_submitted_date("submitted_after")
        if submitted_after is not None:
            queryset = queryset.filter(submitted_at__date__gte=submitted_after)

        submitted_before = self._parse_submitted_date("submitted_before")
        if submitted_before is not None:
            queryset = queryset.filter(submitted_at__date__lte=submitted_before)

        search = self.params.get("search", "").strip()
        if search:
            queryset = self._apply_search_filter(queryset, model_class, search)

        return queryset

    def _apply_requested_ordering(
        self, items: Iterable[ReviewItemReference]
    ) -> list[ReviewItemReference]:
        """Sort heterogeneous review items using the dashboard ordering option."""
        ordering = self.params.get("ordering", "-submitted_at")
        filter_obj = ReviewItemFilter([], self.params)
        return filter_obj._apply_ordering(list(items), ordering)

    @staticmethod
    def _select_related_fields(model_class: type[UserCreatedObject]) -> list[str]:
        """Return common foreign keys that are safe to select_related."""
        select_fields = ["owner", "approved_by"]
        for field_name in (
            "property",
            "unit",
            "material",
            "sample",
            "catchment",
            "waste_category",
            "collection_system",
        ):
            try:
                field = model_class._meta.get_field(field_name)
            except FieldDoesNotExist:
                continue
            if field.is_relation and field.many_to_one:
                select_fields.append(field_name)
        return select_fields

    # --- Reference pipeline -------------------------------------------------

    def references(
        self,
        available_models: list[type[UserCreatedObject]],
        limit_per_model: int | None = None,
    ) -> tuple[
        list[ReviewItemReference],
        dict[type[UserCreatedObject], QuerySet[UserCreatedObject]],
    ]:
        """Filter in SQL and sort lightweight references without loading full objects."""
        references = []
        querysets = {}
        selected_model_type_ids = self._selected_model_type_ids()
        active_filters = self._has_active_query_filters()

        for model_class in available_models:
            if not self._matches_selected_model_types(
                model_class, selected_model_type_ids
            ):
                continue
            try:
                queryset = self._scoped_queryset_for_model(model_class)
            except RECOVERABLE_MODEL_ERRORS as exc:
                logger.warning(
                    "Could not build in-review queryset for %s: %s",
                    model_class.__name__,
                    exc,
                )
                continue

            queryset = self._apply_database_review_filters(queryset, model_class)
            querysets[model_class] = queryset
            if not active_filters:
                queryset = queryset.order_by("-submitted_at", "pk")
            try:
                model_class._meta.get_field("name")
                name = "name"
            except FieldDoesNotExist:
                name = Value("", output_field=CharField())
            metadata = queryset.values_list("pk", name, "submitted_at")
            if limit_per_model is not None:
                metadata = metadata[:limit_per_model]
            references.extend(
                ReviewItemReference(model_class, *row) for row in metadata.iterator()
            )

        return self._apply_requested_ordering(references), querysets

    def hydrate(
        self,
        references: Iterable[ReviewItemReference],
        querysets: dict[type[UserCreatedObject], QuerySet[UserCreatedObject]],
    ) -> list[UserCreatedObject]:
        """Load only selected objects, retaining the original visibility filters."""
        ids_by_model = defaultdict(list)
        for reference in references:
            ids_by_model[reference.model].append(reference.pk)
        objects = {}
        for model_class, ids in ids_by_model.items():
            queryset = (
                querysets[model_class]
                .filter(pk__in=ids)
                .select_related(*self._select_related_fields(model_class))
                .order_by()
            )
            objects.update(((model_class, obj.pk), obj) for obj in queryset)
        return [
            objects[(reference.model, reference.pk)]
            for reference in references
            if (reference.model, reference.pk) in objects
        ]

    def collect(
        self, available_models: list[type[UserCreatedObject]] | None = None
    ) -> list[UserCreatedObject]:
        """Return hydrated review items, capping per-model prefetch when unfiltered."""
        if available_models is None:
            available_models = self.available_models()
        limit = (
            None
            if self._has_active_query_filters()
            else self.page_size * max(10, len(available_models))
        )
        references, querysets = self.references(available_models, limit)
        return self.hydrate(references, querysets)
