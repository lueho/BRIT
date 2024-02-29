from rest_framework.decorators import action
from rest_framework.response import Response

from utils.viewsets import AutoPermModelViewSet
from .models import Location
from .serializers import LocationModelSerializer, LocationGeoFeatureModelSerializer


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
