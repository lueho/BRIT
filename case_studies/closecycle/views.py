import re
from collections import defaultdict

from django.db.models import F
from django.http import HttpResponseRedirect

from inventories.models import ScenarioStatus
from layer_manager.models import LayerAggregatedValue
from maps.models import Region
from maps.views import GeoDataSetPublishedFilteredMapView, MapMixin
from materials.models import Sample, SampleSeries
from utils.object_management.permissions import filter_queryset_for_user
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

from .filters import COUNTRY_CHOICES, ShowcaseFilterSet
from .forms import (
    ShowcaseMaterialInline,
    ShowcaseModelForm,
    ShowcaseProcessInline,
)
from .models import Showcase, ShowcaseMaterial
from .themes import PILOT_BOUNDARY_NOTE, PILOT_REGION_ROLE, THEMES, get_theme

CHAIN_STAGES = (
    ("input", "Inputs", "fa-seedling"),
    ("process", "Process steps", "fa-gears"),
    ("intermediate", "Intermediates", "fa-flask"),
    ("product", "Products", "fa-box-open"),
)
HEADLINE_RESULT_LIMIT = 4
MATERIAL_SAMPLE_LIMIT = 5

# ----------- Showcase CRUD --------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class ShowcasePublishedListView(PublishedObjectFilterView):
    model = Showcase
    filterset_class = ShowcaseFilterSet


class ShowcasePrivateFilterView(PrivateObjectFilterView):
    model = Showcase
    filterset_class = ShowcaseFilterSet


def _showcase_list_key(showcase):
    code = showcase.code
    number = int(re.sub(r"\D", "", code)) if code else None
    return (number is None, number or 0, code or "", showcase.title)


def showcase_list_groups(showcases, user):
    """``showcases`` grouped by the country of their region, in code order.

    Showcases whose region ``user`` may not read are listed under "Other".
    """
    countries = dict(COUNTRY_CHOICES)
    visible_regions = set(
        filter_queryset_for_user(
            Region.objects.filter(pk__in={s.region_id for s in showcases}), user
        ).values_list("pk", flat=True)
    )
    groups = {}
    for showcase in sorted(showcases, key=_showcase_list_key):
        visible = showcase.region_id in visible_regions
        country = showcase.region.country if visible else ""
        groups.setdefault(countries.get(country, "Other"), []).append(showcase)
    return [
        {"country": country, "showcases": groups[country]}
        for country in sorted(groups, key=lambda name: (name == "Other", name))
    ]


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
        showcases = list(self.object_list.select_related("region"))
        context.update(
            {
                "closecycle_themes": [get_theme(key) for key in THEMES],
                "showcase_count": len(showcases),
                "showcase_groups": showcase_list_groups(showcases, self.request.user),
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
                "pilot_region_role": PILOT_REGION_ROLE,
                "pilot_boundary_note": PILOT_BOUNDARY_NOTE,
                "material_links": material_links,
                "process_chain": process_chain,
                "chain_stages": chain_stages(material_links, process_chain),
                "samples": self.object.visible_samples(user),
                "sample_series": self.object.visible_sample_series(user),
                "material_sample_groups": material_sample_groups(material_links, user),
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


def _visible_by_material(model, materials, user):
    queryset = filter_queryset_for_user(
        model.objects.filter(material__in=materials), user
    )
    by_material = defaultdict(list)
    for item in queryset.only("id", "name", "material_id").order_by("name", "pk"):
        by_material[item.material_id].append(item)
    return by_material


def material_sample_groups(material_links, user):
    """Visible samples and sample series of each showcase material, in chain order."""
    materials = list(
        {link.material_id: link.material for link in material_links}.values()
    )
    if not materials:
        return []
    samples = _visible_by_material(Sample, materials, user)
    sample_series = _visible_by_material(SampleSeries, materials, user)
    groups = []
    for material in materials:
        material_samples = samples[material.pk]
        if not material_samples and not sample_series[material.pk]:
            continue
        groups.append(
            {
                "material": material,
                "samples": material_samples[:MATERIAL_SAMPLE_LIMIT],
                "more_samples": material_samples[MATERIAL_SAMPLE_LIMIT:],
                "sample_series": sample_series[material.pk],
            }
        )
    return groups


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
    values = (
        LayerAggregatedValue.objects.filter(
            layer__scenario_id__in=evaluated, layer__staged=False
        )
        .select_related("layer__feedstock")
        .order_by("layer__scenario_id", "layer_id", "pk")
    )
    for value in values.annotate(scenario_id=F("layer__scenario_id")):
        results[value.scenario_id].append(value)
    cards = []
    for scenario in scenarios:
        values = results.get(scenario.pk, [])
        cards.append(
            {
                "scenario": scenario,
                "status": statuses.get(scenario.pk),
                "evaluated": scenario.pk in evaluated,
                "several_layers": len({value.layer_id for value in values}) > 1,
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
