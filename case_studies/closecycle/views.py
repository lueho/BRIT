from django.conf import settings

from maps.views import GeoDataSetPublishedFilteredMapView, MapMixin
from processes.views import MOCK_PROCESS_TYPES
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

# Hybrid mock: Showcase name to involved process names
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
        # Only inject mock data in dev/test
        if getattr(settings, "ENVIRONMENT", "dev") != "prod":
            showcase_name = getattr(self.object, "name", None)
            involved_processes = []
            if showcase_name in SHOWCASE_PROCESS_MAP:
                process_names = SHOWCASE_PROCESS_MAP[showcase_name]
                # Find process dicts from MOCK_PROCESS_TYPES
                for pname in process_names:
                    proc = next(
                        (p for p in MOCK_PROCESS_TYPES if p["name"] == pname), None
                    )
                    if proc:
                        involved_processes.append(
                            {
                                "name": proc["name"],
                                "id": proc["id"],
                            }
                        )
            context["involved_processes"] = involved_processes
        return context


class ShowcaseUpdateView(UserCreatedObjectUpdateView):
    model = Showcase
    form_class = ShowcaseModelForm


class ShowcaseModalDeleteView(UserCreatedObjectModalDeleteView):
    model = Showcase
