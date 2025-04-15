import json

from dal import autocomplete
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt

import case_studies.flexibi_hamburg.tasks
from maps.models import Catchment, GeoDataset
from maps.views import GeoDataSetPublishedFilteredMapView
from utils.file_export.views import FilteredListFileExportView
from .filters import HamburgRoadsideTreesFilterSet


class RoadsideTreesPublishedMapView(GeoDataSetPublishedFilteredMapView):
    model_name = 'HamburgRoadsideTrees'
    template_name = 'hamburg_roadside_trees_map.html'
    filterset_class = HamburgRoadsideTreesFilterSet
    features_layer_api_basename = 'api-hamburg-roadside-trees'
    map_title = 'Roadside Trees'


@method_decorator(xframe_options_exempt, name='dispatch')
class RoadsideTreesPublishedMapIframeView(GeoDataSetPublishedFilteredMapView):
    model_name = 'HamburgRoadsideTrees'
    template_name = 'hamburg_roadside_trees_map_iframe.html'
    filterset_class = HamburgRoadsideTreesFilterSet
    features_layer_api_basename = 'api-hamburg-roadside-trees'
    map_title = 'Roadside Trees'


class HamburgRoadsideTreesListFileExportView(FilteredListFileExportView):
    task_function = case_studies.flexibi_hamburg.tasks.export_hamburg_roadside_trees_to_file


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
