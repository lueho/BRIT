from maps.views import GeoDataSetPublishedFilteredMapView, MapMixin
from processes.models import ProcessType
from utils.object_management.views import (
    PrivateObjectFilterView,
    PublishedObjectFilterView,
    UserCreatedObjectCreateView,
    UserCreatedObjectDetailView,
    UserCreatedObjectModalDeleteView,
    UserCreatedObjectUpdateView,
)

from .filters import ShowcaseFilterSet
from .forms import ShowcaseModelForm
from .models import Showcase

SHOWCASE_PROCESS_MAP = {
    "Municipality & farms 1": ["Anaerobic Digestion", "Composting"],
    "Agricultural Education": ["Anaerobic Digestion", "Pyrolysis", "Composting"],
}

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
    model_name = "Showcase"
    template_name = "closecycleshowcase_map.html"
    filterset_class = ShowcaseFilterSet
    map_title = "CLOSECYCLE Showcases & Pilot Regions"
    features_layer_api_basename = "api-showcase"


class ShowcaseCreateView(UserCreatedObjectCreateView):
    model = Showcase
    form_class = ShowcaseModelForm
    permission_required = "closecycle.add_showcase"


class ShowcaseDetailView(MapMixin, UserCreatedObjectDetailView):
    model = Showcase

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        showcase_name = getattr(self.object, "name", None)
        involved_processes = []
        if showcase_name in SHOWCASE_PROCESS_MAP:
            process_names = SHOWCASE_PROCESS_MAP[showcase_name]
            for pt in ProcessType.objects.filter(
                name__in=process_names, publication_status="published"
            ):
                involved_processes.append(
                    {
                        "name": pt.name,
                        "id": pt.pk,
                    }
                )
        context["involved_processes"] = involved_processes
        return context


class ShowcaseUpdateView(UserCreatedObjectUpdateView):
    model = Showcase
    form_class = ShowcaseModelForm


class ShowcaseModalDeleteView(UserCreatedObjectModalDeleteView):
    model = Showcase
