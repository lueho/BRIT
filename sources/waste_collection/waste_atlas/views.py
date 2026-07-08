from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import Http404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.generic import TemplateView

from .map_selection import (
    MAP_SELECTION_YEARS,
    build_conflict_maps_context,
    build_map_selection_context,
    build_overview_directory_context,
    build_related_maps_context,
    resolve_map_set,
    resolve_overview_region,
)
from .pages import MAP_PAGES, MAP_SET_LABELS

WASTE_ATLAS_GROUP_NAME = "waste_atlas"


def _previous_selection_year(year):
    year = str(year)
    if year in MAP_SELECTION_YEARS:
        index = MAP_SELECTION_YEARS.index(year)
        return MAP_SELECTION_YEARS[index - 1] if index else year
    try:
        return str(int(year) - 1)
    except ValueError:
        return year


class WasteAtlasGroupMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict access to members of the ``waste_atlas`` group."""

    def test_func(self):
        """Return True if the user belongs to the waste_atlas group."""
        return self.request.user.groups.filter(name=WASTE_ATLAS_GROUP_NAME).exists()


class AtlasMapView(WasteAtlasGroupMixin, TemplateView):
    """Generic choropleth map page driven by a ``MAP_PAGES`` entry.

    The page entry (see ``pages.py``) provides the URL, title, region scope,
    selector theme, and the key of the JS map configuration in
    ``map_configs.py``.  ``year`` can always be overridden via query string;
    ``country``/``nuts_*`` only when the page is not locked to a region.
    """

    template_name = "waste_atlas/map.html"
    page = None

    def get_template_names(self):
        return [self.page.get("template", self.template_name)]

    def _get_param(self, key, default):
        if self.page["lock"]:
            return default
        return self.request.GET.get(key, default)

    def get_country(self):
        return self._get_param("country", self.page["country"])

    def get_nuts_prefix(self):
        return self._get_param("nuts_prefix", self.page.get("nuts_prefix", ""))

    def get_nuts_level(self):
        return self._get_param("nuts_level", self.page.get("nuts_level", ""))

    def get_selected_map_set(self):
        if self.page["selector_set"]:
            return self.page["selector_set"]
        return resolve_map_set(
            self.get_country(),
            self.get_nuts_prefix(),
            self.get_nuts_level(),
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        page = self.page
        selected_map_set = self.get_selected_map_set()
        ctx["country"] = self.get_country()
        ctx["year"] = self.request.GET.get("year", page["year"])
        ctx["nuts_prefix"] = self.get_nuts_prefix()
        ctx["nuts_level"] = self.get_nuts_level()
        ctx["map_title"] = page["title"]
        ctx["map_overview_label"] = "Map overview"
        ctx["map_overview_url"] = "waste-atlas-overview"
        region_label = MAP_SET_LABELS.get(selected_map_set, "")
        overview_href = reverse("waste-atlas-overview")
        overview_region_href = f"{overview_href}?region={selected_map_set}"
        ctx["atlas_map_set"] = selected_map_set
        ctx["atlas_region_label"] = region_label
        ctx["atlas_overview_href"] = overview_href
        ctx["atlas_overview_region_href"] = overview_region_href
        ctx["atlas_overview_region_tab"] = resolve_overview_region(selected_map_set)
        ctx["breadcrumb_module_label"] = "Waste Atlas"
        ctx["breadcrumb_module_url"] = overview_href
        if region_label:
            ctx["breadcrumb_section_label"] = region_label
            ctx["breadcrumb_section_url"] = overview_region_href
        ctx["breadcrumb_object_label"] = page["title"]
        ctx["map_config_key"] = page["config_key"]
        ctx["map_config_overrides"] = page.get("overrides")
        ctx.update(
            build_map_selection_context(
                reverse,
                selected_map_set=selected_map_set,
                selected_theme=page["theme"],
            )
        )
        ctx.update(build_related_maps_context(selected_map_set, page["theme"], reverse))
        selected_theme_option = next(
            (
                theme
                for theme in ctx["map_selection_themes_by_map_set"].get(
                    selected_map_set, []
                )
                if theme["value"] == page["theme"]
            ),
            None,
        )
        ctx["is_change_map"] = False
        change_url = (
            selected_theme_option["change_url"] if selected_theme_option else ""
        )
        ctx["map_toggle_url"] = (
            f"{change_url}?from_year={_previous_selection_year(ctx['year'])}&to_year={ctx['year']}"
            if change_url
            else ""
        )
        ctx["map_toggle_label"] = "View changes for this map"
        return ctx


class AtlasChangeMapView(AtlasMapView):
    """Generic change map comparing a map theme between two years.

    The page entry is resolved from the ``map_set``/``theme`` URL kwargs.
    The client fetches the theme's data endpoint for both years. Numeric
    themes are classified by value difference; categorical themes are
    classified as no-change/changed/new/removed.
    Supports ``from_year`` and ``to_year`` query params.
    """

    template_name = "waste_atlas/change_map.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.page = self._resolve_page(kwargs["map_set"], kwargs["theme"])

    @staticmethod
    def _resolve_page(map_set, theme):
        for page in MAP_PAGES:
            if page["selector_set"] == map_set and page["theme"] == theme:
                return page
        raise Http404(f"No waste atlas map for {map_set}/{theme}")

    def get_template_names(self):
        return [self.template_name]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["map_overview_url"] = "waste-atlas-change-map-overview"
        ctx["from_year"] = self.request.GET.get("from_year", "2024")
        ctx["to_year"] = self.request.GET.get("to_year", "2024")
        ctx["year"] = ctx["to_year"]
        ctx["default_from_year"] = ctx["from_year"]
        ctx["default_to_year"] = ctx["to_year"]
        ctx["map_title"] = f"{self.page['title']} — changes"
        ctx["breadcrumb_object_label"] = ctx["map_title"]
        ctx["is_change_map"] = True
        ctx["map_toggle_url"] = reverse(self.page["name"])
        ctx["map_toggle_label"] = "View current map"
        return ctx


class WasteAtlasOverviewView(WasteAtlasGroupMixin, TemplateView):
    """Overview page linking to all waste atlas maps."""

    template_name = "waste_atlas/overview.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["selected_required_bin_capacity_reference"] = self.request.GET.get(
            "required_bin_capacity_reference",
            "person",
        )
        ctx.update(
            build_overview_directory_context(
                reverse,
                selected_region=self.request.GET.get("region"),
            )
        )
        ctx["directory_selected_category"] = self.request.GET.get("category", "")
        ctx["directory_query"] = self.request.GET.get("q", "")
        return ctx


class WasteAtlasChangeMapOverviewView(WasteAtlasGroupMixin, TemplateView):
    """Overview page for change maps — compare two versions of a waste atlas map."""

    template_name = "waste_atlas/change_map_overview.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        selection_ctx = build_map_selection_context(reverse)
        years = list(selection_ctx["map_selection_years"])
        ctx.update(selection_ctx)
        ctx["default_from_year"] = self.request.GET.get(
            "from_year", years[-1] if years else "2024"
        )
        ctx["default_to_year"] = self.request.GET.get(
            "to_year", years[-1] if years else "2024"
        )
        return ctx


class WasteAtlasDataConflictsOverviewView(WasteAtlasGroupMixin, TemplateView):
    """Overview page listing maps with the maintainer conflict-overlay aid.

    Surfaces every choropleth map whose ``MAP_CONFIGS`` entry opts into the
    conflict overlay (``conflictUrl``) so data maintainers can find maps that
    highlight catchments where the dataset holds conflicting theme values.
    """

    template_name = "waste_atlas/data_conflicts_overview.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(build_conflict_maps_context(reverse))
        return ctx


class EuropeDataCoverageContextMixin:
    """Provide shared context for the Europe coverage map page variants."""

    template_name = "waste_atlas/karte0_europe_data_coverage.html"
    base_template = "base.html"
    iframe_mode = False

    def get_context_data(self, **kwargs):
        """Provide page title, layout mode, and overview label context."""
        ctx = super().get_context_data(**kwargs)
        ctx["map_title"] = "Waste collection data coverage in Europe"
        ctx["map_overview_label"] = "Map overview"
        ctx["base_template"] = self.base_template
        ctx["iframe_mode"] = self.iframe_mode
        return ctx


class EuropeDataCoverageMapView(
    WasteAtlasGroupMixin, EuropeDataCoverageContextMixin, TemplateView
):
    """Map 0 — Waste collection data coverage in Europe."""


@method_decorator(xframe_options_exempt, name="dispatch")
class EuropeDataCoverageMapIframeView(EuropeDataCoverageContextMixin, TemplateView):
    """Iframe-friendly Europe coverage map for third-party embedding."""

    template_name = "waste_atlas/karte0_europe_data_coverage_iframe.html"
    base_template = "base_iframe.html"
    iframe_mode = True


class EuropeBiowasteCollectionAmountMapView(WasteAtlasGroupMixin, TemplateView):
    template_name = "waste_atlas/karte41_europe_biowaste_collection_amount.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["map_title"] = (
            "Regional average amount of separately collected biowaste in Europe"
        )
        ctx["map_overview_label"] = "Map overview"
        ctx["year"] = "2024"
        return ctx
