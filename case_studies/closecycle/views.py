from maps.views import GeoDataSetPublishedFilteredMapView, MapMixin
from utils.views import (OwnedObjectCreateView, PrivateObjectFilterView, PublishedObjectFilterView,
                         UserCreatedObjectDetailView, UserCreatedObjectModalDeleteView, UserCreatedObjectUpdateView)
from .filters import ShowcaseFilterSet
from .forms import ShowcaseModelForm
from .models import Showcase


# ----------- Showcase CRUD --------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class ShowcasePublishedListView(PublishedObjectFilterView):
    model = Showcase
    filterset_class = ShowcaseFilterSet


class ShowcasePrivateFilterView(PrivateObjectFilterView):
    model = Showcase
    filterset_class = ShowcaseFilterSet


class ShowcasePublishedMapView(GeoDataSetPublishedFilteredMapView):
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


class ShowcaseDetailView(MapMixin, UserCreatedObjectDetailView):
    model = Showcase


class ShowcaseUpdateView(UserCreatedObjectUpdateView):
    model = Showcase
    form_class = ShowcaseModelForm


class ShowcaseModalDeleteView(UserCreatedObjectModalDeleteView):
    model = Showcase
