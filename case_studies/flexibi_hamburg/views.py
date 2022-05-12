from django.http import JsonResponse
from django.urls import reverse_lazy
from rest_framework.generics import GenericAPIView
from django_filters import rest_framework as rf_filters

from maps.models import GeoDataset
from maps.views import GeoDatasetDetailView
from .filters import TreeFilter
from .models import HamburgRoadsideTrees
from .serializers import HamburgRoadsideTreeGeometrySerializer


class RoadsideTreesMapView(GeoDatasetDetailView):
    feature_url = reverse_lazy('data.hamburg_roadside_trees')
    filter_class = TreeFilter
    load_features = False
    marker_style = {
        'color': '#63c36c',
        'fillOpacity': 1,
        'radius': 5,
        'stroke': False
    }

    def get_object(self, **kwargs):
        self.kwargs.update({'pk': GeoDataset.objects.get(model_name='HamburgRoadsideTrees').pk})
        return super().get_object(**kwargs)


class HamburgRoadsideTreeAPIView(GenericAPIView):
    queryset = HamburgRoadsideTrees.objects.all()
    serializer_class = HamburgRoadsideTreeGeometrySerializer
    filter_backends = (rf_filters.DjangoFilterBackend,)
    filterset_class = TreeFilter

    def get(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = {
            'geoJson': serializer.data,
            'summaries': [{
                'tree_count': {
                    'label': 'Number of trees',
                    'value': len(serializer.data['features'])
                },
            }]
        }
        return JsonResponse(data)
