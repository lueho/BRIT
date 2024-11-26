from django.urls import reverse_lazy
from django.views.generic import DetailView

from maps.views import GeoDataSetFilteredMapView, MapMixin
from utils.views import OwnedObjectCreateView, OwnedObjectListView, OwnedObjectModalDeleteView, OwnedObjectUpdateView
from .filters import ShowcaseFilterSet
from .forms import ShowcaseModelForm
from .models import Showcase


# ----------- Showcase CRUD --------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class ShowcaseListView(OwnedObjectListView):
    model = Showcase
    filterset_class = ShowcaseFilterSet
    permission_required = set()


class ShowcaseMapView(GeoDataSetFilteredMapView):
    model = Showcase
    model_name = 'Showcase'
    template_name = 'closecycleshowcase_map.html'
    filterset_class = ShowcaseFilterSet
    map_title = 'CLOSECYCLE Showcases & Pilot Regions'
    features_layer_api_basename = 'api-showcase'


class ShowcaseCreateView(OwnedObjectCreateView):
    model = Showcase
    form_class = ShowcaseModelForm
    permission_required = 'closecycle.add_showcase'


class ShowcaseDetailView(MapMixin, DetailView):
    model = Showcase
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
