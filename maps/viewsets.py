from django.db.models import Count
from rest_framework.decorators import action
from rest_framework.response import Response

from utils.viewsets import AutoPermModelViewSet
from .filters import CatchmentFilterSet, RegionFilterSet
from .models import Catchment, Location, NutsRegion, Region
from .serializers import (CatchmentGeoFeatureModelSerializer, CatchmentModelSerializer,
                          LocationGeoFeatureModelSerializer, LocationModelSerializer, NutsRegionGeometrySerializer,
                          NutsRegionSummarySerializer, RegionGeoFeatureModelSerializer, RegionModelSerializer)


class LocationViewSet(AutoPermModelViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationModelSerializer
    filterset_fields = ('id',)
    custom_permission_required = {
        'list': None,
        'retrieve': None,
        'geojson': None
    }

    @action(detail=False, methods=['get'])
    def geojson(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = LocationGeoFeatureModelSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)


class RegionViewSet(AutoPermModelViewSet):
    queryset = Region.objects.all()
    serializer_class = RegionModelSerializer
    filterset_class = RegionFilterSet
    custom_permission_required = {
        'list': None,
        'retrieve': None,
        'geojson': None
    }

    @action(detail=False, methods=['get'])
    def geojson(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = RegionGeoFeatureModelSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def summaries(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        summary_data = queryset.aggregate(
            total_count=Count('id'),
        )
        return Response(summary_data)


class CatchmentViewSet(AutoPermModelViewSet):
    queryset = Catchment.objects.all()
    serializer_class = CatchmentModelSerializer
    filterset_class = CatchmentFilterSet
    custom_permission_required = {
        'list': None,
        'retrieve': None,
        'geojson': None
    }

    @action(detail=False, methods=['get'])
    def geojson(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = CatchmentGeoFeatureModelSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)


class NutsRegionViewSet(AutoPermModelViewSet):
    queryset = NutsRegion.objects.all()
    serializer_class = NutsRegionSummarySerializer
    filterset_fields = ('id', 'levl_code', 'cntr_code', 'parent_id')
    custom_permission_required = {
        'list': None,
        'retrieve': None,
        'geojson': None
    }

    @action(detail=False, methods=['get'])
    def geojson(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = NutsRegionGeometrySerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)
