from django.http import JsonResponse
from django_filters import rest_framework as rf_filters
from rest_framework.decorators import action
from rest_framework.response import Response

from case_studies.flexibi_hamburg.filters import HamburgRoadsideTreesFilterSet
from case_studies.flexibi_hamburg.models import HamburgRoadsideTrees
from case_studies.flexibi_hamburg.serializers import (HamburgRoadsideTreeGeometrySerializer,
                                                      HamburgRoadsideTreeSimpleModelSerializer)
from utils.viewsets import AutoPermModelViewSet


class HamburgRoadsideTreeViewSet(AutoPermModelViewSet):
    queryset = HamburgRoadsideTrees.objects.all()
    serializer_class = HamburgRoadsideTreeSimpleModelSerializer
    filter_backends = (rf_filters.DjangoFilterBackend,)
    filterset_class = HamburgRoadsideTreesFilterSet

    custom_permission_required = {
        'list': None,
        'retrieve': None,
        'geojson': None,
        'summaries': None,
    }

    @action(detail=False, methods=['get'])
    def geojson(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = HamburgRoadsideTreeGeometrySerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def summaries(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        data = {
            'summaries': [{
                'tree_count': {
                    'label': 'Number of trees',
                    'value': queryset.count()
                },
            }]
        }
        return JsonResponse(data)
