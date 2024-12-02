import json

from celery.result import AsyncResult
from dal import autocomplete
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.clickjacking import xframe_options_exempt

import case_studies.flexibi_hamburg.tasks
from maps.models import Catchment, GeoDataset
from maps.views import GeoDataSetFilteredMapView
from .filters import HamburgRoadsideTreesFilterSet


class RoadsideTreesMapView(GeoDataSetFilteredMapView):
    model_name = 'HamburgRoadsideTrees'
    template_name = 'hamburg_roadside_trees_map.html'
    filterset_class = HamburgRoadsideTreesFilterSet
    features_layer_api_basename = 'api-hamburg-roadside-trees'
    map_title = 'Roadside Trees'


@method_decorator(xframe_options_exempt, name='dispatch')
class RoadsideTreesMapIframeView(GeoDataSetFilteredMapView):
    model_name = 'HamburgRoadsideTrees'
    template_name = 'hamburg_roadside_trees_map_iframe.html'
    filterset_class = HamburgRoadsideTreesFilterSet
    features_layer_api_basename = 'api-hamburg-roadside-trees'
    map_title = 'Roadside Trees'


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
        if self.request.user.is_authenticated:
            qs = Catchment.objects.filter(Q(owner=self.request.user) | Q(publication_status='published'))
        else:
            qs = Catchment.objects.filter(publication_status='published')
        dataset_region = GeoDataset.objects.get(model_name='HamburgRoadsideTrees').region
        qs = qs.filter(region__borders__geom__within=dataset_region.geom).order_by('name')
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs
