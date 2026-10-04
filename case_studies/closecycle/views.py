from maps.views import GeoDataSetPublishedFilteredMapView, MapMixin
from utils.object_management.views import (
    PrivateObjectFilterView,
    PublishedObjectFilterView,
    UserCreatedObjectAutocompleteView,
    UserCreatedObjectCreateWithInlinesView,
    UserCreatedObjectDetailView,
    UserCreatedObjectModalDeleteView,
    UserCreatedObjectUpdateWithInlinesView,
)

from .filters import ShowcaseFilterSet
from .forms import (
    ShowcaseMaterialInline,
    ShowcaseModelForm,
    ShowcaseProcessInline,
)
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
    model_name = "Showcase"
    template_name = "closecycleshowcase_map.html"
    filterset_class = ShowcaseFilterSet
    map_title = "CLOSECYCLE Showcases & Pilot Regions"
    features_layer_api_basename = "api-showcase"


class ShowcaseCreateView(UserCreatedObjectCreateWithInlinesView):
    model = Showcase
    form_class = ShowcaseModelForm
    permission_required = "closecycle.add_showcase"
    inlines = [ShowcaseMaterialInline, ShowcaseProcessInline]


class ShowcaseDetailView(MapMixin, UserCreatedObjectDetailView):
    model = Showcase

    def get_catchment_feature_id(self):
        catchment = self.object.visible_catchment(self.request.user)
        return catchment.pk if catchment is not None else None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context.update(
            {
                "visible_catchment": self.object.visible_catchment(user),
                "material_links": self.object.visible_material_links(user),
                "process_chain": self.object.visible_process_chain(user),
                "samples": self.object.visible_samples(user),
                "sample_series": self.object.visible_sample_series(user),
                "scenarios": self.object.visible_scenarios(user),
            }
        )
        return context


class ShowcaseUpdateView(UserCreatedObjectUpdateWithInlinesView):
    model = Showcase
    form_class = ShowcaseModelForm
    inlines = [ShowcaseMaterialInline, ShowcaseProcessInline]


class ShowcaseModalDeleteView(UserCreatedObjectModalDeleteView):
    model = Showcase


class ShowcaseAutocompleteView(UserCreatedObjectAutocompleteView):
    model = Showcase
