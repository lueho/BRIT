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
        return HamburgRoadsideTrees.objects.all().order_by("baumid")

    def get_geojson_queryset(self):
        """Return optimized queryset for GeoJSON with minimal fields."""
        return self.get_queryset().only("id", "geom")

    def get_geojson_serializer_class(self):
        return HamburgRoadsideTreeGeometrySerializer

    def get_cache_key(self, request):
        """Build a deterministic cache key from filter parameters.

        Format: tree_geojson:filter:<hash>
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

        filter_string = json.dumps(dict(sorted(filters.items())), sort_keys=True)
        filter_hash = hashlib.sha1(filter_string.encode("utf-8")).hexdigest()[:16]
        return f"tree_geojson:filter:{filter_hash}"

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
