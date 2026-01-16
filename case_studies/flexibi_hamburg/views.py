from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt

from maps.views import CatchmentAutocompleteView, GeoDataSetPublishedFilteredMapView
from utils.file_export.views import GenericUserCreatedObjectExportView

from .filters import HamburgRoadsideTreesFilterSet


class RoadsideTreesPublishedMapView(GeoDataSetPublishedFilteredMapView):
    model_name = "HamburgRoadsideTrees"
    template_name = "hamburg_roadside_trees_map.html"
    filterset_class = HamburgRoadsideTreesFilterSet
    features_layer_api_basename = "api-hamburg-roadside-trees"
    map_title = "Roadside Trees"


@method_decorator(xframe_options_exempt, name="dispatch")
class RoadsideTreesPublishedMapIframeView(GeoDataSetPublishedFilteredMapView):
    model_name = "HamburgRoadsideTrees"
    template_name = "hamburg_roadside_trees_map_iframe.html"
    filterset_class = HamburgRoadsideTreesFilterSet
    features_layer_api_basename = "api-hamburg-roadside-trees"
    map_title = "Roadside Trees"

    def post_process_map_config(self, map_config):
        map_config = super().post_process_map_config(map_config)
        map_config["applyFilterToFeatures"] = True
        return map_config


class HamburgRoadsideTreesListFileExportView(GenericUserCreatedObjectExportView):
    model_label = "flexibi_hamburg.HamburgRoadsideTrees"


class HamburgRoadsideTreeCatchmentAutocompleteView(CatchmentAutocompleteView):
    geodataset_model_name = "HamburgRoadsideTrees"
