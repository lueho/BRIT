from django.urls import reverse_lazy
from django.views.generic import DetailView

from maps.views import GeoDataSetDetailView, MapMixin
from utils.views import OwnedObjectCreateView, OwnedObjectUpdateView, OwnedObjectModalDeleteView, OwnedObjectListView
from .filters import ShowcaseFilterSet
from .forms import ShowcaseModelForm
from .models import Showcase


# ----------- Showcase CRUD --------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class ShowcaseListView(OwnedObjectListView):
    model = Showcase
    filterset_class = ShowcaseFilterSet
    permission_required = set()


class ShowcaseMapView(GeoDataSetDetailView):
    model = Showcase
    model_name = 'Showcase'
    template_name = 'closecycleshowcase_map.html'
    filterset_class = ShowcaseFilterSet
    map_title = 'CLOSECYCLE Showcases'
    load_region = True
    load_catchment = False
    load_features = True
    feature_url = reverse_lazy('api-showcase-geojson')
    feature_summary_url = reverse_lazy('api-showcase-summary')
    apply_filter_to_features = False
    api_basename = 'api-showcase'
    region_layer_style = {
        'color': '#63c36c',
        'fillOpacity': 0,
        'width': 2,
    }
    feature_layer_style = {
        'color': '#007BFF',
        'fillOpacity': 0.5,
    }


class ShowcaseCreateView(OwnedObjectCreateView):
    model = Showcase
    form_class = ShowcaseModelForm
    permission_required = 'closecycle.add_showcase'


class ShowcaseDetailView(MapMixin, DetailView):
    model = Showcase
    api_basename = 'showcase'
    feature_url = reverse_lazy('api-showcase-geojson')
    load_region = False
    load_catchment = False
    permission_required = set()


class ShowcaseUpdateView(OwnedObjectUpdateView):
    model = Showcase
    form_class = ShowcaseModelForm
    permission_required = 'closecycle.change_showcase'


class ShowcaseModalDeleteView(OwnedObjectModalDeleteView):
    model = Showcase
    success_url = reverse_lazy('showcase-list')
    success_message = 'The showcase was successfully deleted.'
    permission_required = 'closecycle.delete_showcase'
