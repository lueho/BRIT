from django.db.models import F

from inventories.models import ScenarioStatus
from layer_manager.models import LayerAggregatedValue
from maps.views import GeoDataSetPublishedFilteredMapView, MapMixin
from utils.object_management.views import (
    PrivateObjectFilterView,
    PublishedObjectFilterView,
    ReviewItemDetailView,
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
from .models import Showcase, ShowcaseMaterial

CHAIN_STAGES = (
    ("input", "Inputs", "fa-seedling"),
    ("process", "Process steps", "fa-gears"),
    ("intermediate", "Intermediates", "fa-flask"),
    ("product", "Products", "fa-box-open"),
)
HEADLINE_RESULT_LIMIT = 4

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

    def get_region_feature_id(self):
        region = self.object.visible_region(self.request.user)
        return region.pk if region is not None else None

    def get_catchment_feature_id(self):
        catchment = self.object.visible_catchment(self.request.user)
        return catchment.pk if catchment is not None else None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        material_links = self.object.visible_material_links(user)
        process_chain = self.object.visible_process_chain(user)
        scenarios = self.object.visible_scenarios(user)
        context.update(
            {
                "visible_region": self.object.visible_region(user),
                "visible_catchment": self.object.visible_catchment(user),
                "material_links": material_links,
                "process_chain": process_chain,
                "chain_stages": chain_stages(material_links, process_chain),
                "samples": self.object.visible_samples(user),
                "sample_series": self.object.visible_sample_series(user),
                "scenarios": scenarios,
                "scenario_cards": scenario_cards(scenarios),
            }
        )
        return context


class ShowcaseReviewItemDetailView(ReviewItemDetailView):
    """Render showcase moderation with the complete showcase detail context."""

    model = Showcase
    detail_view_class = ShowcaseDetailView


ShowcaseReviewItemDetailView.register_for_model(Showcase)


def chain_stages(material_links, process_chain):
    """Non-empty stages of the processing chain in flow order."""
    items = {role: [] for role in ShowcaseMaterial.Role.values}
    for link in material_links:
        items[link.role].append(link.material)
    items["process"] = list(process_chain)
    return [
        {"key": key, "label": label, "icon": icon, "items": items[key]}
        for key, label, icon in CHAIN_STAGES
        if items[key]
    ]


def scenario_cards(scenarios):
    """Scenarios with their status and, once evaluated, their headline results."""
    statuses = dict(
        ScenarioStatus.objects.filter(scenario__in=scenarios).values_list(
            "scenario_id", "status"
        )
    )
    evaluated = {
        pk
        for pk, status in statuses.items()
        if status == ScenarioStatus.Status.FINISHED
    }
    results = {pk: [] for pk in evaluated}
    values = LayerAggregatedValue.objects.filter(
        layer__scenario_id__in=evaluated, layer__staged=False
    ).order_by("layer__scenario_id", "layer_id", "pk")
    for value in values.annotate(scenario_id=F("layer__scenario_id")):
        results[value.scenario_id].append(value)
    cards = []
    for scenario in scenarios:
        values = results.get(scenario.pk, [])
        cards.append(
            {
                "scenario": scenario,
                "evaluated": scenario.pk in evaluated,
                "results": values[:HEADLINE_RESULT_LIMIT],
                "more_results": max(len(values) - HEADLINE_RESULT_LIMIT, 0),
            }
        )
    return cards


class ShowcaseUpdateView(UserCreatedObjectUpdateWithInlinesView):
    model = Showcase
    form_class = ShowcaseModelForm
    inlines = [ShowcaseMaterialInline, ShowcaseProcessInline]


class ShowcaseModalDeleteView(UserCreatedObjectModalDeleteView):
    model = Showcase


class ShowcaseAutocompleteView(UserCreatedObjectAutocompleteView):
    model = Showcase
