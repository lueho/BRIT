import hashlib
import json

from django.http import JsonResponse
from django_filters import rest_framework as rf_filters
from rest_framework.decorators import action
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

from maps.mixins import CachedGeoJSONMixin
from sources.roadside_trees.filters import HamburgRoadsideTreesFilterSet
from sources.roadside_trees.models import HamburgRoadsideTrees
from sources.roadside_trees.serializers import (
    HamburgRoadsideTreeGeometrySerializer,
    HamburgRoadsideTreeSimpleModelSerializer,
)
from utils.viewsets import AutoPermModelViewSet


class GeoJSONAnonThrottle(AnonRateThrottle):
    rate = "10/minute"


class GeoJSONUserThrottle(UserRateThrottle):
    rate = "60/minute"


class HamburgRoadsideTreeViewSet(CachedGeoJSONMixin, AutoPermModelViewSet):
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
        return HamburgRoadsideTrees.objects.all()

    def get_geojson_queryset(self):
        return HamburgRoadsideTrees.objects.only("id", "geom").order_by()

    def get_geojson_serializer_class(self):
        return HamburgRoadsideTreeGeometrySerializer

    def get_cache_key(self, request):
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

        if self._is_default_filter_state(filters):
            return "tree_geojson:all"

        filter_string = json.dumps(dict(sorted(filters.items())), sort_keys=True)
        filter_hash = hashlib.sha1(filter_string.encode("utf-8")).hexdigest()[:16]
        return f"tree_geojson:filter:{filter_hash}"

    def _is_default_filter_state(self, filters):
        range_filter_keys = {
            "plantation_year_min",
            "plantation_year_max",
            "plantation_year_is_null",
            "stem_circumference_min",
            "stem_circumference_max",
            "stem_circumference_is_null",
        }

        for key, value in filters.items():
            if key not in range_filter_keys:
                if value and str(value).strip():
                    return False

        if filters.get("plantation_year_is_null") != "true":
            return False
        if filters.get("stem_circumference_is_null") != "true":
            return False

        from django.db.models import Max, Min

        aggregates = HamburgRoadsideTrees.objects.aggregate(
            year_min=Min("pflanzjahr"),
            year_max=Max("pflanzjahr"),
            circ_min=Min("stammumfang"),
            circ_max=Max("stammumfang"),
        )

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
        if not values_match(filters.get("stem_circumference_min"), aggregates["circ_min"]):
            return False
        if not values_match(filters.get("stem_circumference_max"), aggregates["circ_max"]):
            return False

        return True

    @action(
        detail=False,
        methods=["get"],
        throttle_classes=[GeoJSONAnonThrottle, GeoJSONUserThrottle],
    )
    def geojson(self, request, *args, **kwargs):
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


__all__ = [
    "GeoJSONAnonThrottle",
    "GeoJSONUserThrottle",
    "HamburgRoadsideTreeViewSet",
]
