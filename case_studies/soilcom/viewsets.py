from django_filters import rest_framework as rf_filters
from rest_framework.decorators import action
from rest_framework.response import Response

from case_studies.soilcom.filters import CollectionFilterSet
from case_studies.soilcom.models import Collection
from case_studies.soilcom.serializers import (CollectionFlatSerializer, CollectionModelSerializer,
                                              WasteCollectionGeometrySerializer)
from maps.mixins import GeoJSONMixin
from utils.viewsets import UserCreatedObjectViewSet


class CollectionViewSet(GeoJSONMixin, UserCreatedObjectViewSet):
    """Collection viewset that integrates with GeoJSONMixin and UserCreatedObjectViewSet.
    
    Provides the standard CRUD operations for collections, plus:
    - GeoJSON endpoint with scope-based filtering
    - Review workflow actions (register_for_review, withdraw_from_review, approve, reject)
    - Publication status filtering based on user permissions
    """
    queryset = Collection.objects.all()
    serializer_class = CollectionFlatSerializer
    geojson_serializer_class = WasteCollectionGeometrySerializer
    filter_backends = (rf_filters.DjangoFilterBackend,)
    filterset_class = CollectionFilterSet

    @action(detail=False, methods=['get'])
    def summaries(self, request, *args, **kwargs):
        serializer = CollectionModelSerializer(Collection.objects.filter(id__in=request.query_params.getlist('id')),
                                               many=True, field_labels_as_keys=True, context={'request': request})
        return Response({'summaries': serializer.data})
