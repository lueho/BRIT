from django.db.models import F
from django_filters import rest_framework as rf_filters
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

from case_studies.soilcom.filters import CollectionFilterSet
from case_studies.soilcom.importers import CollectionImporter
from case_studies.soilcom.models import Collection, Collector
from case_studies.soilcom.serializers import (
    GEOMETRY_SIMPLIFY_TOLERANCE,
    CollectionFlatSerializer,
    CollectionImportRecordSerializer,
    CollectionModelSerializer,
    CollectorGeometrySerializer,
    WasteCollectionGeometrySerializer,
)
from maps.db_functions import SimplifyPreserveTopology
from maps.mixins import CachedGeoJSONMixin
from maps.utils import build_collection_cache_key
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
            "waste_stream",
            "waste_stream__category",
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
