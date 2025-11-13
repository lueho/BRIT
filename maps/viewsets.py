from django.db.models import Count
from rest_framework.decorators import action
from rest_framework.response import Response

from utils.viewsets import AutoPermModelViewSet

from .filters import CatchmentFilterSet, RegionFilterSet
from .mixins import CachedGeoJSONMixin
from .models import Catchment, Location, NutsRegion, Region
from .serializers import (
    CatchmentGeoFeatureModelSerializer,
    CatchmentModelSerializer,
    LocationGeoFeatureModelSerializer,
    LocationModelSerializer,
    NutsRegionGeometrySerializer,
    NutsRegionSummarySerializer,
    RegionGeoFeatureModelSerializer,
    RegionModelSerializer,
)
from .utils import (
    get_catchment_cache_key,
    get_nuts_region_cache_key,
    get_region_cache_key,
)


class LocationViewSet(AutoPermModelViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationModelSerializer
    filterset_fields = ("id",)
    custom_permission_required = {"list": None, "retrieve": None, "geojson": None}

    @action(detail=False, methods=["get"])
    def geojson(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = LocationGeoFeatureModelSerializer(
            queryset, many=True, context={"request": request}
        )
        return Response(serializer.data)


class RegionViewSet(CachedGeoJSONMixin, AutoPermModelViewSet):
    queryset = Region.objects.all()
    serializer_class = RegionModelSerializer
    filterset_class = RegionFilterSet
    custom_permission_required = {
        "list": None,
        "retrieve": None,
        "geojson": None,
        "summaries": None,
    }

    def get_cache_key(self, request):
        filters = request.query_params.dict()
        region_id = filters.get("id")
        return get_region_cache_key(region_id, filters)

    def get_serializer_class(self):
        if self.action == "geojson":
            return RegionGeoFeatureModelSerializer
        return RegionModelSerializer

    @action(detail=False, methods=["get"])
    def summaries(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        summary_data = queryset.aggregate(
            total_count=Count("id"),
        )
        return Response(summary_data)


class CatchmentViewSet(CachedGeoJSONMixin, AutoPermModelViewSet):
    queryset = Catchment.objects.all()
    serializer_class = CatchmentModelSerializer
    filterset_class = CatchmentFilterSet
    custom_permission_required = {"list": None, "retrieve": None, "geojson": None}

    def get_cache_key(self, request):
        filters = request.query_params.dict()
        catchment_id = filters.get("id")
        return get_catchment_cache_key(catchment_id, filters)

    def get_serializer_class(self):
        if self.action == "geojson":
            return CatchmentGeoFeatureModelSerializer
        return CatchmentModelSerializer


class NutsRegionViewSet(CachedGeoJSONMixin, AutoPermModelViewSet):
    queryset = NutsRegion.objects.all()
    serializer_class = NutsRegionSummarySerializer
    filterset_fields = ("id", "levl_code", "cntr_code", "parent_id")
    custom_permission_required = {"list": None, "retrieve": None, "geojson": None}

    def get_cache_key(self, request):
        filters = request.query_params.dict()
        level = filters.get("levl_code")
        parent_id = filters.get("parent_id")
        return get_nuts_region_cache_key(level, parent_id, filters)

    def get_serializer_class(self):
        if self.action == "geojson":
            return NutsRegionGeometrySerializer
        return NutsRegionSummarySerializer
