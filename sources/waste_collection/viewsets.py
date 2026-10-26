import logging
import time

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import connection, transaction
from django.db.models import BigIntegerField, F, Max, Prefetch
from django.db.models.functions import Cast
from django.urls import reverse
from django.utils import timezone
from django_filters import rest_framework as rf_filters
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import (
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

from maps.db_functions import SimplifyPreserveTopology
from maps.mixins import CachedGeoJSONMixin
from maps.models import GeoPolygon
from maps.utils import build_collection_cache_key, row_xmin_subquery
from sources.waste_collection.filters import (
    CollectionExtendedFilterSet,
    CollectionFilterSet,
)
from sources.waste_collection.geojson import exclude_published_predecessors
from sources.waste_collection.importers import CollectionImporter
from sources.waste_collection.models import (
    AggregatedCollectionPropertyValue,
    Collection,
    CollectionCountOptions,
    CollectionFrequency,
    CollectionPropertyValue,
    CollectionSeason,
    Collector,
    WasteFlyer,
)
from sources.waste_collection.serializers import (
    GEOMETRY_SIMPLIFY_TOLERANCE,
    AggregatedCollectionPropertyValueMutationSerializer,
    CollectionAnalysisSerializer,
    CollectionFlatSerializer,
    CollectionFrequencyMutationSerializer,
    CollectionFrequencyReferenceSerializer,
    CollectionImportRecordSerializer,
    CollectionModelSerializer,
    CollectionMutationCreateSerializer,
    CollectionMutationUpdateSerializer,
    CollectionMutationVersionSerializer,
    CollectionPropertyValueMutationSerializer,
    CollectionPropertyValueSerializer,
    CollectionResearchSerializer,
    CollectorGeometrySerializer,
    WasteCollectionGeometrySerializer,
)
from sources.waste_collection.services import flyer_title, resolve_flyer
from utils.object_management.permissions import apply_scope_filter, get_object_policy
from utils.object_management.policy import (
    PUBLIC_READ_STATES,
    decide,
    is_active_actor,
    is_admin,
    visible_queryset,
)
from utils.object_management.services import (
    _fresh_actor,
    _lock_instance,
    authorize_create,
    content_mutation,
    perform_transition,
    record_creation,
    validate_references,
)
from utils.object_management.viewsets import UserCreatedObjectViewSet

logger = logging.getLogger(__name__)


class CollectionDjangoFilterBackend(rf_filters.DjangoFilterBackend):
    """DjangoFilterBackend variant that accepts extra view-provided kwargs."""

    def get_filterset_class(self, view, queryset=None):
        if view._extended_list_requested():
            return CollectionExtendedFilterSet
        return super().get_filterset_class(view, queryset)

    def get_filterset_kwargs(self, request, queryset, view):
        kwargs = super().get_filterset_kwargs(request, queryset, view)
        get_extra_kwargs = getattr(view, "get_filterset_kwargs", None)
        if callable(get_extra_kwargs):
            kwargs.update(get_extra_kwargs())
        return kwargs


class GeoJSONAnonThrottle(AnonRateThrottle):
    """Rate limit for anonymous users on GeoJSON endpoints."""

    rate = "10/minute"


class GeoJSONUserThrottle(UserRateThrottle):
    """Rate limit for authenticated users on GeoJSON endpoints."""

    rate = "60/minute"


class CollectionListPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 200


class CollectionViewSet(CachedGeoJSONMixin, UserCreatedObjectViewSet):
    """Collection viewset that integrates with CachedGeoJSONMixin and UserCreatedObjectViewSet.

    Provides the standard CRUD operations for collections, plus:
    - GeoJSON endpoint with scope-based filtering
    - Review workflow actions (register_for_review, withdraw_from_review, approve, reject)
    - Publication status filtering based on user permissions
    """

    queryset = Collection.objects.all()
    serializer_class = CollectionFlatSerializer
    geojson_serializer_class = WasteCollectionGeometrySerializer
    geojson_geometry_field = "simplified_geom"
    geojson_point_field = "catchment__region__borders__geom"
    filter_backends = (CollectionDjangoFilterBackend,)
    filterset_class = CollectionFilterSet
    pagination_class = CollectionListPagination
    # ``None`` falls back to ``COLLECTION_LIST_SLOW_LOG_THRESHOLD_SECONDS``
    # (default 1.0) so deployments and tests can tune the threshold.
    collection_list_slow_log_threshold_seconds = None
    requires_add_permission_actions = {
        "create_collection",
        "create_new_version",
        "create_collection_property_value",
        "create_aggregated_collection_property_value",
    }

    action_create_models = {
        "create_collection": Collection,
        "create_collection_frequency": CollectionFrequency,
        "create_collection_property_value": CollectionPropertyValue,
        "create_aggregated_collection_property_value": AggregatedCollectionPropertyValue,
    }

    def _slow_log_threshold_seconds(self):
        if self.collection_list_slow_log_threshold_seconds is not None:
            return self.collection_list_slow_log_threshold_seconds
        return getattr(settings, "COLLECTION_LIST_SLOW_LOG_THRESHOLD_SECONDS", 1.0)

    def get_queryset(self):
        if (
            getattr(self, "action", None) == "list"
            and self._extended_list_requested()
            and (self.request.query_params.get("scope") or "").lower() == "all"
        ):
            # On the extended list ``all`` means "all records the actor may
            # see" (CollectionExtendedFilterSet applies the same rule), which
            # is general read authorization, not a named core scope.
            queryset = visible_queryset(self.request.user, self.queryset)
        else:
            queryset = super().get_queryset()
        if getattr(self, "action", None) != "list":
            return queryset

        relation_queryset = Collection.objects.only("pk").order_by("pk")
        queryset = queryset.select_related(
            "owner",
            "catchment",
            "catchment__region",
            "catchment__region__nutsregion",
            "catchment__region__lauregion",
            "collector",
            "collection_system",
            "waste_category",
            "fee_system",
            "frequency",
            "bin_configuration",
        ).prefetch_related(
            "allowed_materials",
            "forbidden_materials",
            "flyers",
            "sources",
            Prefetch(
                "predecessors",
                queryset=relation_queryset,
                to_attr="_prefetched_predecessors",
            ),
            Prefetch(
                "successors",
                queryset=relation_queryset,
                to_attr="_prefetched_successors",
            ),
        )
        if not self._extended_list_requested():
            return queryset
        nuts_ancestry = [
            "catchment__region__nutsregion__parent",
            "catchment__region__nutsregion__parent__parent",
            "catchment__region__nutsregion__parent__parent__parent",
            "catchment__region__lauregion__nuts_parent",
            "catchment__region__lauregion__nuts_parent__parent",
            "catchment__region__lauregion__nuts_parent__parent__parent",
            "catchment__region__lauregion__nuts_parent__parent__parent__parent",
        ]
        return queryset.select_related(*nuts_ancestry).order_by("pk")

    def _version_aggregates(self):
        return {
            **super()._version_aggregates(),
            "max_region_mod": Max("catchment__region__lastmodified_at"),
        }

    def _version_timestamp(self, aggregates):
        timestamp = super()._version_timestamp(aggregates)
        region_modified = aggregates.get("max_region_mod")
        return (
            max(timestamp, int(region_modified.timestamp()))
            if region_modified
            else timestamp
        )

    def get_geojson_queryset(self):
        """Return optimized queryset for GeoJSON with simplified geometry.

        Uses PostGIS ST_SimplifyPreserveTopology to reduce geometry complexity
        while maintaining valid topology. This significantly reduces response
        size and serialization time.
        """
        qs = self.get_queryset().select_related(
            "catchment",
            "catchment__region",
            "catchment__region__borders",
            "waste_category",
            "collection_system",
        )
        # Add simplified geometry annotation
        qs = qs.annotate(
            simplified_geom=SimplifyPreserveTopology(
                F("catchment__region__borders__geom"),
                GEOMETRY_SIMPLIFY_TOLERANCE,
            )
        )
        return qs

    def get_geojson_queryset_with_bbox(self, request):
        """Apply base filtering and hide outdated versions by default on maps.

        Map views should show the latest visible versions by default. Historical
        versions remain available when users explicitly request a point in time
        via ``valid_on`` or ask for specific ``id`` values.
        """
        queryset = super().get_geojson_queryset_with_bbox(request)
        return self._latest_visible_versions_queryset(queryset, request)

    def get_stats_queryset(self, request):
        """Return the count/version row set without the geometry annotation.

        The statistics aggregate only needs the filtered rows; carrying the
        ST_SimplifyPreserveTopology annotation into it would plan or evaluate
        geometry simplification for every matching collection.
        """
        queryset = self.filter_queryset(self.get_queryset())
        queryset = self._apply_id_filter(queryset, request)
        bbox = self._parse_bbox(request)
        if bbox:
            queryset = self._apply_bbox_filter(queryset, bbox)
        return self._latest_visible_versions_queryset(queryset, request)

    def _latest_visible_versions_queryset(self, queryset, request):
        """Return latest visible versions unless an explicit temporal/id filter is set.

        A collection is only considered outdated when a *published* successor exists.
        Using the scope-filtered outer queryset for the subquery would incorrectly
        suppress published collections when their review-status successors appear in
        an unscoped (all-objects) staff view.
        """
        params = request.query_params
        has_id_filter = bool(params.get("id"))
        if hasattr(params, "getlist"):
            has_id_filter = has_id_filter or bool(params.getlist("id"))

        if params.get("valid_on") or has_id_filter:
            return queryset

        return exclude_published_predecessors(queryset)

    def get_serializer_class(self):
        """Use detailed serializer for retrieve so the UI receives ownership and status fields.

        - retrieve -> CollectionModelSerializer (includes owner_id, publication_status, etc.)
        - list     -> CollectionResearchSerializer (research workflow metadata)
        - default  -> self.serializer_class (CollectionFlatSerializer)
        """
        action = getattr(self, "action", None)
        if action == "retrieve":
            return CollectionModelSerializer
        if action == "list":
            if self._extended_list_requested():
                return CollectionAnalysisSerializer
            return CollectionResearchSerializer
        return super().get_serializer_class()

    def _extended_list_requested(self):
        return getattr(self, "action", None) == "list" and (
            self.request.query_params.get("view") == "extended"
        )

    # Ensure CachedGeoJSONMixin uses the GeoJSON serializer class
    def get_geojson_serializer_class(self):
        return WasteCollectionGeometrySerializer

    def get_filterset_kwargs(self):
        """Pass lightweight filter kwargs for API-only actions.

        API endpoints do not render filter widgets, so they can skip
        expensive min/max slider calculations performed during filterset init.
        """
        if getattr(self, "action", None) in {"geojson", "list", "version"}:
            return {"skip_min_max": True}
        return {}

    analysis_group_name = "analysis_api"

    def _enforce_analysis_group(self, request):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            raise NotAuthenticated(
                "Authentication is required for the extended collection list."
            )
        if is_active_actor(user) and (
            is_admin(user) or user.groups.filter(name=self.analysis_group_name).exists()
        ):
            return
        raise PermissionDenied(
            f"Membership in the '{self.analysis_group_name}' group is required "
            "for the extended collection list."
        )

    def _enforce_authenticated_non_public_scope(self, request):
        scope = (request.query_params.get("scope") or "published").lower()
        # ``archived`` is public historical data, not a privileged scope.
        if scope in PUBLIC_READ_STATES:
            return

        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            raise NotAuthenticated(
                f"Authentication is required to access the '{scope}' scope."
            )

    def list(self, request, *args, **kwargs):
        if "view" in request.query_params and not self._extended_list_requested():
            raise ValidationError({"view": "Use 'extended' or omit this parameter."})
        if self._extended_list_requested():
            self._enforce_analysis_group(request)
        self._enforce_authenticated_non_public_scope(request)
        started_at = time.perf_counter()
        query_count_start = (
            len(connection.queries)
            if getattr(connection, "queries_logged", False)
            else None
        )

        response = super().list(request, *args, **kwargs)

        if self._extended_list_requested():
            response.data.update(
                schema_version="1.0",
                generated_at=timezone.now().isoformat(),
                snapshot_isolation=False,
            )
            response["Cache-Control"] = "private, no-store"

        duration_seconds = time.perf_counter() - started_at
        if duration_seconds >= self._slow_log_threshold_seconds():
            data = response.data
            result_count = None
            total_count = None
            if isinstance(data, dict):
                total_count = data.get("count")
                results = data.get("results")
                if results is not None:
                    result_count = len(results)
            elif isinstance(data, list):
                result_count = len(data)

            query_count = None
            if query_count_start is not None:
                query_count = len(connection.queries) - query_count_start

            page_size = getattr(getattr(self, "paginator", None), "page_size", None)
            logger.warning(
                "slow_collection_list_api action=%s result_count=%s total_count=%s page_size=%s serializer=%s duration_ms=%.1f query_count=%s",
                getattr(self, "action", None),
                result_count,
                total_count,
                page_size,
                self.get_serializer_class().__name__,
                duration_seconds * 1000,
                query_count,
                extra={
                    "action": getattr(self, "action", None),
                    "result_count": result_count,
                    "total_count": total_count,
                    "page_size": page_size,
                    "serializer": self.get_serializer_class().__name__,
                    "duration_ms": duration_seconds * 1000,
                    "query_count": query_count,
                },
            )
        return response

    def get_cache_key(self, request):
        """Build a deterministic cache key including filters and dataset version.

        Uses the shared build_collection_cache_key utility to ensure consistency
        with cache warm-up tasks.

        Format examples:
        - collection_geojson:id:1,2,3:dv:abc123def456
        - collection_geojson:filter:<hash>:dv:abc123def456
        """
        params = request.query_params
        scope = (params.get("scope") or "published").lower()
        user = getattr(request, "user", None)

        # Extract ID list if present
        id_list = params.getlist("id") if hasattr(params, "getlist") else []

        # Build filter dict, excluding transient or non-data keys
        # `scope` is already encoded in dataset version (`dv`) via build_collection_cache_key.
        # Excluding it here avoids duplicate cache key variants for equivalent published requests.
        exclude_keys = {"csrfmiddlewaretoken", "page", "next", "dv", "scope"}
        filters = {}
        for key in params.keys():
            if key in exclude_keys:
                continue
            values = (
                params.getlist(key) if hasattr(params, "getlist") else [params.get(key)]
            )
            # Normalize singletons to string, multi-values to list
            if len(values) == 1:
                filters[key] = values[0]
            elif len(values) > 1:
                filters[key] = sorted(values)

        return build_collection_cache_key(
            scope=scope,
            user=user,
            filters=filters if filters else None,
            id_list=id_list if id_list else None,
        )

    @staticmethod
    def _require_authenticated_actor(request):
        actor = getattr(request, "user", None)
        if actor is None or not actor.is_authenticated:
            raise PermissionDenied("Authentication is required for this action.")
        return actor

    @classmethod
    def _require_create_capability(cls, actor, action_name, *, parent=None):
        model = cls.action_create_models[action_name]
        decision = decide(actor, "create", model, parent=parent)
        if not decision.allowed:
            raise PermissionDenied(
                f"You do not have permission to add {model._meta.verbose_name}."
            )

    @staticmethod
    def _require_can_add_property(request, collection):
        policy = get_object_policy(
            getattr(request, "user", None), collection, request=request
        )
        if policy.get("can_add_property"):
            return

        raise PermissionDenied(
            "You do not have permission to add statistics to this collection."
        )

    @staticmethod
    def _flyer_title(url):
        """Return a short title derived from the URL hostname (max 255 chars)."""
        return flyer_title(url)

    @staticmethod
    def _attach_sources_and_flyers(
        collection,
        sources=None,
        flyer_urls=None,
        *,
        replace_sources=False,
        replace_flyers=False,
        actor,
    ):
        """Attach bibliography sources and flyer URLs to ``collection``.

        Every submitted source must be readable by the acting user; flyer
        URLs resolve through the shared flyer service, which enforces read
        access on existing rows and create capability plus actor ownership
        on new rows.
        """
        if sources is not None:
            sources = list(sources)
        if flyer_urls is not None:
            flyer_urls = list(flyer_urls)

        if sources:
            validate_references(actor, list(sources))
        if sources is not None:
            if replace_sources:
                collection.sources.set(sources)
            elif sources:
                collection.sources.add(*sources)

        flyers = []
        for url in flyer_urls or []:
            if len(url) > 2083:
                continue
            flyer, _created = resolve_flyer(actor, url)
            flyers.append(flyer)

        if flyer_urls is not None:
            if replace_flyers:
                collection.flyers.set(flyers)
            else:
                collection.flyers.add(*flyers)

    @staticmethod
    def _attach_sources_and_flyers_to_property_value(obj, sources, flyer_urls):
        if sources:
            obj.sources.add(*sources)

        for url in flyer_urls:
            if len(url) > 2083:
                continue

            flyer, _ = WasteFlyer.objects.get_or_create_by_url(
                url=url,
                defaults={
                    "owner": obj.owner,
                    "title": CollectionViewSet._flyer_title(url),
                    "publication_status": "private",
                },
            )
            obj.sources.add(flyer)

    def _submit_for_review_if_requested(self, request, collection, submit_for_review):
        """Submit ``collection`` for review through the transition service."""
        if not submit_for_review:
            return False

        try:
            perform_transition(request.user, collection, "submit")
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict or exc.messages) from exc
        collection.refresh_from_db()
        return True

    def _submit_object_for_review_if_requested(self, request, obj, submit_for_review):
        if not submit_for_review:
            return False

        try:
            perform_transition(request.user, obj, "submit")
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict or exc.messages) from exc
        obj.refresh_from_db()
        return True

    @staticmethod
    def _serialize_mutation_response(collection, submitted):
        """Build a consistent response payload for mutation endpoints."""
        content_type_id = ContentType.objects.get_for_model(collection.__class__).id
        return {
            "id": collection.pk,
            "content_type_id": content_type_id,
            "object_id": collection.pk,
            "publication_status": collection.publication_status,
            "submitted": submitted,
            "review_detail_url": reverse(
                "object_management:review_item_detail",
                kwargs={
                    "content_type_id": content_type_id,
                    "object_id": collection.pk,
                },
            ),
            "detail_url": reverse(
                "collection-detail",
                kwargs={"pk": collection.pk},
            ),
        }

    @staticmethod
    def _serialize_user_created_object_response(obj, submitted, *, detail_url_name):
        content_type_id = ContentType.objects.get_for_model(obj.__class__).id
        return {
            "id": obj.pk,
            "content_type_id": content_type_id,
            "object_id": obj.pk,
            "publication_status": obj.publication_status,
            "submitted": submitted,
            "review_detail_url": reverse(
                "object_management:review_item_detail",
                kwargs={
                    "content_type_id": content_type_id,
                    "object_id": obj.pk,
                },
            ),
            "detail_url": reverse(detail_url_name, kwargs={"pk": obj.pk}),
        }

    @staticmethod
    def _collection_identity_mismatches(collection, data):
        mismatches = {}

        actual_waste_category = collection.effective_waste_category
        identity_pairs = {
            "catchment": {
                "actual": str(collection.catchment),
                "actual_id": getattr(collection.catchment, "pk", None),
                "expected": data.get("expected_catchment"),
                "expected_id": data.get("expected_catchment_id"),
            },
            "waste_category": {
                "actual": str(actual_waste_category) if actual_waste_category else "",
                "actual_id": getattr(actual_waste_category, "pk", None),
                "expected": data.get("expected_waste_category"),
                "expected_id": data.get("expected_waste_category_id"),
            },
            "collection_system": {
                "actual": str(collection.collection_system),
                "actual_id": getattr(collection.collection_system, "pk", None),
                "expected": data.get("expected_collection_system"),
                "expected_id": data.get("expected_collection_system_id"),
            },
        }

        for field_name, values in identity_pairs.items():
            expected_values = set()
            if values["expected"] not in {None, ""}:
                expected_values.add(str(values["expected"]))
            if values["expected_id"] is not None:
                expected_values.add(str(values["expected_id"]))

            actual_values = {values["actual"]}
            if values["actual_id"] is not None:
                actual_values.add(str(values["actual_id"]))

            if expected_values.isdisjoint(actual_values):
                mismatches[field_name] = {
                    "actual": values["actual"],
                    "actual_id": values["actual_id"],
                    "expected": values["expected"],
                    "expected_id": values["expected_id"],
                }

        expected_pairs = {
            "publication_status": (
                collection.publication_status,
                data["expected_publication_status"],
            ),
            "valid_from": (
                collection.valid_from.isoformat() if collection.valid_from else None,
                data["expected_valid_from"].isoformat(),
            ),
        }

        for field_name, (actual_value, expected_value) in expected_pairs.items():
            if actual_value != expected_value:
                mismatches[field_name] = {
                    "actual": actual_value,
                    "expected": expected_value,
                }

        return mismatches

    @staticmethod
    def _apply_collection_mutation_update(collection, data, actor):
        scalar_fields = (
            "collector",
            "frequency",
            "fee_system",
            "bin_configuration",
            "established",
            "participation_policy",
            "min_bin_size",
            "required_bin_capacity",
            "required_bin_capacity_reference",
            "access_control_bp",
            "access_control_pap",
            "description",
        )
        touched_scalar_fields = []
        for field_name in scalar_fields:
            if field_name not in data:
                continue
            setattr(collection, field_name, data[field_name])
            touched_scalar_fields.append(field_name)

        if touched_scalar_fields:
            collection.save(update_fields=[*touched_scalar_fields, "lastmodified_at"])
        else:
            collection.save()

        if "allowed_materials" in data:
            collection.allowed_materials.set(list(data["allowed_materials"]))
        if "forbidden_materials" in data:
            collection.forbidden_materials.set(list(data["forbidden_materials"]))
        if "sources" in data or "flyer_urls" in data:
            CollectionViewSet._attach_sources_and_flyers(
                collection,
                sources=data.get("sources") if "sources" in data else None,
                flyer_urls=data.get("flyer_urls") if "flyer_urls" in data else None,
                replace_sources="sources" in data,
                replace_flyers=data.get("replace_flyer_urls", False),
                actor=actor,
            )

    @staticmethod
    def _visible_summary_queryset(request):
        queryset = Collection.objects.all()
        return apply_scope_filter(
            queryset,
            request.query_params.get("scope"),
            user=getattr(request, "user", None),
        )

    @staticmethod
    def _visible_frequency_queryset(request):
        queryset = CollectionFrequency.objects.all()
        return apply_scope_filter(
            queryset,
            request.query_params.get("scope", "published"),
            user=getattr(request, "user", None),
        )

    @staticmethod
    def _visible_property_value_queryset(request):
        queryset = CollectionPropertyValue.objects.all()
        return apply_scope_filter(
            queryset,
            request.query_params.get("scope", "published"),
            user=getattr(request, "user", None),
        )

    def _resolve_frequency_season(self, actor, row):
        """Return ``(season, created)`` for ``row`` under its own policy.

        An existing season only needs read authorization; a new season needs
        the independent ``add_collectionseason`` capability, stays private
        and is owned by the acting user. A season won by a concurrent
        inserter falls back to its read authorization, not to a creation
        audit.
        """
        season = CollectionSeason.objects.filter(
            distribution=row["distribution"],
            first_timestep=row["first_timestep"],
            last_timestep=row["last_timestep"],
        ).first()
        if season is not None:
            validate_references(actor, season)
            return season, False
        actor = authorize_create(actor, CollectionSeason)
        season, created = CollectionSeason.objects.get_or_create(
            distribution=row["distribution"],
            first_timestep=row["first_timestep"],
            last_timestep=row["last_timestep"],
            defaults={
                "owner": actor,
                "publication_status": CollectionSeason.STATUS_PRIVATE,
            },
        )
        if not created:
            validate_references(actor, season)
        return season, created

    def _create_collection_frequency(self, actor, data):
        frequency = CollectionFrequency.objects.create(
            owner=actor,
            publication_status=CollectionFrequency.STATUS_PRIVATE,
            name=data["canonical_name"],
            type=data["frequency_type"],
            description=data.get("description", ""),
        )
        count_options = []
        created_seasons = {}
        for row in data.get("rows", []):
            validate_references(
                actor,
                [
                    row["distribution"],
                    row["first_timestep"],
                    row["last_timestep"],
                ],
            )
            season, season_created = self._resolve_frequency_season(actor, row)
            if season_created:
                created_seasons.setdefault(season.pk, season)
            actor = authorize_create(actor, CollectionCountOptions)
            count_options_row = CollectionCountOptions.objects.create(
                frequency=frequency,
                season=season,
                standard=row.get("standard"),
                option_1=row.get("option_1"),
                option_2=row.get("option_2"),
                option_3=row.get("option_3"),
                owner=actor,
                publication_status=CollectionCountOptions.STATUS_PRIVATE,
            )
            count_options.append(count_options_row)
        return frequency, count_options, list(created_seasons.values())

    @staticmethod
    def _submittable_frequency_rows(actor, frequency):
        return list(
            CollectionCountOptions.objects.filter(
                frequency=frequency,
                owner=actor,
                publication_status__in=(
                    CollectionCountOptions.STATUS_PRIVATE,
                    getattr(CollectionCountOptions, "STATUS_DECLINED", "declined"),
                ),
            ).order_by("pk")
        )

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated],
        url_path="frequency/create",
        url_name="frequency-create",
    )
    def create_collection_frequency(self, request, *args, **kwargs):
        actor = self._require_authenticated_actor(request)
        self._require_create_capability(actor, "create_collection_frequency")

        serializer = CollectionFrequencyMutationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            actor = _fresh_actor(request.user)
            actor = authorize_create(actor, CollectionFrequency)
            frequency = visible_queryset(
                actor,
                CollectionFrequency.objects.filter(
                    name__iexact=data["canonical_name"]
                ).order_by("pk"),
            ).first()
            created = frequency is None
            count_options = []
            created_seasons = []
            if created:
                frequency, count_options, created_seasons = (
                    self._create_collection_frequency(actor, data)
                )
                actor = _fresh_actor(request.user)
                actor = authorize_create(actor, CollectionFrequency)
                for row in data.get("rows", []):
                    validate_references(
                        actor,
                        [
                            row["distribution"],
                            row["first_timestep"],
                            row["last_timestep"],
                        ],
                    )
                validate_references(
                    actor,
                    [row_obj.season for row_obj in count_options],
                )
                for _count_options_row in count_options:
                    actor = authorize_create(actor, CollectionCountOptions)
                for _season in created_seasons:
                    actor = authorize_create(actor, CollectionSeason)
                record_creation(actor, frequency)
                for season in created_seasons:
                    record_creation(actor, season)
                for count_options_row in count_options:
                    record_creation(actor, count_options_row)
            else:
                frequency = _lock_instance(frequency)
                actor = _fresh_actor(request.user)
                actor = authorize_create(actor, CollectionFrequency)
                if not decide(actor, "read", frequency).allowed:
                    raise PermissionDenied(
                        "You do not have permission to inspect this frequency."
                    )
                count_options = self._submittable_frequency_rows(actor, frequency)

            submitted = False
            if data.get("submit_for_review", True):
                for count_options_row in count_options:
                    self._submit_object_for_review_if_requested(
                        request,
                        count_options_row,
                        submit_for_review=True,
                    )
                submitted = self._submit_object_for_review_if_requested(
                    request,
                    frequency,
                    submit_for_review=(
                        created
                        or frequency.publication_status
                        in {frequency.STATUS_PRIVATE, frequency.STATUS_DECLINED}
                    ),
                )

        return Response(
            {
                **self._serialize_user_created_object_response(
                    frequency,
                    submitted,
                    detail_url_name="collectionfrequency-detail",
                ),
                "created": created,
                "name": frequency.name,
                "type": frequency.type,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated],
        url_path="update",
        url_name="update",
    )
    def update_collection(self, request, pk=None):
        actor = self._require_authenticated_actor(request)
        collection = self.get_object()

        serializer = CollectionMutationUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            with content_mutation(actor, collection, action="edit") as locked:
                mismatches = self._collection_identity_mismatches(locked, data)
                if mismatches:
                    return Response(
                        {
                            "detail": "Target collection no longer matches the expected identity.",
                            "mismatches": mismatches,
                        },
                        status=status.HTTP_409_CONFLICT,
                    )
                actor = _fresh_actor(request.user)
                validate_references(actor, data)
                self._apply_collection_mutation_update(locked, data, actor)
        except DjangoValidationError as exc:
            raise ValidationError(
                getattr(exc, "message_dict", None) or exc.messages
            ) from exc

        response_payload = {
            **self._serialize_mutation_response(locked, False),
            "updated": True,
        }

        return Response(
            response_payload,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated],
        url_path="update_collection",
        url_name="update-collection",
    )
    def update_collection_legacy(self, request, pk=None):
        return self.update_collection(request, pk=pk)

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[permissions.AllowAny],
        url_path="property-value",
        url_name="property-value-list",
    )
    def property_values(self, request, *args, **kwargs):
        """List CollectionPropertyValue records, optionally filtered by collection."""
        self.check_permissions(request)
        self._enforce_authenticated_non_public_scope(request)
        queryset = self._visible_property_value_queryset(request)

        collection_id = request.query_params.get("collection")
        if collection_id is not None:
            queryset = queryset.filter(collection_id=collection_id)

        try:
            limit = int(request.query_params.get("limit", 50))
        except (TypeError, ValueError):
            limit = 50
        limit = max(1, min(limit, 200))

        serializer = CollectionPropertyValueSerializer(
            queryset.select_related("property", "unit").order_by("pk")[:limit],
            many=True,
        )
        return Response({"results": serializer.data})

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated],
        url_path="property-value/create",
        url_name="property-value-create",
    )
    def create_collection_property_value(self, request, *args, **kwargs):
        actor = self._require_authenticated_actor(request)
        self._require_create_capability(actor, "create_collection_property_value")

        serializer = CollectionPropertyValueMutationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        target_collection = data["collection"]
        self._require_can_add_property(request, target_collection)
        anchor_collection = target_collection.version_anchor or target_collection

        with transaction.atomic():
            importer = CollectionImporter(
                owner=actor,
                publication_status=(
                    "review" if data.get("submit_for_review", True) else "private"
                ),
            )
            importer._load_lookups()
            prop = importer._properties.get(data["property_id"])
            unit = importer._units.get(data["unit_name"])
            if prop is None:
                return Response(
                    {"detail": f"Property id={data['property_id']} not found."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if unit is None:
                return Response(
                    {"detail": f"Unit '{data['unit_name']}' not found."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            existing_cpv = (
                CollectionPropertyValue.objects.filter(
                    collection=anchor_collection,
                    property=prop,
                    unit=unit,
                    year=data["year"],
                )
                .order_by("pk")
                .first()
            )

            cpv_stats = {
                "cpv_created": 0,
                "cpv_unchanged": 0,
                "cpv_skipped": 0,
                "flyers_created": 0,
                "warnings": [],
            }
            importer._import_property_value(
                anchor_collection,
                {
                    "property_id": data["property_id"],
                    "unit_name": data["unit_name"],
                    "year": data["year"],
                    "average": data["average"],
                    "standard_deviation": data.get("standard_deviation"),
                    "flyer_urls": data.get("flyer_urls", []),
                },
                cpv_stats,
                record={},
            )

            cpv = (
                existing_cpv
                or CollectionPropertyValue.objects.filter(
                    collection=anchor_collection,
                    property=prop,
                    unit=unit,
                    year=data["year"],
                    owner=actor,
                )
                .order_by("-pk")
                .first()
            )
            if cpv is None:
                return Response(
                    {"detail": "CollectionPropertyValue could not be created."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            self._attach_sources_and_flyers_to_property_value(
                cpv,
                sources=data.get("sources", []),
                flyer_urls=[],
            )
            submitted = bool(
                data.get("submit_for_review", True)
                and cpv.publication_status == cpv.STATUS_REVIEW
            )

        response_payload = self._serialize_user_created_object_response(
            cpv,
            submitted,
            detail_url_name="collectionpropertyvalue-detail",
        )
        response_payload.update(cpv_stats)
        response_payload.update(
            {
                "collection_id": target_collection.pk,
                "anchor_collection_id": anchor_collection.pk,
                "is_derived": cpv.is_derived,
            }
        )
        return Response(response_payload, status=status.HTTP_201_CREATED)

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated],
        url_path="aggregated-property-value/create",
        url_name="aggregated-property-value-create",
    )
    def create_aggregated_collection_property_value(self, request, *args, **kwargs):
        actor = self._require_authenticated_actor(request)
        self._require_create_capability(
            actor, "create_aggregated_collection_property_value"
        )

        serializer = AggregatedCollectionPropertyValueMutationSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        collections = list(data["collections"])
        if not collections:
            return Response(
                {"detail": "At least one collection is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        for collection in collections:
            self._require_can_add_property(request, collection)

        importer = CollectionImporter(
            owner=actor,
            publication_status=(
                "review" if data.get("submit_for_review", True) else "private"
            ),
        )
        importer._load_lookups()
        prop = importer._properties.get(data["property_id"])
        unit = importer._units.get(data["unit_name"])
        if prop is None:
            return Response(
                {"detail": f"Property id={data['property_id']} not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if unit is None:
            return Response(
                {"detail": f"Unit '{data['unit_name']}' not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        requested_collection_ids = sorted(collection.pk for collection in collections)

        with transaction.atomic():
            # The dedup key spans the collections M2M, so no unique constraint
            # can enforce it; serialize find-or-create per owner instead.
            get_user_model().objects.select_for_update().filter(pk=actor.pk).exists()
            existing_acpv = None
            for candidate in AggregatedCollectionPropertyValue.objects.filter(
                owner=actor,
                property=prop,
                unit=unit,
                year=data["year"],
            ).prefetch_related("collections"):
                candidate_ids = sorted(
                    collection.pk for collection in candidate.collections.all()
                )
                if candidate_ids == requested_collection_ids:
                    existing_acpv = candidate
                    break

            if existing_acpv is None:
                acpv = AggregatedCollectionPropertyValue.objects.create(
                    name=f"Aggregated {prop.name} {data['year']}",
                    owner=actor,
                    publication_status="private",
                    property=prop,
                    unit=unit,
                    year=data["year"],
                    average=data["average"],
                    standard_deviation=data.get("standard_deviation"),
                )
                acpv.collections.set(collections)
                created = True
            else:
                acpv = existing_acpv
                created = False

            self._attach_sources_and_flyers_to_property_value(
                acpv,
                sources=data.get("sources", []),
                flyer_urls=data.get("flyer_urls", []),
            )
            submitted = self._submit_object_for_review_if_requested(
                request,
                acpv,
                submit_for_review=data.get("submit_for_review", True),
            )

        response_payload = self._serialize_user_created_object_response(
            acpv,
            submitted,
            detail_url_name="aggregatedcollectionpropertyvalue-detail",
        )
        response_payload.update(
            {
                "created": created,
                "skipped": not created,
                "collection_ids": requested_collection_ids,
            }
        )
        return Response(response_payload, status=status.HTTP_201_CREATED)

    @action(
        detail=False,
        methods=["post"],
        url_path="create",
        url_name="create",
    )
    def create_collection(self, request, *args, **kwargs):
        """Create a collection from a programmatic payload and optionally submit it."""
        actor = self._require_authenticated_actor(request)
        self._require_create_capability(actor, "create_collection")
        serializer = CollectionMutationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        allowed_materials = list(data.get("allowed_materials", []))
        forbidden_materials = list(data.get("forbidden_materials", []))

        with transaction.atomic():
            actor = _fresh_actor(request.user)
            actor = authorize_create(actor, Collection)
            validate_references(actor, data)
            collection = Collection.objects.create(
                name="",
                owner=actor,
                publication_status=Collection.STATUS_PRIVATE,
                catchment=data["catchment"],
                collector=data.get("collector"),
                collection_system=data["collection_system"],
                waste_category=data["waste_category"],
                frequency=data.get("frequency"),
                fee_system=data.get("fee_system"),
                bin_configuration=data.get("bin_configuration"),
                established=data.get("established"),
                valid_from=data["valid_from"],
                valid_until=data.get("valid_until"),
                participation_policy=data.get("participation_policy"),
                min_bin_size=data.get("min_bin_size"),
                required_bin_capacity=data.get("required_bin_capacity"),
                required_bin_capacity_reference=data.get(
                    "required_bin_capacity_reference"
                ),
                description=data.get("description", ""),
                access_control_bp=data.get("access_control_bp"),
                access_control_pap=data.get("access_control_pap"),
            )
            if allowed_materials:
                collection.allowed_materials.set(allowed_materials)
            if forbidden_materials:
                collection.forbidden_materials.set(forbidden_materials)

            self._attach_sources_and_flyers(
                collection,
                sources=data.get("sources", []),
                flyer_urls=data.get("flyer_urls", []),
                actor=actor,
            )
            actor = _fresh_actor(request.user)
            actor = authorize_create(actor, Collection)
            validate_references(actor, data)
            validate_references(
                actor,
                list(collection.sources.all()) + list(collection.flyers.all()),
            )
            record_creation(actor, collection)
            submitted = self._submit_for_review_if_requested(
                request,
                collection,
                submit_for_review=data.get("submit_for_review", True),
            )

        response_payload = self._serialize_mutation_response(collection, submitted)

        return Response(
            response_payload,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="new-version",
        url_name="new-version",
    )
    def create_new_version(self, request, pk=None):
        """Create a new collection version from an existing predecessor."""
        actor = self._require_authenticated_actor(request)
        predecessor = Collection.objects.filter(pk=pk).first()

        with transaction.atomic():
            if predecessor is None:
                return Response(status=status.HTTP_404_NOT_FOUND)
            predecessor = _lock_instance(predecessor)
            actor = _fresh_actor(request.user)
            if not decide(actor, "read", predecessor).allowed:
                return Response(status=status.HTTP_404_NOT_FOUND)
            decision = decide(actor, "new_version", predecessor)
            if not decision.allowed:
                raise PermissionDenied(
                    "You do not have permission to create a new version of this collection."
                )

            serializer = CollectionMutationVersionSerializer(
                data=request.data,
                context={"predecessor": predecessor},
            )
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data

            waste_category = data.get(
                "waste_category",
                predecessor.effective_waste_category,
            )
            if waste_category is None:
                return Response(
                    {
                        "detail": "waste_category is required when the predecessor has no waste_category."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            allowed_materials = list(
                data.get(
                    "allowed_materials",
                    predecessor.effective_allowed_materials,
                )
            )
            forbidden_materials = list(
                data.get(
                    "forbidden_materials",
                    predecessor.effective_forbidden_materials,
                )
            )
            resolved = {
                "catchment": data.get("catchment", predecessor.catchment),
                "collector": data.get("collector", predecessor.collector),
                "collection_system": data.get(
                    "collection_system", predecessor.collection_system
                ),
                "waste_category": waste_category,
                "frequency": data.get("frequency", predecessor.frequency),
                "fee_system": data.get("fee_system", predecessor.fee_system),
                "bin_configuration": data.get(
                    "bin_configuration", predecessor.bin_configuration
                ),
                "allowed_materials": allowed_materials,
                "forbidden_materials": forbidden_materials,
            }
            if "sources" in data:
                resolved["sources"] = list(data["sources"])
            if "flyer_urls" in data:
                resolved["flyer_urls"] = list(data["flyer_urls"])
            validate_references(actor, resolved)
            actor = authorize_create(actor, Collection)

            collection = Collection.objects.create(
                name="",
                owner=actor,
                publication_status=Collection.STATUS_PRIVATE,
                catchment=resolved["catchment"],
                collector=resolved["collector"],
                collection_system=resolved["collection_system"],
                waste_category=resolved["waste_category"],
                frequency=resolved["frequency"],
                fee_system=resolved["fee_system"],
                bin_configuration=resolved["bin_configuration"],
                established=data.get("established", predecessor.established),
                valid_from=data["valid_from"],
                valid_until=data.get("valid_until"),
                participation_policy=data.get(
                    "participation_policy", predecessor.participation_policy
                ),
                min_bin_size=data.get("min_bin_size", predecessor.min_bin_size),
                required_bin_capacity=data.get(
                    "required_bin_capacity",
                    predecessor.required_bin_capacity,
                ),
                required_bin_capacity_reference=data.get(
                    "required_bin_capacity_reference",
                    predecessor.required_bin_capacity_reference,
                ),
                description=data.get("description", predecessor.description or ""),
                access_control_bp=data.get(
                    "access_control_bp", predecessor.access_control_bp
                ),
                access_control_pap=data.get(
                    "access_control_pap", predecessor.access_control_pap
                ),
            )
            collection.allowed_materials.set(resolved["allowed_materials"])
            collection.forbidden_materials.set(resolved["forbidden_materials"])
            collection.add_predecessor(predecessor)

            default_sources = [
                source
                for source in predecessor.sources.all()
                if decide(actor, "read", source).allowed
            ]
            default_flyer_urls = [
                flyer.url
                for flyer in predecessor.flyers.exclude(url__isnull=True).exclude(
                    url=""
                )
                if decide(actor, "read", flyer).allowed
            ]
            self._attach_sources_and_flyers(
                collection,
                sources=data.get("sources", default_sources),
                flyer_urls=data.get("flyer_urls", default_flyer_urls),
                actor=actor,
            )
            actor = _fresh_actor(request.user)
            actor = authorize_create(actor, Collection)
            if not decide(actor, "read", predecessor).allowed:
                raise NotFound()
            if not decide(actor, "new_version", predecessor).allowed:
                raise PermissionDenied(
                    "You do not have permission to create a new version of this collection."
                )
            validate_references(actor, resolved)
            validate_references(
                actor,
                list(collection.sources.all()) + list(collection.flyers.all()),
            )
            record_creation(actor, collection)
            submitted = self._submit_for_review_if_requested(
                request,
                collection,
                submit_for_review=data.get("submit_for_review", True),
            )

        response_payload = {
            **self._serialize_mutation_response(collection, submitted),
            "predecessor_id": predecessor.pk,
        }

        return Response(
            response_payload,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated],
        url_path="import",
    )
    def bulk_import(self, request, *args, **kwargs):
        """Bulk-import waste collection records from a JSON array.

        Accepts a JSON body with a top-level ``records`` list.  Each element
        follows the ``CollectionImportRecordSerializer`` schema.

        Optional top-level fields:

        - ``dry_run`` (bool, default false) – validate and report without writing.
        - ``publication_status`` (str, default ``"private"``) – status to assign
          to newly created records.

        Returns a summary dict with created/skipped counts and any warnings.

        Only users holding the ``create`` capability for ``Collection`` (and
        ``Collector`` when ``create_collectors`` is set) may call this
        endpoint.
        """
        if not decide(request.user, "create", Collection).allowed:
            return Response(
                {"detail": "You may not create collection records."},
                status=status.HTTP_403_FORBIDDEN,
            )

        payload = request.data
        if not isinstance(payload, dict):
            return Response(
                {"detail": "Request body must be a JSON object."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        records_raw = payload.get("records")
        if not isinstance(records_raw, list):
            return Response(
                {"detail": "'records' must be a JSON array."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        dry_run = payload.get("dry_run", False)
        if not isinstance(dry_run, bool):
            return Response(
                {"detail": "'dry_run' must be a boolean."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        create_collectors = payload.get("create_collectors", False)
        if not isinstance(create_collectors, bool):
            return Response(
                {"detail": "'create_collectors' must be a boolean."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if create_collectors and not decide(request.user, "create", Collector).allowed:
            return Response(
                {"detail": "You may not create collector records."},
                status=status.HTTP_403_FORBIDDEN,
            )

        pub_status = payload.get("publication_status", "private")
        valid_statuses = ("private", "review")
        if pub_status not in valid_statuses:
            return Response(
                {"detail": f"'publication_status' must be one of {valid_statuses}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate all records up-front; collect per-record errors
        serializer = CollectionImportRecordSerializer(data=records_raw, many=True)
        if not serializer.is_valid():
            return Response(
                {"detail": "Validation failed.", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        importer = CollectionImporter(
            owner=request.user,
            publication_status=pub_status,
            create_collectors=create_collectors,
        )
        stats = importer.run(serializer.validated_data, dry_run=dry_run)

        http_status = status.HTTP_200_OK if dry_run else status.HTTP_201_CREATED
        return Response({"dry_run": dry_run, "stats": stats}, status=http_status)

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny])
    def summaries(self, request, *args, **kwargs):
        self.check_permissions(request)
        self._enforce_authenticated_non_public_scope(request)
        queryset = self._visible_summary_queryset(request).filter(
            id__in=request.query_params.getlist("id")
        )
        serializer = CollectionModelSerializer(
            queryset,
            many=True,
            field_labels_as_keys=True,
            context={"request": request},
        )
        return Response({"summaries": serializer.data})

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny])
    def frequencies(self, request, *args, **kwargs):
        self.check_permissions(request)
        self._enforce_authenticated_non_public_scope(request)
        queryset = self._visible_frequency_queryset(request)

        exact_name = str(request.query_params.get("exact_name") or "").strip()
        query = str(request.query_params.get("query") or "").strip()
        if exact_name:
            queryset = queryset.filter(name__iexact=exact_name)
        elif query:
            queryset = queryset.filter(name__icontains=query)

        try:
            limit = int(request.query_params.get("limit", 50))
        except (TypeError, ValueError):
            limit = 50
        limit = max(1, min(limit, 200))

        serializer = CollectionFrequencyReferenceSerializer(
            queryset.order_by("name")[:limit],
            many=True,
        )
        return Response({"results": serializer.data})

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[permissions.AllowAny],
        throttle_classes=[GeoJSONAnonThrottle, GeoJSONUserThrottle],
    )
    def geojson(self, request, *args, **kwargs):
        """GeoJSON endpoint with optimized geometry and rate limiting.

        Uses simplified geometry to reduce payload size and improve performance.
        Rate limited to prevent abuse and protect against crawler overload.
        """
        self._enforce_authenticated_non_public_scope(request)
        return super().geojson(request, *args, **kwargs)


class CollectorViewSet(CachedGeoJSONMixin, viewsets.ReadOnlyModelViewSet):
    """
    Collector viewset with GeoJSON endpoint for QGIS map rendering.

    Provides collectors with their catchment geometries and organizational levels.
    Optimized for QGIS with caching and efficient queries.
    """

    queryset = Collector.objects.all()
    serializer_class = CollectorGeometrySerializer
    permission_classes = [permissions.AllowAny]
    filterset_fields = ["id", "catchment__region__country"]
    # ``Collector.geom`` is a property over the catchment's region borders;
    # the rendered path needs the underlying database field path.
    geojson_geometry_field = "catchment__region__borders__geom"

    def get_queryset(self):
        """
        Optimized queryset with select_related for geometry access.
        Fetches all necessary relations in a single query.
        """
        qs = super().get_queryset()
        qs = qs.select_related(
            "catchment",
            "catchment__region",
            "catchment__region__borders",
            # Reverse one-to-one subtype links read by the serializer on every
            # feature: select_related keeps them joined even though the
            # rendered streaming path clears prefetches.
            "catchment__region__nutsregion",
            "catchment__region__lauregion",
        )

        # Filter by country if specified
        country = self.request.query_params.get("country")
        if country:
            qs = qs.filter(catchment__region__country=country)

        # Only include collectors with geometry
        qs = qs.filter(
            catchment__isnull=False,
            catchment__region__isnull=False,
            catchment__region__borders__isnull=False,
        )

        return qs

    def _version_aggregates(self):
        """Collector responses depend on the linked catchment, its region and
        the region's border polygon.

        GeoPolygon carries no modification timestamp, so the newest borders
        transaction id (xmin) stands in for it — inserts, in-place edits and
        reimports all advance xmin.
        """
        return {
            **super()._version_aggregates(),
            "max_catchment_mod": Max("catchment__lastmodified_at"),
            "max_region_mod": Max("catchment__region__lastmodified_at"),
            "max_borders_xmin": Max(
                Cast(
                    row_xmin_subquery(GeoPolygon, "catchment__region__borders_id"),
                    output_field=BigIntegerField(),
                )
            ),
        }

    def _version_timestamp(self, aggregates):
        """Fingerprint combining every version input as its own segment.

        The inputs are incomparable units (epoch seconds vs. transaction
        ids), so taking a max would let whichever unit is numerically
        largest dominate and silently drop changes in the others.
        """
        parts = [str(super()._version_timestamp(aggregates))]
        for key in ("max_catchment_mod", "max_region_mod"):
            modified = aggregates.get(key)
            parts.append(modified.isoformat() if modified else "")
        parts.append(str(aggregates.get("max_borders_xmin") or 0))
        return ":".join(parts)

    def get_cache_key(self, request):
        """Build cache key including country filter and dataset version."""
        params = request.query_params
        country = params.get("country", "all")
        id_list = params.getlist("id") if hasattr(params, "getlist") else []
        # Embedding the dataset version orphans stale payloads when collector,
        # catchment, region or border data changes, instead of serving them.
        dataset_version = self.get_dataset_stats(request)["version"]

        if id_list:
            try:
                ids_sorted = sorted([str(int(x)) for x in id_list])
            except Exception:
                ids_sorted = sorted([str(x) for x in id_list])
            return (
                f"collector_geojson:country:{country}:id:{','.join(ids_sorted)}"
                f":dv:{dataset_version}"
            )

        return f"collector_geojson:country:{country}:dv:{dataset_version}"

    def get_geojson_serializer_class(self):
        """Use CollectorGeometrySerializer for GeoJSON endpoint."""
        return CollectorGeometrySerializer

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[permissions.AllowAny],
        throttle_classes=[GeoJSONAnonThrottle, GeoJSONUserThrottle],
    )
    def geojson(self, request, *args, **kwargs):
        """GeoJSON endpoint optimized for QGIS rendering."""
        return super().geojson(request, *args, **kwargs)


__all__ = ["CollectionViewSet", "CollectorViewSet"]
