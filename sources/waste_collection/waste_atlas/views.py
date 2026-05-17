from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.generic import TemplateView

WASTE_ATLAS_GROUP_NAME = "waste_atlas"

ITALY_SOUTH_TYROL_MAP_ROUTES = {
    "orga_level": {
        "IT": "waste-atlas-orga-level-italy-map",
        "IT-ST": "waste-atlas-south-tyrol-orga-level-map",
    },
    "collection_system": {
        "IT": "waste-atlas-italy-collection-system-map",
        "IT-ST": "waste-atlas-south-tyrol-collection-system-map",
    },
    "green_waste_collection_system_count": {
        "IT": "waste-atlas-italy-green-waste-collection-system-count-map",
        "IT-ST": "waste-atlas-south-tyrol-green-waste-collection-system-count-map",
    },
    "collection_count_ratio": {
        "IT-ST": "waste-atlas-south-tyrol-collection-count-ratio-map",
    },
    "collection_point_count": {
        "IT": "waste-atlas-italy-collection-point-count-map",
        "IT-ST": "waste-atlas-south-tyrol-collection-point-count-map",
    },
    "biowaste_collection_point_count": {
        "IT-ST": "waste-atlas-south-tyrol-biowaste-collection-point-count-map",
    },
    "residual_collection_point_count": {
        "IT-ST": "waste-atlas-south-tyrol-residual-collection-point-count-map",
    },
    "collection_point_count_ratio": {
        "IT-ST": "waste-atlas-south-tyrol-collection-point-count-ratio-map",
    },
    "residual_frequency": {
        "IT": "waste-atlas-italy-residual-frequency-map",
        "IT-ST": "waste-atlas-south-tyrol-residual-frequency-map",
    },
    "biowaste_frequency": {
        "IT": "waste-atlas-italy-biowaste-frequency-map",
        "IT-ST": "waste-atlas-south-tyrol-biowaste-frequency-map",
    },
    "combined_frequency": {
        "IT-ST": "waste-atlas-south-tyrol-combined-frequency-map",
    },
    "residual_collection_count": {
        "IT": "waste-atlas-italy-residual-collection-count-map",
        "IT-ST": "waste-atlas-south-tyrol-residual-collection-count-map",
    },
    "biowaste_collection_count": {
        "IT": "waste-atlas-italy-biowaste-collection-count-map",
        "IT-ST": "waste-atlas-south-tyrol-biowaste-collection-count-map",
    },
    "combined_collection_count": {
        "IT-ST": "waste-atlas-south-tyrol-combined-collection-count-map",
    },
    "residual_fee_system": {
        "IT-ST": "waste-atlas-south-tyrol-residual-fee-system-map",
    },
    "biowaste_fee_system": {
        "IT-ST": "waste-atlas-south-tyrol-biowaste-fee-system-map",
    },
    "combined_fee_system": {
        "IT-ST": "waste-atlas-south-tyrol-combined-fee-system-map",
    },
    "residual_collection_amount": {
        "IT": "waste-atlas-italy-residual-collection-amount-map",
        "IT-ST": "waste-atlas-south-tyrol-residual-collection-amount-map",
    },
    "biowaste_collection_amount": {
        "IT": "waste-atlas-italy-biowaste-collection-amount-map",
        "IT-ST": "waste-atlas-south-tyrol-biowaste-collection-amount-map",
    },
    "green_waste_collection_amount": {
        "IT": "waste-atlas-italy-green-waste-collection-amount-map",
        "IT-ST": "waste-atlas-south-tyrol-green-waste-collection-amount-map",
    },
    "organic_collection_amount": {
        "IT": "waste-atlas-italy-organic-collection-amount-map",
        "IT-ST": "waste-atlas-south-tyrol-organic-collection-amount-map",
    },
    "organic_waste_ratio": {
        "IT": "waste-atlas-italy-organic-waste-ratio-map",
        "IT-ST": "waste-atlas-south-tyrol-organic-waste-ratio-map",
    },
    "biowaste_min_bin_size": {
        "IT-ST": "waste-atlas-south-tyrol-biowaste-min-bin-size-map",
    },
    "residual_min_bin_size": {
        "IT-ST": "waste-atlas-south-tyrol-residual-min-bin-size-map",
    },
    "min_bin_size_ratio": {
        "IT-ST": "waste-atlas-south-tyrol-min-bin-size-ratio-map",
    },
}

ITALY_SOUTH_TYROL_MAP_LABELS = {
    "IT": "Italy (IT)",
    "IT-ST": "South Tyrol (ITH10)",
}


class WasteAtlasGroupMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict access to members of the ``waste_atlas`` group."""

    def test_func(self):
        """Return True if the user belongs to the waste_atlas group."""
        return self.request.user.groups.filter(name=WASTE_ATLAS_GROUP_NAME).exists()


class AtlasMapView(WasteAtlasGroupMixin, TemplateView):
    """Base view for all waste atlas choropleth map pages.

    Subclasses set ``template_name`` and ``map_title``.
    Country and year query params are forwarded to the template context.
    Access restricted to members of the ``waste_atlas`` group.
    """

    map_title = ""
    default_country = "DE"
    default_year = "2024"
    default_nuts_prefix = ""
    default_nuts_level = ""
    map_overview_label = "Map overview"
    allow_country_override = True
    allow_nuts_override = True
    map_set = ""
    map_route_key = ""
    map_set_selector_label = "Country"

    def get_country(self):
        if self.allow_country_override:
            return self.request.GET.get("country", self.default_country)
        return self.default_country

    def get_nuts_prefix(self):
        if self.allow_nuts_override:
            return self.request.GET.get("nuts_prefix", self.default_nuts_prefix)
        return self.default_nuts_prefix

    def get_nuts_level(self):
        if self.allow_nuts_override:
            return self.request.GET.get("nuts_level", self.default_nuts_level)
        return self.default_nuts_level

    def get_map_set_options(self):
        routes = ITALY_SOUTH_TYROL_MAP_ROUTES.get(self.map_route_key, {})
        return [
            {
                "value": value,
                "label": ITALY_SOUTH_TYROL_MAP_LABELS[value],
                "url": reverse(route_name),
                "selected": value == self.map_set,
            }
            for value, route_name in routes.items()
        ]

    def get_context_data(self, **kwargs):
        """Pass country, year, nuts_prefix, and map_title to the template."""
        ctx = super().get_context_data(**kwargs)
        ctx["country"] = self.get_country()
        ctx["year"] = self.request.GET.get("year", self.default_year)
        ctx["nuts_prefix"] = self.get_nuts_prefix()
        ctx["nuts_level"] = self.get_nuts_level()
        ctx["map_title"] = self.map_title
        ctx["map_overview_label"] = self.map_overview_label
        ctx["map_set_options"] = self.get_map_set_options()
        ctx["map_set_selector_label"] = self.map_set_selector_label
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


class PopulationDensityMapView(AtlasMapView):
    """Karte 20 — Einwohnerdichte."""

    template_name = "waste_atlas/population_density_map.html"
    map_title = "Population density"


class OrgaLevelMapView(AtlasMapView):
    """Karte 1 — Sammlungs-Organisationsebene."""

    template_name = "waste_atlas/karte1_orga_level.html"
    map_title = "Administrative level of waste collection"


class ItalyAtlasMapView(AtlasMapView):
    default_country = "IT"
    map_overview_label = "Map overview"
    allow_country_override = False
    allow_nuts_override = False
    map_set = "IT"
    map_set_selector_label = "Map set"


class ItalyOrgaLevelMapView(ItalyAtlasMapView):
    template_name = "waste_atlas/karte29_orga_level_italy.html"
    map_title = "Administrative level of waste collection"
    map_route_key = "orga_level"


class ItalyCollectionSystemMapView(ItalyAtlasMapView):
    template_name = "waste_atlas/karte2_collection_system.html"
    map_title = "Primary collection system for kitchen waste"
    map_route_key = "collection_system"


class ItalyGreenWasteCollectionSystemCountMapView(ItalyAtlasMapView):
    template_name = "waste_atlas/karte21_green_waste_collection_system_count.html"
    map_title = "Number of green-waste collection systems per catchment"
    map_route_key = "green_waste_collection_system_count"


class ItalyCollectionPointCountMapView(ItalyAtlasMapView):
    template_name = "waste_atlas/karte44_collection_point_count.html"
    map_title = "Number of collection points"
    map_route_key = "collection_point_count"


class ItalyResidualFrequencyMapView(ItalyAtlasMapView):
    template_name = "waste_atlas/karte8_residual_frequency.html"
    map_title = "Collection frequency types for residual-waste collection"
    map_route_key = "residual_frequency"


class ItalyBiowasteFrequencyMapView(ItalyAtlasMapView):
    template_name = "waste_atlas/karte9_biowaste_frequency.html"
    map_title = "Collection frequency types for biowaste collection"
    map_route_key = "biowaste_frequency"


class ItalyResidualCollectionCountMapView(ItalyAtlasMapView):
    template_name = "waste_atlas/karte11_residual_collection_count.html"
    map_title = "Annual residual-waste collection count"
    map_route_key = "residual_collection_count"


class ItalyBiowasteCollectionCountMapView(ItalyAtlasMapView):
    template_name = "waste_atlas/karte12_biowaste_collection_count.html"
    map_title = "Annual biowaste collection count"
    map_route_key = "biowaste_collection_count"


class ItalyResidualCollectionAmountMapView(ItalyAtlasMapView):
    template_name = "waste_atlas/karte17_residual_collection_amount.html"
    map_title = "Specifically collected amount of residual waste"
    map_route_key = "residual_collection_amount"


class ItalyBiowasteCollectionAmountMapView(ItalyAtlasMapView):
    template_name = "waste_atlas/karte18_biowaste_collection_amount.html"
    map_title = "Specifically collected amount of biowaste"
    map_route_key = "biowaste_collection_amount"


class ItalyGreenWasteCollectionAmountMapView(ItalyAtlasMapView):
    template_name = "waste_atlas/karte22_green_waste_collection_amount.html"
    map_title = "Specifically collected amount of green waste"
    map_route_key = "green_waste_collection_amount"


class ItalyOrganicCollectionAmountMapView(ItalyAtlasMapView):
    template_name = "waste_atlas/karte27_organic_collection_amount.html"
    map_title = "Aggregated collected amount of organic fractions (kg/cap/a)"
    map_route_key = "organic_collection_amount"


class ItalyOrganicWasteRatioMapView(ItalyAtlasMapView):
    template_name = "waste_atlas/karte28_organic_waste_ratio.html"
    map_title = "Share of organic fractions in total waste"
    map_route_key = "organic_waste_ratio"


class SouthTyrolAtlasMapView(AtlasMapView):
    default_country = "IT"
    default_year = "2024"
    default_nuts_prefix = "ITH10"
    default_nuts_level = "3"
    map_overview_label = "Map overview"
    allow_country_override = False
    allow_nuts_override = False
    map_set = "IT-ST"
    map_set_selector_label = "Map set"


class SouthTyrolOrgaLevelMapView(SouthTyrolAtlasMapView):
    template_name = "waste_atlas/karte29_orga_level_italy.html"
    map_title = "Administrative level of waste collection"
    map_route_key = "orga_level"


class SouthTyrolCollectionSystemMapView(SouthTyrolAtlasMapView):
    template_name = "waste_atlas/karte2_collection_system.html"
    map_title = "Primary collection system for kitchen waste"
    map_route_key = "collection_system"


class SouthTyrolGreenWasteCollectionSystemCountMapView(SouthTyrolAtlasMapView):
    template_name = "waste_atlas/karte21_green_waste_collection_system_count.html"
    map_title = "Number of green-waste collection systems per catchment"
    map_route_key = "green_waste_collection_system_count"


class SouthTyrolCollectionCountRatioMapView(SouthTyrolAtlasMapView):
    template_name = "waste_atlas/karte42_collection_count_ratio.html"
    map_title = "Annual collection-count ratio: biowaste vs residual waste"
    map_route_key = "collection_count_ratio"


class SouthTyrolCollectionPointCountMapView(SouthTyrolAtlasMapView):
    template_name = "waste_atlas/karte44_collection_point_count.html"
    map_title = "Number of collection points"
    map_route_key = "collection_point_count"


class SouthTyrolBiowasteCollectionPointCountMapView(SouthTyrolAtlasMapView):
    template_name = "waste_atlas/karte45_biowaste_collection_point_count.html"
    map_title = "Number of biowaste collection points"
    map_route_key = "biowaste_collection_point_count"


class SouthTyrolResidualCollectionPointCountMapView(SouthTyrolAtlasMapView):
    template_name = "waste_atlas/karte46_residual_collection_point_count.html"
    map_title = "Number of residual-waste collection points"
    map_route_key = "residual_collection_point_count"


class SouthTyrolCollectionPointCountRatioMapView(SouthTyrolAtlasMapView):
    template_name = "waste_atlas/karte47_collection_point_count_ratio.html"
    map_title = "Collection points: biowaste vs residual waste"
    map_route_key = "collection_point_count_ratio"


class SouthTyrolResidualFrequencyMapView(SouthTyrolAtlasMapView):
    template_name = "waste_atlas/karte8_residual_frequency.html"
    map_title = "Collection frequency setting for residual-waste collection"
    map_route_key = "residual_frequency"


class SouthTyrolBiowasteFrequencyMapView(SouthTyrolAtlasMapView):
    template_name = "waste_atlas/karte9_biowaste_frequency.html"
    map_title = "Collection frequency setting for biowaste collection"
    map_route_key = "biowaste_frequency"


class SouthTyrolResidualCollectionCountMapView(SouthTyrolAtlasMapView):
    template_name = "waste_atlas/karte11_residual_collection_count.html"
    map_title = "Annual residual-waste collection count"
    map_route_key = "residual_collection_count"


class SouthTyrolBiowasteCollectionCountMapView(SouthTyrolAtlasMapView):
    template_name = "waste_atlas/karte12_biowaste_collection_count.html"
    map_title = "Annual biowaste collection count"
    map_route_key = "biowaste_collection_count"


class SouthTyrolCombinedFrequencyMapView(SouthTyrolAtlasMapView):
    template_name = "waste_atlas/karte10_combined_frequency.html"
    map_title = "Collection frequency setting: biowaste vs residual waste"
    map_route_key = "combined_frequency"


class SouthTyrolCombinedCollectionCountMapView(SouthTyrolAtlasMapView):
    template_name = "waste_atlas/karte13_combined_collection_count.html"
    map_title = "Annual collection count: biowaste vs residual waste"
    map_route_key = "combined_collection_count"


class SouthTyrolResidualFeeSystemMapView(SouthTyrolAtlasMapView):
    template_name = "waste_atlas/karte14_residual_fee_system.html"
    map_title = "Fee system for residual-waste collection"
    map_route_key = "residual_fee_system"


class SouthTyrolBiowasteFeeSystemMapView(SouthTyrolAtlasMapView):
    template_name = "waste_atlas/karte15_biowaste_fee_system.html"
    map_title = "Fee system for biowaste collection"
    map_route_key = "biowaste_fee_system"


class SouthTyrolCombinedFeeSystemMapView(SouthTyrolAtlasMapView):
    template_name = "waste_atlas/karte16_combined_fee_system.html"
    map_title = "Fee system: biowaste vs residual waste"
    map_route_key = "combined_fee_system"


class SouthTyrolResidualCollectionAmountMapView(SouthTyrolAtlasMapView):
    template_name = "waste_atlas/karte17_residual_collection_amount.html"
    map_title = "Specifically collected amount of residual waste"
    map_route_key = "residual_collection_amount"


class SouthTyrolBiowasteCollectionAmountMapView(SouthTyrolAtlasMapView):
    template_name = "waste_atlas/karte18_biowaste_collection_amount.html"
    map_title = "Specifically collected amount of biowaste"
    map_route_key = "biowaste_collection_amount"


class SouthTyrolGreenWasteCollectionAmountMapView(SouthTyrolAtlasMapView):
    template_name = "waste_atlas/karte22_green_waste_collection_amount.html"
    map_title = "Specifically collected amount of green waste"
    map_route_key = "green_waste_collection_amount"


class SouthTyrolOrganicCollectionAmountMapView(SouthTyrolAtlasMapView):
    template_name = "waste_atlas/karte27_organic_collection_amount.html"
    map_title = "Aggregated collected amount of organic fractions (kg/cap/a)"
    map_route_key = "organic_collection_amount"


class SouthTyrolOrganicWasteRatioMapView(SouthTyrolAtlasMapView):
    template_name = "waste_atlas/karte28_organic_waste_ratio.html"
    map_title = "Share of organic fractions in total waste"
    map_route_key = "organic_waste_ratio"


class SouthTyrolBiowasteMinBinSizeMapView(SouthTyrolAtlasMapView):
    template_name = "waste_atlas/karte23_biowaste_min_bin_size.html"
    map_title = "Smallest available bin size for biowaste (L)"
    map_route_key = "biowaste_min_bin_size"


class SouthTyrolResidualMinBinSizeMapView(SouthTyrolAtlasMapView):
    template_name = "waste_atlas/karte24_residual_min_bin_size.html"
    map_title = "Smallest available bin size for residual waste (L)"
    map_route_key = "residual_min_bin_size"


class SouthTyrolMinBinSizeRatioMapView(SouthTyrolAtlasMapView):
    template_name = "waste_atlas/karte43_min_bin_size_ratio.html"
    map_title = "Minimum bin size ratio: biowaste vs residual waste"
    map_route_key = "min_bin_size_ratio"


class SwedenOrgaLevelMapView(AtlasMapView):
    """Map 30 — Organization level of waste collection in Sweden (English)."""

    template_name = "waste_atlas/karte30_orga_level_sweden.html"
    map_title = "Administrative level of waste collection"
    default_country = "SE"
    map_overview_label = "Map overview"


class SwedenBinConfigurationMapView(AtlasMapView):
    """Map 34 — Bin configuration of waste fractions in Sweden (English)."""

    template_name = "waste_atlas/karte34_bin_configuration_sweden.html"
    map_title = "Bin configuration of waste fractions"
    default_country = "SE"
    default_year = "2023"
    map_overview_label = "Map overview"


class DenmarkOrgaLevelMapView(AtlasMapView):
    """Map 31 — Organization level of waste collection in Denmark (English)."""

    template_name = "waste_atlas/karte31_orga_level_denmark.html"
    map_title = "Administrative level of waste collection"
    default_country = "DK"
    default_year = "2023"
    map_overview_label = "Map overview"


class DenmarkAtlasMapView(AtlasMapView):
    default_country = "DK"
    default_year = "2023"
    map_overview_label = "Map overview"
    allow_country_override = False
    allow_nuts_override = False


class DenmarkFoodWasteCategoryMapView(DenmarkAtlasMapView):
    """Map 45 — Accepted food-waste categories in biowaste in Denmark."""

    template_name = "waste_atlas/karte45_food_waste_category_denmark.html"
    map_title = "Accepted food-waste categories in biowaste"


class DenmarkPaperBagsMapView(DenmarkAtlasMapView):
    """Map 46 — Use of paper bags for biowaste collection in Denmark."""

    template_name = "waste_atlas/karte46_paper_bags_denmark.html"
    map_title = "Use of paper bags for biowaste collection"


class DenmarkPlasticBagsMapView(DenmarkAtlasMapView):
    """Map 47 — Use of plastic bags for biowaste collection in Denmark."""

    template_name = "waste_atlas/karte47_plastic_bags_denmark.html"
    map_title = "Use of plastic bags for biowaste collection"


class DenmarkCollectionSupportMapView(DenmarkAtlasMapView):
    """Map 48 — Accepted materials for biowaste collection aids in Denmark."""

    template_name = "waste_atlas/karte48_collection_support_denmark.html"
    map_title = "Accepted materials for collection aids"


class NetherlandsOrgaLevelMapView(AtlasMapView):
    """Map 32 — Organization level of waste collection in the Netherlands (English)."""

    template_name = "waste_atlas/karte32_orga_level_netherlands.html"
    map_title = "Administrative level of waste collection"
    default_country = "NL"
    map_overview_label = "Map overview"


class BelgiumOrgaLevelMapView(AtlasMapView):
    """Map 33 — Organization level of waste collection in Belgium (English)."""

    template_name = "waste_atlas/karte33_orga_level_belgium.html"
    map_title = "Administrative level of waste collection"
    default_country = "BE"
    map_overview_label = "Map overview"


class BelgiumFlandersOrgaLevelMapView(AtlasMapView):
    """Map 35 — Organization level of waste collection in Flanders + Brussels (English)."""

    template_name = "waste_atlas/karte35_orga_level_belgium_flanders.html"
    map_title = "Administrative level of waste collection"
    default_country = "BE"
    default_year = "2022"
    map_overview_label = "Map overview"


class CollectionSystemMapView(AtlasMapView):
    """Karte 2 — Küchenabfall-Sammelsysteme."""

    template_name = "waste_atlas/karte2_collection_system.html"
    map_title = "Primary collection system for kitchen waste"


class GreenWasteCollectionSystemCountMapView(AtlasMapView):
    """Karte 21 — Anzahl Grüngut-Sammelsysteme."""

    template_name = "waste_atlas/karte21_green_waste_collection_system_count.html"
    map_title = "Number of green-waste collection systems per catchment"


class ConnectionRateMapView(AtlasMapView):
    """Karte 3 — Anschlussgrad an die Biotonne."""

    template_name = "waste_atlas/karte3_connection_rate.html"
    map_title = "Connection rates for door-to-door biowaste collection"


class FoodWasteCategoryMapView(AtlasMapView):
    """Karte 4 — Küchenabfall in der Biotonne."""

    template_name = "waste_atlas/karte4_food_waste_category.html"
    map_title = "Accepted food-waste categories in biowaste"


class PaperBagsMapView(AtlasMapView):
    """Karte 5 — Papierprodukte in Bioabfällen."""

    template_name = "waste_atlas/karte5_paper_bags.html"
    map_title = "Use of paper bags for biowaste collection"


class PlasticBagsMapView(AtlasMapView):
    """Karte 6 — Kunststoffbeutel in Bioabfällen."""

    template_name = "waste_atlas/karte6_plastic_bags.html"
    map_title = "Use of compostable plastic bags for biowaste collection"


class CollectionSupportMapView(AtlasMapView):
    """Karte 7 — Bioabfall-Sammelhilfen."""

    template_name = "waste_atlas/karte7_collection_support.html"
    map_title = "Accepted materials for collection aids"


class ResidualFrequencyMapView(AtlasMapView):
    """Karte 8 — Sammelrhythmus Restmüll."""

    template_name = "waste_atlas/karte8_residual_frequency.html"
    map_title = "Collection frequency types for residual-waste collection"


class BiowasteFrequencyMapView(AtlasMapView):
    """Karte 9 — Sammelrhythmus Bioabfall."""

    template_name = "waste_atlas/karte9_biowaste_frequency.html"
    map_title = "Collection frequency types for biowaste collection"


class CombinedFrequencyMapView(AtlasMapView):
    """Karte 10 — Sammelrhythmus in Kombination."""

    template_name = "waste_atlas/karte10_combined_frequency.html"
    map_title = "Collection frequency type: biowaste vs residual waste"


class ResidualCollectionCountMapView(AtlasMapView):
    """Karte 11 — Häufigkeit Restmüllabholung."""

    template_name = "waste_atlas/karte11_residual_collection_count.html"
    map_title = "Annual residual-waste collection count"


class BiowasteCollectionCountMapView(AtlasMapView):
    """Karte 12 — Häufigkeit Bioabfallabholung."""

    template_name = "waste_atlas/karte12_biowaste_collection_count.html"
    map_title = "Annual biowaste collection count"


class CombinedCollectionCountMapView(AtlasMapView):
    """Karte 13 — Sammelhäufigkeit in Kombination."""

    template_name = "waste_atlas/karte13_combined_collection_count.html"
    map_title = "Annual collection count: biowaste vs residual waste"


class CollectionCountRatioMapView(AtlasMapView):
    """Karte 42 — Sammelhäufigkeits-Verhältnis."""

    template_name = "waste_atlas/karte42_collection_count_ratio.html"
    map_title = "Annual collection-count ratio: biowaste vs residual waste"


class ResidualFeeSystemMapView(AtlasMapView):
    """Karte 14 — Gebührensysteme Restmüll."""

    template_name = "waste_atlas/karte14_residual_fee_system.html"
    map_title = "Fee system for residual-waste collection"


class BiowasteFeeSystemMapView(AtlasMapView):
    """Karte 15 — Gebührensysteme Bioabfall."""

    template_name = "waste_atlas/karte15_biowaste_fee_system.html"
    map_title = "Fee system for biowaste collection"


class CombinedFeeSystemMapView(AtlasMapView):
    """Karte 16 — Gebührensysteme in Kombination."""

    template_name = "waste_atlas/karte16_combined_fee_system.html"
    map_title = "Fee system: biowaste vs residual waste"


class ResidualCollectionAmountMapView(AtlasMapView):
    """Karte 17 — Restmüll-Sammelmengen."""

    template_name = "waste_atlas/karte17_residual_collection_amount.html"
    map_title = "Specifically collected amount of residual waste"


class BiowasteCollectionAmountMapView(AtlasMapView):
    """Karte 18 — Bioabfall-Sammelmengen."""

    template_name = "waste_atlas/karte18_biowaste_collection_amount.html"
    map_title = "Specifically collected amount of biowaste"


class GreenWasteCollectionAmountMapView(AtlasMapView):
    """Karte 22 — Grüngut-Sammelmengen."""

    template_name = "waste_atlas/karte22_green_waste_collection_amount.html"
    map_title = "Specifically collected amount of green waste"


class OrganicCollectionAmountMapView(AtlasMapView):
    """Karte 27 — Aggregierte Sammelmenge organischer Fraktionen."""

    template_name = "waste_atlas/karte27_organic_collection_amount.html"
    map_title = "Aggregated collected amount of organic fractions (kg/cap/a)"


class OrganicWasteRatioMapView(AtlasMapView):
    """Karte 28 — Verhältnis organischer Fraktionen zu Restabfall."""

    template_name = "waste_atlas/karte28_organic_waste_ratio.html"
    map_title = "Share of organic fractions in total waste"


class BiowasteMinBinSizeMapView(AtlasMapView):
    """Karte 23 — Mindest-Behältergröße Bioabfall."""

    template_name = "waste_atlas/karte23_biowaste_min_bin_size.html"
    map_title = "Smallest available bin size for biowaste (L)"


class ResidualMinBinSizeMapView(AtlasMapView):
    """Karte 24 — Mindest-Behältergröße Restmüll."""

    template_name = "waste_atlas/karte24_residual_min_bin_size.html"
    map_title = "Smallest available bin size for residual waste (L)"


class BiowasteRequiredBinCapacityMapView(AtlasMapView):
    """Karte 25 — Mindest-Behältervolumen Bioabfall."""

    template_name = "waste_atlas/karte25_biowaste_required_bin_capacity.html"
    map_title = "Required bin capacity for biowaste (L/reference unit)"


class ResidualRequiredBinCapacityMapView(AtlasMapView):
    """Karte 26 — Mindest-Behältervolumen Restmüll."""

    template_name = "waste_atlas/karte26_residual_required_bin_capacity.html"
    map_title = "Required bin capacity for residual waste (L/reference unit)"


class WasteRatioMapView(AtlasMapView):
    """Karte 19 — Sammelmengen-Verhältnis."""

    template_name = "waste_atlas/karte19_waste_ratio.html"
    map_title = "Biowaste share of total waste"


class BwRpAtlasMapView(AtlasMapView):
    """Base view for Baden-Württemberg (DE1) + Rheinland-Pfalz (DEB) case-study maps."""

    default_country = "DE"
    default_nuts_prefix = "DE1,DEB"
    default_nuts_level = "1"
    map_overview_label = "Map overview"
    allow_country_override = False
    allow_nuts_override = False


class BwRpOrgaLevelMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/karte1_orga_level.html"
    map_title = "Administrative level of waste collection"


class BwRpCollectionSystemMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/karte2_collection_system.html"
    map_title = "Primary collection system for kitchen waste"


class BwRpConnectionRateMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/karte3_connection_rate.html"
    map_title = "Connection rates for door-to-door biowaste collection"


class BwRpFoodWasteCategoryMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/karte4_food_waste_category.html"
    map_title = "Accepted food-waste categories in biowaste"


class BwRpPaperBagsMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/karte5_paper_bags.html"
    map_title = "Use of paper bags for biowaste collection"


class BwRpPlasticBagsMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/karte6_plastic_bags.html"
    map_title = "Use of compostable plastic bags for biowaste collection"


class BwRpCollectionSupportMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/karte7_collection_support.html"
    map_title = "Accepted materials for collection aids"


class BwRpGreenWasteCollectionSystemCountMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/karte21_green_waste_collection_system_count.html"
    map_title = "Number of green-waste collection systems per catchment"


class BwRpBiowasteMinBinSizeMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/karte23_biowaste_min_bin_size.html"
    map_title = "Smallest available bin size for biowaste (L)"


class BwRpResidualMinBinSizeMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/karte24_residual_min_bin_size.html"
    map_title = "Smallest available bin size for residual waste (L)"


class BwRpBiowasteRequiredBinCapacityMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/karte25_biowaste_required_bin_capacity.html"
    map_title = "Required bin capacity for biowaste (L/reference unit)"


class BwRpResidualRequiredBinCapacityMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/karte26_residual_required_bin_capacity.html"
    map_title = "Required bin capacity for residual waste (L/reference unit)"


class BwRpResidualFrequencyMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/karte8_residual_frequency.html"
    map_title = "Collection frequency types for residual-waste collection"


class BwRpBiowasteFrequencyMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/karte9_biowaste_frequency.html"
    map_title = "Collection frequency types for biowaste collection"


class BwRpCombinedFrequencyMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/karte10_combined_frequency.html"
    map_title = "Collection frequency type: biowaste vs residual waste"


class BwRpResidualCollectionCountMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/karte11_residual_collection_count.html"
    map_title = "Annual residual-waste collection count"


class BwRpBiowasteCollectionCountMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/karte12_biowaste_collection_count.html"
    map_title = "Annual biowaste collection count"


class BwRpCombinedCollectionCountMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/karte13_combined_collection_count.html"
    map_title = "Annual collection count: biowaste vs residual waste"


class BwRpCollectionCountRatioMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/karte42_collection_count_ratio.html"
    map_title = "Annual collection-count ratio: biowaste vs residual waste"


class BwRpResidualFeeSystemMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/karte14_residual_fee_system.html"
    map_title = "Fee system for residual-waste collection"


class BwRpBiowasteFeeSystemMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/karte15_biowaste_fee_system.html"
    map_title = "Fee system for biowaste collection"


class BwRpCombinedFeeSystemMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/karte16_combined_fee_system.html"
    map_title = "Fee system: biowaste vs residual waste"


class BwRpResidualCollectionAmountMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/karte17_residual_collection_amount.html"
    map_title = "Specifically collected amount of residual waste"


class BwRpBiowasteCollectionAmountMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/karte18_biowaste_collection_amount.html"
    map_title = "Specifically collected amount of biowaste"


class BwRpWasteRatioMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/karte19_waste_ratio.html"
    map_title = "Biowaste share of total waste"


class BwRpPopulationDensityMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/population_density_map.html"
    map_title = "Population density"


class BwRpGreenWasteCollectionAmountMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/karte22_green_waste_collection_amount.html"
    map_title = "Specifically collected amount of green waste"


class BwRpOrganicCollectionAmountMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/karte27_organic_collection_amount.html"
    map_title = "Aggregated collected amount of organic fractions (kg/cap/a)"


class BwRpOrganicWasteRatioMapView(BwRpAtlasMapView):
    template_name = "waste_atlas/karte28_organic_waste_ratio.html"
    map_title = "Share of organic fractions in total waste"


class GermanyAtlasMapView(AtlasMapView):
    """Base view for Germany maps with Bundesländer borders."""

    default_country = "DE"
    default_year = "2024"
    default_nuts_level = "1"  # NUTS-1 = Bundesländer level
    map_overview_label = "Map overview"
    allow_country_override = False
    allow_nuts_override = False
    map_set = "DE"
    map_set_selector_label = "Map set"


class GermanyBWRPAtlasMapView(AtlasMapView):
    """Base view for Germany Baden-Württemberg & Rheinland-Pfalz case study."""

    default_country = "DE"
    default_year = "2024"
    default_nuts_prefix = "DE1,DEB"  # Baden-Württemberg & Rheinland-Pfalz
    default_nuts_level = "1"
    map_overview_label = "Map overview"
    allow_country_override = False
    allow_nuts_override = False
    map_set = "DE-BW-RP"
    map_set_selector_label = "Map set"


class CataloniaAtlasMapView(AtlasMapView):
    default_country = "ES"
    default_year = "2024"
    default_nuts_prefix = "ES51"
    default_nuts_level = "3"
    map_overview_label = "Map overview"
    allow_country_override = False
    allow_nuts_override = False
    map_set = "ES-CT"
    map_set_selector_label = "Map set"


class GermanyOrgaLevelMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte1_orga_level.html"
    map_title = "Administrative level of waste collection"
    map_route_key = "orga_level"


class GermanyBWRPOrgaLevelMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte1_orga_level.html"
    map_title = "Administrative level of waste collection"
    map_route_key = "orga_level"


class GermanyCollectionSystemMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte2_collection_system.html"
    map_title = "Primary collection system for kitchen waste"
    map_route_key = "collection_system"


class CataloniaCollectionSystemMapView(CataloniaAtlasMapView):
    template_name = "waste_atlas/karte2_collection_system.html"
    map_title = "Primary collection system for kitchen waste"
    map_route_key = "collection_system"


class CataloniaAccessControlMapView(CataloniaAtlasMapView):
    template_name = "waste_atlas/access_control.html"
    map_title = "Access control for biowaste collection"
    map_route_key = "access_control"


class GermanyBWRPCollectionSystemMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte2_collection_system.html"
    map_title = "Primary collection system for kitchen waste"
    map_route_key = "collection_system"


class GermanyGreenWasteCollectionSystemCountMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte21_green_waste_collection_system_count.html"
    map_title = "Number of green-waste collection systems per catchment"
    map_route_key = "green_waste_collection_system_count"


class GermanyBWRPGreenWasteCollectionSystemCountMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte21_green_waste_collection_system_count.html"
    map_title = "Number of green-waste collection systems per catchment"
    map_route_key = "green_waste_collection_system_count"


class GermanyCollectionPointCountMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte44_collection_point_count.html"
    map_title = "Number of collection points"
    map_route_key = "collection_point_count"


class GermanyBWRPCollectionPointCountMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte44_collection_point_count.html"
    map_title = "Number of collection points"
    map_route_key = "collection_point_count"


class GermanyConnectionRateMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte3_connection_rate.html"
    map_title = "Connection rates for door-to-door biowaste collection"
    map_route_key = "connection_rate"


class GermanyBWRPConnectionRateMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte3_connection_rate.html"
    map_title = "Connection rates for door-to-door biowaste collection"
    map_route_key = "connection_rate"


class GermanyFoodWasteCategoryMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte4_food_waste_category.html"
    map_title = "Accepted food-waste categories in biowaste"
    map_route_key = "food_waste_category"


class GermanyBWRPFoodWasteCategoryMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte4_food_waste_category.html"
    map_title = "Accepted food-waste categories in biowaste"
    map_route_key = "food_waste_category"


class GermanyPaperBagsMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte5_paper_bags.html"
    map_title = "Use of paper bags for biowaste collection"
    map_route_key = "paper_bags"


class GermanyBWRPPaperBagsMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte5_paper_bags.html"
    map_title = "Use of paper bags for biowaste collection"
    map_route_key = "paper_bags"


class GermanyPlasticBagsMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte6_plastic_bags.html"
    map_title = "Use of compostable plastic bags for biowaste collection"
    map_route_key = "plastic_bags"


class GermanyBWRPPlasticBagsMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte6_plastic_bags.html"
    map_title = "Use of compostable plastic bags for biowaste collection"
    map_route_key = "plastic_bags"


class GermanyCollectionSupportMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte7_collection_support.html"
    map_title = "Accepted materials for collection aids"
    map_route_key = "collection_support"


class GermanyBWRPCollectionSupportMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte7_collection_support.html"
    map_title = "Accepted materials for collection aids"
    map_route_key = "collection_support"


class GermanyResidualFrequencyMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte8_residual_frequency.html"
    map_title = "Collection frequency types for residual-waste collection"
    map_route_key = "residual_frequency"


class GermanyBWRPResidualFrequencyMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte8_residual_frequency.html"
    map_title = "Collection frequency types for residual-waste collection"
    map_route_key = "residual_frequency"


class GermanyBiowasteFrequencyMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte9_biowaste_frequency.html"
    map_title = "Collection frequency types for biowaste collection"
    map_route_key = "biowaste_frequency"


class GermanyBWRPBiowasteFrequencyMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte9_biowaste_frequency.html"
    map_title = "Collection frequency types for biowaste collection"
    map_route_key = "biowaste_frequency"


class GermanyCombinedFrequencyMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte10_combined_frequency.html"
    map_title = "Collection frequency type: biowaste vs residual waste"
    map_route_key = "combined_frequency"


class GermanyBWRPCombinedFrequencyMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte10_combined_frequency.html"
    map_title = "Collection frequency type: biowaste vs residual waste"
    map_route_key = "combined_frequency"


class GermanyResidualCollectionCountMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte11_residual_collection_count.html"
    map_title = "Annual residual-waste collection count"
    map_route_key = "residual_collection_count"


class GermanyBWRPResidualCollectionCountMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte11_residual_collection_count.html"
    map_title = "Annual residual-waste collection count"
    map_route_key = "residual_collection_count"


class GermanyBiowasteCollectionCountMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte12_biowaste_collection_count.html"
    map_title = "Annual biowaste collection count"
    map_route_key = "biowaste_collection_count"


class GermanyBWRPBiowasteCollectionCountMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte12_biowaste_collection_count.html"
    map_title = "Annual biowaste collection count"
    map_route_key = "biowaste_collection_count"


class GermanyCombinedCollectionCountMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte13_combined_collection_count.html"
    map_title = "Annual collection count: biowaste vs residual waste"
    map_route_key = "combined_collection_count"


class GermanyBWRPCombinedCollectionCountMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte13_combined_collection_count.html"
    map_title = "Annual collection count: biowaste vs residual waste"
    map_route_key = "combined_collection_count"


class GermanyCollectionCountRatioMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte42_collection_count_ratio.html"
    map_title = "Annual collection-count ratio: biowaste vs residual waste"
    map_route_key = "collection_count_ratio"


class GermanyBWRPCollectionCountRatioMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte42_collection_count_ratio.html"
    map_title = "Annual collection-count ratio: biowaste vs residual waste"
    map_route_key = "collection_count_ratio"


class GermanyResidualFeeSystemMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte14_residual_fee_system.html"
    map_title = "Fee system for residual-waste collection"
    map_route_key = "residual_fee_system"


class GermanyBWRPResidualFeeSystemMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte14_residual_fee_system.html"
    map_title = "Fee system for residual-waste collection"
    map_route_key = "residual_fee_system"


class GermanyBiowasteFeeSystemMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte15_biowaste_fee_system.html"
    map_title = "Fee system for biowaste collection"
    map_route_key = "biowaste_fee_system"


class GermanyBWRPBiowasteFeeSystemMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte15_biowaste_fee_system.html"
    map_title = "Fee system for biowaste collection"
    map_route_key = "biowaste_fee_system"


class GermanyCombinedFeeSystemMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte16_combined_fee_system.html"
    map_title = "Fee system: biowaste vs residual waste"
    map_route_key = "combined_fee_system"


class GermanyBWRPCombinedFeeSystemMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte16_combined_fee_system.html"
    map_title = "Fee system: biowaste vs residual waste"
    map_route_key = "combined_fee_system"


class GermanyResidualCollectionAmountMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte17_residual_collection_amount.html"
    map_title = "Specifically collected amount of residual waste"
    map_route_key = "residual_collection_amount"


class GermanyBWRPResidualCollectionAmountMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte17_residual_collection_amount.html"
    map_title = "Specifically collected amount of residual waste"
    map_route_key = "residual_collection_amount"


class GermanyBiowasteCollectionAmountMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte18_biowaste_collection_amount.html"
    map_title = "Specifically collected amount of biowaste"
    map_route_key = "biowaste_collection_amount"


class GermanyBWRPBiowasteCollectionAmountMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte18_biowaste_collection_amount.html"
    map_title = "Specifically collected amount of biowaste"
    map_route_key = "biowaste_collection_amount"


class GermanyGreenWasteCollectionAmountMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte22_green_waste_collection_amount.html"
    map_title = "Specifically collected amount of green waste"
    map_route_key = "green_waste_collection_amount"


class GermanyBWRPGreenWasteCollectionAmountMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte22_green_waste_collection_amount.html"
    map_title = "Specifically collected amount of green waste"
    map_route_key = "green_waste_collection_amount"


class GermanyOrganicCollectionAmountMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte27_organic_collection_amount.html"
    map_title = "Aggregated collected amount of organic fractions (kg/cap/a)"
    map_route_key = "organic_collection_amount"


class GermanyBWRPOrganicCollectionAmountMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte27_organic_collection_amount.html"
    map_title = "Aggregated collected amount of organic fractions (kg/cap/a)"
    map_route_key = "organic_collection_amount"


class GermanyOrganicWasteRatioMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte28_organic_waste_ratio.html"
    map_title = "Share of organic fractions in total waste"
    map_route_key = "organic_waste_ratio"


class GermanyBWRPOrganicWasteRatioMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte28_organic_waste_ratio.html"
    map_title = "Share of organic fractions in total waste"
    map_route_key = "organic_waste_ratio"


class GermanyBiowasteMinBinSizeMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte23_biowaste_min_bin_size.html"
    map_title = "Smallest available bin size for biowaste (L)"
    map_route_key = "biowaste_min_bin_size"


class GermanyBWRPBiowasteMinBinSizeMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte23_biowaste_min_bin_size.html"
    map_title = "Smallest available bin size for biowaste (L)"
    map_route_key = "biowaste_min_bin_size"


class GermanyResidualMinBinSizeMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte24_residual_min_bin_size.html"
    map_title = "Smallest available bin size for residual waste (L)"
    map_route_key = "residual_min_bin_size"


class GermanyBWRPResidualMinBinSizeMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte24_residual_min_bin_size.html"
    map_title = "Smallest available bin size for residual waste (L)"
    map_route_key = "residual_min_bin_size"


class GermanyBiowasteRequiredBinCapacityMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte25_biowaste_required_bin_capacity.html"
    map_title = "Required bin capacity for biowaste (L/reference unit)"
    map_route_key = "biowaste_required_bin_capacity"


class GermanyBWRPBiowasteRequiredBinCapacityMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte25_biowaste_required_bin_capacity.html"
    map_title = "Required bin capacity for biowaste (L/reference unit)"
    map_route_key = "biowaste_required_bin_capacity"


class GermanyResidualRequiredBinCapacityMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte26_residual_required_bin_capacity.html"
    map_title = "Required bin capacity for residual waste (L/reference unit)"
    map_route_key = "residual_required_bin_capacity"


class GermanyBWRPResidualRequiredBinCapacityMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte26_residual_required_bin_capacity.html"
    map_title = "Required bin capacity for residual waste (L/reference unit)"
    map_route_key = "residual_required_bin_capacity"


def _build_country_variant_map_view(name, atlas_base_class, inherited_view_class):
    """Create a trivial country-specific atlas view from shared metadata."""

    return type(
        name,
        (atlas_base_class, inherited_view_class),
        {
            "__module__": __name__,
            "template_name": inherited_view_class.template_name,
            "map_title": inherited_view_class.map_title,
            "map_route_key": inherited_view_class.map_route_key,
        },
    )


CATALONIA_GERMANY_VARIANT_VIEWS = (
    ("CataloniaOrgaLevelMapView", GermanyOrgaLevelMapView),
    (
        "CataloniaGreenWasteCollectionSystemCountMapView",
        GermanyGreenWasteCollectionSystemCountMapView,
    ),
    ("CataloniaCollectionPointCountMapView", GermanyCollectionPointCountMapView),
    ("CataloniaConnectionRateMapView", GermanyConnectionRateMapView),
    ("CataloniaFoodWasteCategoryMapView", GermanyFoodWasteCategoryMapView),
    ("CataloniaPaperBagsMapView", GermanyPaperBagsMapView),
    ("CataloniaPlasticBagsMapView", GermanyPlasticBagsMapView),
    ("CataloniaCollectionSupportMapView", GermanyCollectionSupportMapView),
    ("CataloniaResidualFrequencyMapView", GermanyResidualFrequencyMapView),
    ("CataloniaBiowasteFrequencyMapView", GermanyBiowasteFrequencyMapView),
    ("CataloniaCombinedFrequencyMapView", GermanyCombinedFrequencyMapView),
    ("CataloniaResidualCollectionCountMapView", GermanyResidualCollectionCountMapView),
    ("CataloniaBiowasteCollectionCountMapView", GermanyBiowasteCollectionCountMapView),
    ("CataloniaCombinedCollectionCountMapView", GermanyCombinedCollectionCountMapView),
    ("CataloniaCollectionCountRatioMapView", GermanyCollectionCountRatioMapView),
    ("CataloniaResidualFeeSystemMapView", GermanyResidualFeeSystemMapView),
    ("CataloniaBiowasteFeeSystemMapView", GermanyBiowasteFeeSystemMapView),
    ("CataloniaCombinedFeeSystemMapView", GermanyCombinedFeeSystemMapView),
    ("CataloniaResidualCollectionAmountMapView", GermanyResidualCollectionAmountMapView),
    ("CataloniaBiowasteCollectionAmountMapView", GermanyBiowasteCollectionAmountMapView),
    (
        "CataloniaGreenWasteCollectionAmountMapView",
        GermanyGreenWasteCollectionAmountMapView,
    ),
    ("CataloniaOrganicCollectionAmountMapView", GermanyOrganicCollectionAmountMapView),
    ("CataloniaOrganicWasteRatioMapView", GermanyOrganicWasteRatioMapView),
    ("CataloniaBiowasteMinBinSizeMapView", GermanyBiowasteMinBinSizeMapView),
    ("CataloniaResidualMinBinSizeMapView", GermanyResidualMinBinSizeMapView),
    (
        "CataloniaBiowasteRequiredBinCapacityMapView",
        GermanyBiowasteRequiredBinCapacityMapView,
    ),
    (
        "CataloniaResidualRequiredBinCapacityMapView",
        GermanyResidualRequiredBinCapacityMapView,
    ),
)

globals().update(
    {
        view_name: _build_country_variant_map_view(
            view_name,
            CataloniaAtlasMapView,
            inherited_view,
        )
        for view_name, inherited_view in CATALONIA_GERMANY_VARIANT_VIEWS
    }
)


class GermanyWasteRatioMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/karte19_waste_ratio.html"
    map_title = "Biowaste share of total waste"
    map_route_key = "waste_ratio"


class GermanyBWRPWasteRatioMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/karte19_waste_ratio.html"
    map_title = "Biowaste share of total waste"
    map_route_key = "waste_ratio"


class GermanyPopulationDensityMapView(GermanyAtlasMapView):
    template_name = "waste_atlas/population_density_map.html"
    map_title = "Population density"
    map_route_key = "population_density"


class GermanyBWRPPopulationDensityMapView(GermanyBWRPAtlasMapView):
    template_name = "waste_atlas/population_density_map.html"
    map_title = "Population density"
    map_route_key = "population_density"


CataloniaWasteRatioMapView = _build_country_variant_map_view(
    "CataloniaWasteRatioMapView",
    CataloniaAtlasMapView,
    GermanyWasteRatioMapView,
)

CataloniaPopulationDensityMapView = _build_country_variant_map_view(
    "CataloniaPopulationDensityMapView",
    CataloniaAtlasMapView,
    GermanyPopulationDensityMapView,
)


class NetherlandsCollectionSystemMapView(CollectionSystemMapView):
    """Map 36 — Collection system map for the Netherlands entry point."""

    default_country = "NL"
    default_year = "2024"
    map_title = "Primary collection system for kitchen waste"
    map_overview_label = "Map overview"


class NetherlandsBiowasteFrequencyMapView(BiowasteFrequencyMapView):
    """Map 37 — Biowaste frequency map for the Netherlands entry point."""

    default_country = "NL"
    default_year = "2024"
    map_title = "Collection frequency types for biowaste"
    map_overview_label = "Map overview"


class NetherlandsBiowasteCollectionAmountMapView(BiowasteCollectionAmountMapView):
    """Map 38 — Biowaste collection amount map for the Netherlands entry point."""

    default_country = "NL"
    default_year = "2024"
    map_title = "Specifically collected amount of biowaste per person and year"
    map_overview_label = "Map overview"


class NetherlandsOrganicCollectionAmountMapView(OrganicCollectionAmountMapView):
    """Map 39 — Organic collection amount map for the Netherlands entry point."""

    default_country = "NL"
    default_year = "2024"
    map_title = "Aggregated collected amount of organic fractions (kg/p/a)"
    map_overview_label = "Map overview"


class NetherlandsOrganicWasteRatioMapView(OrganicWasteRatioMapView):
    """Map 40 — Organic waste ratio map for the Netherlands entry point."""

    default_country = "NL"
    default_year = "2024"
    map_title = "Share of organic fractions in total waste"
    map_overview_label = "Map overview"
