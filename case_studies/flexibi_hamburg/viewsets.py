import hashlib
import json

from django.http import JsonResponse
from django_filters import rest_framework as rf_filters
from rest_framework.decorators import action
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

from case_studies.flexibi_hamburg.filters import HamburgRoadsideTreesFilterSet
from case_studies.flexibi_hamburg.models import HamburgRoadsideTrees
from case_studies.flexibi_hamburg.serializers import (
    HamburgRoadsideTreeGeometrySerializer,
    HamburgRoadsideTreeSimpleModelSerializer,
)
from maps.mixins import CachedGeoJSONMixin
from utils.viewsets import AutoPermModelViewSet


class GeoJSONAnonThrottle(AnonRateThrottle):
    """Rate limit for anonymous users on GeoJSON endpoints."""

    rate = "10/minute"


class GeoJSONUserThrottle(UserRateThrottle):
    """Rate limit for authenticated users on GeoJSON endpoints."""

    rate = "60/minute"


class HamburgRoadsideTreeViewSet(CachedGeoJSONMixin, AutoPermModelViewSet):
    """ViewSet for Hamburg roadside trees with cached GeoJSON support.

    Uses CachedGeoJSONMixin for server-side caching and streaming support
    for large datasets.
    """

    queryset = HamburgRoadsideTrees.objects.all()
    serializer_class = HamburgRoadsideTreeSimpleModelSerializer
    filter_backends = (rf_filters.DjangoFilterBackend,)
    filterset_class = HamburgRoadsideTreesFilterSet

    custom_permission_required = {
        "list": None,
        "retrieve": None,
        "geojson": None,
        "summaries": None,
        "version": None,
    }

    def get_queryset(self):
        """Return base queryset with model's default ordering."""
        return HamburgRoadsideTrees.objects.all()

    def get_geojson_queryset(self):
        """Return optimized queryset for GeoJSON with minimal fields.

        - Uses only() to fetch just id and geom (no other columns)
        - Removes ordering since point features don't need sorting
        - Avoids deferred field access that would negate .only() benefits
        """
        return HamburgRoadsideTrees.objects.only("id", "geom").order_by()

    def get_geojson_serializer_class(self):
        return HamburgRoadsideTreeGeometrySerializer

    def get_cache_key(self, request):
        """Build a deterministic cache key from filter parameters.

        Format: tree_geojson:filter:<hash>

        Detects when range filters are at full extent with nulls included,
        which means no actual filtering - returns 'tree_geojson:all' to hit
        the warm cache.
        """
        params = request.query_params
        exclude_keys = {"csrfmiddlewaretoken", "page", "format"}
        filters = {}

        for key in params.keys():
            if key in exclude_keys:
                continue
            values = (
                params.getlist(key) if hasattr(params, "getlist") else [params.get(key)]
            )
            if len(values) == 1:
                filters[key] = values[0]
            elif len(values) > 1:
                filters[key] = sorted(values)

        if not filters:
            return "tree_geojson:all"

        # Check if filters represent "no filtering" (default state)
        if self._is_default_filter_state(filters):
            return "tree_geojson:all"

        filter_string = json.dumps(dict(sorted(filters.items())), sort_keys=True)
        filter_hash = hashlib.sha1(filter_string.encode("utf-8")).hexdigest()[:16]
        return f"tree_geojson:filter:{filter_hash}"

    def _is_default_filter_state(self, filters):
        """Check if filter params represent the unfiltered default state.

        Returns True if:
        - No catchment or genus filters are set (key not present or empty value)
        - Range filters include nulls and are at full database extent
        """
        # Define which keys are range filter params (these can be at defaults)
        range_filter_keys = {
            "plantation_year_min",
            "plantation_year_max",
            "plantation_year_is_null",
            "stem_circumference_min",
            "stem_circumference_max",
            "stem_circumference_is_null",
        }

        # Check for any non-range filter keys with non-empty values
        for key, value in filters.items():
            if key not in range_filter_keys:
                # Any non-range filter with a truthy value means not default
                if value and str(value).strip():
                    return False

        # Check if nulls are included (required for "include everything")
        if filters.get("plantation_year_is_null") != "true":
            return False
        if filters.get("stem_circumference_is_null") != "true":
            return False

        # Get database min/max for range filters
        from django.db.models import Max, Min

        aggregates = HamburgRoadsideTrees.objects.aggregate(
            year_min=Min("pflanzjahr"),
            year_max=Max("pflanzjahr"),
            circ_min=Min("stammumfang"),
            circ_max=Max("stammumfang"),
        )

        # Compare filter values to database extent (with tolerance for float formatting)
        def values_match(filter_val, db_val):
            if filter_val is None or db_val is None:
                return filter_val is None and db_val is None
            try:
                return abs(float(filter_val) - float(db_val)) < 0.01
            except (ValueError, TypeError):
                return False

        if not values_match(filters.get("plantation_year_min"), aggregates["year_min"]):
            return False
        if not values_match(filters.get("plantation_year_max"), aggregates["year_max"]):
            return False
        if not values_match(
            filters.get("stem_circumference_min"), aggregates["circ_min"]
        ):
            return False
        if not values_match(
            filters.get("stem_circumference_max"), aggregates["circ_max"]
        ):
            return False

        return True

    @action(
        detail=False,
        methods=["get"],
        throttle_classes=[GeoJSONAnonThrottle, GeoJSONUserThrottle],
    )
    def geojson(self, request, *args, **kwargs):
        """GeoJSON endpoint with rate limiting.

        Uses CachedGeoJSONMixin for caching and streaming, with added
        throttling to prevent abuse.
        """
        return super().geojson(request, *args, **kwargs)

    @action(detail=False, methods=["get"])
    def summaries(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        data = {
            "summaries": [
                {
                    "tree_count": {
                        "label": "Number of trees",
                        "value": queryset.count(),
                    },
                }
            ]
        }
        return JsonResponse(data)
