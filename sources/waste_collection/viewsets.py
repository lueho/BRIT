from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Exists, F, OuterRef, Q
from django.urls import reverse
from django_filters import rest_framework as rf_filters
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

from maps.db_functions import SimplifyPreserveTopology
from maps.mixins import CachedGeoJSONMixin
from maps.utils import build_collection_cache_key
from sources.waste_collection.filters import CollectionFilterSet
from sources.waste_collection.importers import CollectionImporter
from sources.waste_collection.models import (
    AggregatedCollectionPropertyValue,
    Collection,
    CollectionPropertyValue,
    Collector,
    WasteFlyer,
)
from sources.waste_collection.serializers import (
    GEOMETRY_SIMPLIFY_TOLERANCE,
    AggregatedCollectionPropertyValueMutationSerializer,
    CollectionFlatSerializer,
    CollectionImportRecordSerializer,
    CollectionModelSerializer,
    CollectionMutationCreateSerializer,
    CollectionMutationUpdateSerializer,
    CollectionMutationVersionSerializer,
    CollectionPropertyValueMutationSerializer,
    CollectorGeometrySerializer,
    WasteCollectionGeometrySerializer,
)
from utils.object_management.models import ReviewAction
from utils.object_management.permissions import UserCreatedObjectPermission
from utils.object_management.viewsets import UserCreatedObjectViewSet


class CollectionDjangoFilterBackend(rf_filters.DjangoFilterBackend):
    """DjangoFilterBackend variant that accepts extra view-provided kwargs."""

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


class CollectionViewSet(CachedGeoJSONMixin, UserCreatedObjectViewSet):
    """Collection viewset that integrates with GeoJSONMixin and UserCreatedObjectViewSet.

    Provides the standard CRUD operations for collections, plus:
    - GeoJSON endpoint with scope-based filtering
    - Review workflow actions (register_for_review, withdraw_from_review, approve, reject)
    - Publication status filtering based on user permissions
    """

    queryset = Collection.objects.all()
    serializer_class = CollectionFlatSerializer
    geojson_serializer_class = WasteCollectionGeometrySerializer
    filter_backends = (CollectionDjangoFilterBackend,)
    filterset_class = CollectionFilterSet
    requires_add_permission_actions = {
        "create_collection",
        "create_new_version",
        "create_collection_property_value",
        "create_aggregated_collection_property_value",
    }

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

        published_successors = Collection.objects.filter(
            publication_status=Collection.STATUS_PUBLISHED,
            predecessors=OuterRef("pk"),
        )
        return queryset.annotate(
            has_visible_successor=Exists(published_successors)
        ).filter(has_visible_successor=False)

    def get_serializer_class(self):
        """Use detailed serializer for retrieve so the UI receives ownership and status fields.

        - retrieve -> CollectionModelSerializer (includes owner_id, publication_status, etc.)
        - default  -> self.serializer_class (CollectionFlatSerializer)
        """
        if getattr(self, "action", None) == "retrieve":
            return CollectionModelSerializer
        return super().get_serializer_class()

    # Ensure CachedGeoJSONMixin uses the GeoJSON serializer class
    def get_geojson_serializer_class(self):
        return WasteCollectionGeometrySerializer

    def get_filterset_kwargs(self):
        """Pass lightweight filter kwargs for API-only actions.

        GeoJSON/version endpoints do not render filter widgets, so they can skip
        expensive min/max slider calculations performed during filterset init.
        """
        if getattr(self, "action", None) in {"geojson", "version"}:
            return {"skip_min_max": True}
        return {}

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

    @staticmethod
    def _require_add_permission_for_model(actor, model):
        if actor.is_staff:
            return
        app_label = model._meta.app_label
        model_name = model._meta.model_name
        if not actor.has_perm(f"{app_label}.add_{model_name}"):
            raise PermissionDenied(
                f"You do not have permission to add {model._meta.verbose_name}."
            )

    @staticmethod
    def _require_can_add_property(request, collection):
        actor = getattr(request, "user", None)
        if actor is None or not actor.is_authenticated:
            raise PermissionDenied("Authentication is required for this action.")

        if collection.publication_status == Collection.STATUS_ARCHIVED:
            raise PermissionDenied(
                "You do not have permission to add statistics to this collection."
            )

        if actor.is_staff:
            return

        if collection.owner_id == actor.id:
            return

        if collection.publication_status == Collection.STATUS_PUBLISHED:
            return

        raise PermissionDenied(
            "You do not have permission to add statistics to this collection."
        )

    @staticmethod
    def _flyer_title(url):
        """Return a short title derived from the URL hostname (max 255 chars)."""
        from urllib.parse import urlparse

        try:
            hostname = urlparse(url).hostname or url
        except Exception:
            hostname = url
        return hostname[:255]

    @staticmethod
    def _attach_sources_and_flyers(collection, sources, flyer_urls):
        """Attach bibliography sources and flyer URLs to ``collection``."""
        if sources:
            collection.sources.add(*sources)

        for url in flyer_urls:
            if len(url) > 2083:
                continue

            flyer, _ = WasteFlyer.objects.get_or_create_by_url(
                url=url,
                defaults={
                    "owner": collection.owner,
                    "title": CollectionViewSet._flyer_title(url),
                    "publication_status": "private",
                },
            )
            collection.flyers.add(flyer)

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

    @staticmethod
    def _new_version_predecessor_queryset(user):
        """Return predecessor queryset visible for version creation.

        Rule: authenticated users may branch from published collections and
        from their own collections.
        """
        if not user or not user.is_authenticated:
            return Collection.objects.none()
        return Collection.objects.filter(
            Q(publication_status=Collection.STATUS_PUBLISHED) | Q(owner=user)
        )

    def _submit_for_review_if_requested(self, request, collection, submit_for_review):
        """Submit ``collection`` for review and create a submitted ReviewAction."""
        if not submit_for_review:
            return False

        permission = UserCreatedObjectPermission()
        if not permission.has_submit_permission(request, collection):
            raise PermissionDenied(
                "You do not have permission to submit this collection for review."
            )

        collection.submit_for_review()
        ReviewAction.objects.create(
            content_type=ContentType.objects.get_for_model(collection.__class__),
            object_id=collection.pk,
            user=request.user,
            action=ReviewAction.ACTION_SUBMITTED,
            comment="",
        )
        return True

    def _submit_object_for_review_if_requested(self, request, obj, submit_for_review):
        if not submit_for_review:
            return False

        permission = UserCreatedObjectPermission()
        if not permission.has_submit_permission(request, obj):
            raise PermissionDenied(
                f"You do not have permission to submit this {obj._meta.verbose_name} for review."
            )

        obj.submit_for_review()
        ReviewAction.objects.create(
            content_type=ContentType.objects.get_for_model(obj.__class__),
            object_id=obj.pk,
            user=request.user,
            action=ReviewAction.ACTION_SUBMITTED,
            comment="",
        )
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
        expected_pairs = {
            "catchment": (str(collection.catchment), data["expected_catchment"]),
            "waste_category": (
                str(actual_waste_category) if actual_waste_category else "",
                data["expected_waste_category"],
            ),
            "collection_system": (
                str(collection.collection_system),
                data["expected_collection_system"],
            ),
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
    def _apply_collection_mutation_update(collection, data):
        scalar_fields = (
            "collector",
            "frequency",
            "fee_system",
            "sorting_method",
            "established",
            "connection_type",
            "min_bin_size",
            "required_bin_capacity",
            "required_bin_capacity_reference",
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
                data.get("sources", []),
                data.get("flyer_urls", []),
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

        if collection.owner_id != actor.id:
            raise PermissionDenied(
                "Only the collection owner may use the programmatic update endpoint."
            )

        serializer = CollectionMutationUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        mismatches = self._collection_identity_mismatches(collection, data)
        if mismatches:
            return Response(
                {
                    "detail": "Target collection no longer matches the expected identity.",
                    "mismatches": mismatches,
                },
                status=status.HTTP_409_CONFLICT,
            )

        with transaction.atomic():
            self._apply_collection_mutation_update(collection, data)

        return Response(
            {
                **self._serialize_mutation_response(collection, False),
                "updated": True,
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated],
        url_path="property-value/create",
        url_name="property-value-create",
    )
    def create_collection_property_value(self, request, *args, **kwargs):
        actor = self._require_authenticated_actor(request)
        self._require_add_permission_for_model(actor, CollectionPropertyValue)

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
        self._require_add_permission_for_model(actor, AggregatedCollectionPropertyValue)

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
        existing_acpv = None
        for candidate in AggregatedCollectionPropertyValue.objects.filter(
            owner=actor,
            property=prop,
            unit=unit,
            year=data["year"],
        ).prefetch_related("collections"):
            candidate_ids = sorted(candidate.collections.values_list("pk", flat=True))
            if candidate_ids == requested_collection_ids:
                existing_acpv = candidate
                break

        with transaction.atomic():
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
        serializer = CollectionMutationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        allowed_materials = list(data.get("allowed_materials", []))
        forbidden_materials = list(data.get("forbidden_materials", []))

        with transaction.atomic():
            collection = Collection.objects.create(
                name="",
                owner=request.user,
                publication_status=Collection.STATUS_PRIVATE,
                catchment=data["catchment"],
                collector=data.get("collector"),
                collection_system=data["collection_system"],
                waste_category=data["waste_category"],
                frequency=data.get("frequency"),
                fee_system=data.get("fee_system"),
                sorting_method=data.get("sorting_method"),
                established=data.get("established"),
                valid_from=data["valid_from"],
                valid_until=data.get("valid_until"),
                connection_type=data.get("connection_type"),
                min_bin_size=data.get("min_bin_size"),
                required_bin_capacity=data.get("required_bin_capacity"),
                required_bin_capacity_reference=data.get(
                    "required_bin_capacity_reference"
                ),
                description=data.get("description", ""),
            )
            if allowed_materials:
                collection.allowed_materials.set(allowed_materials)
            if forbidden_materials:
                collection.forbidden_materials.set(forbidden_materials)

            self._attach_sources_and_flyers(
                collection,
                sources=data.get("sources", []),
                flyer_urls=data.get("flyer_urls", []),
            )
            submitted = self._submit_for_review_if_requested(
                request,
                collection,
                submit_for_review=data.get("submit_for_review", True),
            )

        return Response(
            self._serialize_mutation_response(collection, submitted),
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
        predecessor = (
            self._new_version_predecessor_queryset(request.user)
            .filter(pk=pk)
            .select_related(
                "owner",
                "catchment",
                "collector",
                "collection_system",
                "waste_category",
                "frequency",
                "fee_system",
                "sorting_method",
            )
            .prefetch_related("allowed_materials", "forbidden_materials")
            .first()
        )
        if predecessor is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = CollectionMutationVersionSerializer(
            data=request.data,
            context={"predecessor": predecessor},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        default_waste_category = predecessor.effective_waste_category
        default_allowed = list(predecessor.effective_allowed_materials)
        default_forbidden = list(predecessor.effective_forbidden_materials)

        waste_category = data.get(
            "waste_category",
            default_waste_category,
        )
        if waste_category is None:
            return Response(
                {
                    "detail": "waste_category is required when the predecessor has no waste_category."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        allowed_materials = list(data.get("allowed_materials", default_allowed))
        forbidden_materials = list(data.get("forbidden_materials", default_forbidden))

        with transaction.atomic():
            collection = Collection.objects.create(
                name="",
                owner=request.user,
                publication_status=Collection.STATUS_PRIVATE,
                catchment=data.get("catchment", predecessor.catchment),
                collector=data.get("collector", predecessor.collector),
                collection_system=data.get(
                    "collection_system",
                    predecessor.collection_system,
                ),
                waste_category=waste_category,
                frequency=data.get("frequency", predecessor.frequency),
                fee_system=data.get("fee_system", predecessor.fee_system),
                sorting_method=data.get("sorting_method", predecessor.sorting_method),
                established=data.get("established", predecessor.established),
                valid_from=data["valid_from"],
                valid_until=data.get("valid_until"),
                connection_type=data.get(
                    "connection_type", predecessor.connection_type
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
            )
            collection.allowed_materials.set(allowed_materials)
            collection.forbidden_materials.set(forbidden_materials)
            collection.add_predecessor(predecessor)

            default_sources = list(predecessor.sources.all())
            default_flyer_urls = list(
                predecessor.flyers.exclude(url__isnull=True)
                .exclude(url="")
                .values_list("url", flat=True)
            )
            self._attach_sources_and_flyers(
                collection,
                sources=data.get("sources", default_sources),
                flyer_urls=data.get("flyer_urls", default_flyer_urls),
            )
            submitted = self._submit_for_review_if_requested(
                request,
                collection,
                submit_for_review=data.get("submit_for_review", True),
            )

        return Response(
            {
                **self._serialize_mutation_response(collection, submitted),
                "predecessor_id": predecessor.pk,
            },
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

        Only staff users may call this endpoint.
        """
        if not request.user.is_staff:
            return Response(
                {"detail": "Only staff users may import collection records."},
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
        )
        stats = importer.run(serializer.validated_data, dry_run=dry_run)

        http_status = status.HTTP_200_OK if dry_run else status.HTTP_201_CREATED
        return Response({"dry_run": dry_run, "stats": stats}, status=http_status)

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny])
    def summaries(self, request, *args, **kwargs):
        self.check_permissions(request)
        queryset = self.get_queryset().filter(id__in=request.query_params.getlist("id"))
        serializer = CollectionModelSerializer(
            queryset,
            many=True,
            field_labels_as_keys=True,
            context={"request": request},
        )
        return Response({"summaries": serializer.data})

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
        ).prefetch_related(
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

    def get_cache_key(self, request):
        """Build cache key including country filter."""
        params = request.query_params
        country = params.get("country", "all")
        id_list = params.getlist("id") if hasattr(params, "getlist") else []

        if id_list:
            try:
                ids_sorted = sorted([str(int(x)) for x in id_list])
            except Exception:
                ids_sorted = sorted([str(x) for x in id_list])
            return f"collector_geojson:country:{country}:id:{','.join(ids_sorted)}"

        return f"collector_geojson:country:{country}"

    def get_geojson_serializer_class(self):
        """Use CollectorGeometrySerializer for GeoJSON endpoint."""
        return CollectorGeometrySerializer

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny])
    def geojson(self, request, *args, **kwargs):
        """GeoJSON endpoint optimized for QGIS rendering."""
        return super().geojson(request, *args, **kwargs)


__all__ = ["CollectionViewSet", "CollectorViewSet"]
