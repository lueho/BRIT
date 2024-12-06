from django_filters import rest_framework as rf_filters
from rest_framework.decorators import action
from rest_framework.response import Response

from case_studies.soilcom.filters import CollectionFilterSet
from case_studies.soilcom.models import Collection
from case_studies.soilcom.serializers import (CollectionFlatSerializer, CollectionModelSerializer,
                                              WasteCollectionGeometrySerializer)
from utils.viewsets import AutoPermModelViewSet


class CollectionViewSet(AutoPermModelViewSet):
    queryset = Collection.objects.all()
    serializer_class = CollectionFlatSerializer
    filter_backends = (rf_filters.DjangoFilterBackend,)
    filterset_class = CollectionFilterSet
    custom_permission_required = {
        'list': None,
        'retrieve': None,
        'geojson': None,
        'summaries': None,
    }

    @action(detail=False, methods=['get'])
    def geojson(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = WasteCollectionGeometrySerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def summaries(self, request, *args, **kwargs):
        serializer = CollectionModelSerializer(Collection.objects.filter(id__in=request.query_params.getlist('id')),
                                               many=True, field_labels_as_keys=True, context={'request': request})
        return Response({'summaries': serializer.data})
