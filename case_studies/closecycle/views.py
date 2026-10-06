from django.http import HttpResponseRedirect

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
from .themes import PILOT_BOUNDARY_NOTE, PILOT_REGION_ROLE, THEMES, get_theme

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

    def get(self, request, *args, **kwargs):
        # The features API only restricts visibility when ``scope`` is present.
        if request.GET and "scope" not in request.GET:
            params = request.GET.copy()
            params["scope"] = "published"
            return HttpResponseRedirect(f"{request.path}?{params.urlencode()}")
        return super().get(request, *args, **kwargs)

    def post_process_map_config(self, map_config):
        config = super().post_process_map_config(map_config)
        config["applyFilterToFeatures"] = False
        config["adjustBoundsToLayer"] = "features"
        if "load_features" not in self.request.GET:
            config["loadFeatures"] = bool(config.get("featuresLayerGeometriesUrl"))
        return config

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "closecycle_themes": [get_theme(key) for key in THEMES],
                "pilot_region_role": PILOT_REGION_ROLE,
                "pilot_boundary_note": PILOT_BOUNDARY_NOTE,
            }
        )
        return context


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
                "pilot_region_role": PILOT_REGION_ROLE,
                "pilot_boundary_note": PILOT_BOUNDARY_NOTE,
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
