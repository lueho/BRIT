import json

from celery.result import AsyncResult
from dal import autocomplete
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.urls import reverse_lazy
from django.views import View
from django_filters import rest_framework as rf_filters
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.viewsets import ReadOnlyModelViewSet

import case_studies.flexibi_hamburg.tasks
from maps.models import Catchment, GeoDataset
from maps.views import GeoDataSetDetailView
from .filters import HamburgRoadsideTreesFilterSet
from .models import HamburgRoadsideTrees
from .serializers import HamburgRoadsideTreeGeometrySerializer, HamburgRoadsideTreeSimpleModelSerializer


class RoadsideTreesMapView(GeoDataSetDetailView):
    template_name = 'hamburg_roadside_trees_map.html'
    filterset_class = HamburgRoadsideTreesFilterSet
    map_title = 'Hamburg Roadside Trees'
    load_region = True
    #TODO: This must be generalized to automatically retrieve the id from the dataset entry
    region_id = 3
    load_catchment = True
    load_features = False
    feature_url = reverse_lazy('data.hamburg_roadside_trees')
    apply_filter_to_features = True
    api_basename = 'api-hamburgroadsidetree'
    feature_layer_style = {
        'color': '#63c36c',
        'fillOpacity': 1,
        'radius': 5,
        'stroke': False
    }
    catchment_layer_style = {
        'color': '#04555E',
        'fillOpacity': 0.1,
        'weight': 1
    }

    def get_object(self, **kwargs):
        self.kwargs.update({'pk': GeoDataset.objects.get(model_name='HamburgRoadsideTrees').pk})
        return super().get_object(**kwargs)


class HamburgRoadsideTreeViewSet(ReadOnlyModelViewSet):
    queryset = HamburgRoadsideTrees.objects.all()
    serializer_class = HamburgRoadsideTreeSimpleModelSerializer
    filter_backends = (rf_filters.DjangoFilterBackend,)
    filterset_class = HamburgRoadsideTreesFilterSet

    def get_permissions(self):
        if self.action == 'retrieve':
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]


class HamburgRoadsideTreeAPIView(GenericAPIView):
    queryset = HamburgRoadsideTrees.objects.all()
    serializer_class = HamburgRoadsideTreeGeometrySerializer
    filter_backends = (rf_filters.DjangoFilterBackend,)
    filterset_class = HamburgRoadsideTreesFilterSet
    authentication_classes = []
    permission_classes = []

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


class HamburgRoadsideTreesListFileExportView(LoginRequiredMixin, View):

    @staticmethod
    def get(request, *args, **kwargs):
        params = dict(request.GET)
        file_format = params.pop('format', 'csv')[0]
        params.pop('page', None)
        task = case_studies.flexibi_hamburg.tasks.export_hamburg_roadside_trees_to_file.delay(file_format, params)
        response_data = {
            'task_id': task.task_id
        }
        return HttpResponse(json.dumps(response_data), content_type='application/json')


class HamburgRoadsideTreesListFileExportProgressView(LoginRequiredMixin, View):

    @staticmethod
    def get(request, task_id):
        result = AsyncResult(task_id)
        response_data = {
            'state': result.state,
            'details': result.info,
        }
        return HttpResponse(json.dumps(response_data), content_type='application/json')


class HamburgRoadsideTreeCatchmentAutocompleteView(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        dataset_region = GeoDataset.objects.get(model_name='HamburgRoadsideTrees').region
        qs = Catchment.objects.filter(region__borders__geom__within=dataset_region.geom).order_by('name')
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs
