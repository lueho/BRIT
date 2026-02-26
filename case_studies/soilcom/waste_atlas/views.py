from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView

WASTE_ATLAS_GROUP_NAME = "waste_atlas"


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

    def get_context_data(self, **kwargs):
        """Pass country, year, and map_title to the template."""
        ctx = super().get_context_data(**kwargs)
        ctx["country"] = self.request.GET.get("country", "DE")
        ctx["year"] = self.request.GET.get("year", "2024")
        ctx["map_title"] = self.map_title
        return ctx


class WasteAtlasOverviewView(WasteAtlasGroupMixin, TemplateView):
    """Overview page linking to all waste atlas maps."""

    template_name = "waste_atlas/overview.html"


class PopulationDensityMapView(AtlasMapView):
    """Karte 20 — Einwohnerdichte."""

    template_name = "waste_atlas/population_density_map.html"
    map_title = "Einwohnerdichte"


class OrgaLevelMapView(AtlasMapView):
    """Karte 1 — Sammlungs-Organisationsebene."""

    template_name = "waste_atlas/karte1_orga_level.html"
    map_title = "Administrative Ebene der Abfallsammlung"


class CollectionSystemMapView(AtlasMapView):
    """Karte 2 — Küchenabfall-Sammelsysteme."""

    template_name = "waste_atlas/karte2_collection_system.html"
    map_title = "Primäres Sammelsystem für Küchenabfälle"


class GreenWasteCollectionSystemCountMapView(AtlasMapView):
    """Karte 21 — Anzahl Grüngut-Sammelsysteme."""

    template_name = "waste_atlas/karte21_green_waste_collection_system_count.html"
    map_title = "Anzahl Grüngut-Sammelsysteme pro Einzugsgebiet"


class ConnectionRateMapView(AtlasMapView):
    """Karte 3 — Anschlussgrad an die Biotonne."""

    template_name = "waste_atlas/karte3_connection_rate.html"
    map_title = "Anschlussgrade an Tür-zu-Tür-Bioabfallsammlungen"


class FoodWasteCategoryMapView(AtlasMapView):
    """Karte 4 — Küchenabfall in der Biotonne."""

    template_name = "waste_atlas/karte4_food_waste_category.html"
    map_title = "Erlaubte Lebensmittelabfälle im Bioabfall"


class PaperBagsMapView(AtlasMapView):
    """Karte 5 — Papierprodukte in Bioabfällen."""

    template_name = "waste_atlas/karte5_paper_bags.html"
    map_title = "Anwendbarkeit von Papiertüten zur Bioabfallsammlung"


class PlasticBagsMapView(AtlasMapView):
    """Karte 6 — Kunststoffbeutel in Bioabfällen."""

    template_name = "waste_atlas/karte6_plastic_bags.html"
    map_title = "Anwendbarkeit von kompostierbaren Kunststoffbeuteln"


class CollectionSupportMapView(AtlasMapView):
    """Karte 7 — Bioabfall-Sammelhilfen."""

    template_name = "waste_atlas/karte7_collection_support.html"
    map_title = "Erlaubte Materialien für Sammelhilfen"


class ResidualFrequencyMapView(AtlasMapView):
    """Karte 8 — Sammelrhythmus Restmüll."""

    template_name = "waste_atlas/karte8_residual_frequency.html"
    map_title = "Sammelrhythmus-Arten der Entsorger zur Restmüllabholung"


class BiowasteFrequencyMapView(AtlasMapView):
    """Karte 9 — Sammelrhythmus Bioabfall."""

    template_name = "waste_atlas/karte9_biowaste_frequency.html"
    map_title = "Sammelrhythmus-Arten der Entsorger zur Bioabfallabholung"


class CombinedFrequencyMapView(AtlasMapView):
    """Karte 10 — Sammelrhythmus in Kombination."""

    template_name = "waste_atlas/karte10_combined_frequency.html"
    map_title = "Sammelrhythmus in Kombination (Bio × Rest)"


class ResidualCollectionCountMapView(AtlasMapView):
    """Karte 11 — Häufigkeit Restmüllabholung."""

    template_name = "waste_atlas/karte11_residual_collection_count.html"
    map_title = "Sammelhäufigkeit der Restmüllabholungen"


class BiowasteCollectionCountMapView(AtlasMapView):
    """Karte 12 — Häufigkeit Bioabfallabholung."""

    template_name = "waste_atlas/karte12_biowaste_collection_count.html"
    map_title = "Sammelhäufigkeit der Bioabfallabholungen"


class CombinedCollectionCountMapView(AtlasMapView):
    """Karte 13 — Sammelhäufigkeit in Kombination."""

    template_name = "waste_atlas/karte13_combined_collection_count.html"
    map_title = "Sammelhäufigkeit in Kombination (Bio × Rest)"


class ResidualFeeSystemMapView(AtlasMapView):
    """Karte 14 — Gebührensysteme Restmüll."""

    template_name = "waste_atlas/karte14_residual_fee_system.html"
    map_title = "Gebührensysteme der Restmüllabholung"


class BiowasteFeeSystemMapView(AtlasMapView):
    """Karte 15 — Gebührensysteme Bioabfall."""

    template_name = "waste_atlas/karte15_biowaste_fee_system.html"
    map_title = "Gebührensysteme der Bioabfallabholung"


class CombinedFeeSystemMapView(AtlasMapView):
    """Karte 16 — Gebührensysteme in Kombination."""

    template_name = "waste_atlas/karte16_combined_fee_system.html"
    map_title = "Gebührensysteme in Kombination (Bio × Rest)"


class ResidualCollectionAmountMapView(AtlasMapView):
    """Karte 17 — Restmüll-Sammelmengen."""

    template_name = "waste_atlas/karte17_residual_collection_amount.html"
    map_title = "Spezifisch gesammelte Menge an Restmüll"


class BiowasteCollectionAmountMapView(AtlasMapView):
    """Karte 18 — Bioabfall-Sammelmengen."""

    template_name = "waste_atlas/karte18_biowaste_collection_amount.html"
    map_title = "Spezifisch gesammelte Menge an Bioabfall"


class GreenWasteCollectionAmountMapView(AtlasMapView):
    """Karte 22 — Grüngut-Sammelmengen."""

    template_name = "waste_atlas/karte22_green_waste_collection_amount.html"
    map_title = "Spezifisch gesammelte Menge an Grüngut"


class OrganicCollectionAmountMapView(AtlasMapView):
    """Karte 27 — Aggregierte Sammelmenge organischer Fraktionen."""

    template_name = "waste_atlas/karte27_organic_collection_amount.html"
    map_title = "Aggregierte Sammelmenge organischer Fraktionen (kg/P/a)"


class OrganicWasteRatioMapView(AtlasMapView):
    """Karte 28 — Verhältnis organischer Fraktionen zu Restabfall."""

    template_name = "waste_atlas/karte28_organic_waste_ratio.html"
    map_title = "Anteil organischer Fraktionen an Gesamtabfall"


class BiowasteMinBinSizeMapView(AtlasMapView):
    """Karte 23 — Mindest-Behältergröße Bioabfall."""

    template_name = "waste_atlas/karte23_biowaste_min_bin_size.html"
    map_title = "Kleinste verfügbare Behältergröße für Bioabfall (L)"


class ResidualMinBinSizeMapView(AtlasMapView):
    """Karte 24 — Mindest-Behältergröße Restmüll."""

    template_name = "waste_atlas/karte24_residual_min_bin_size.html"
    map_title = "Kleinste verfügbare Behältergröße für Restmüll (L)"


class BiowasteRequiredBinCapacityMapView(AtlasMapView):
    """Karte 25 — Mindest-Behältervolumen Bioabfall."""

    template_name = "waste_atlas/karte25_biowaste_required_bin_capacity.html"
    map_title = "Mindest-Behältervolumen für Bioabfall (L/Bezugseinheit)"


class ResidualRequiredBinCapacityMapView(AtlasMapView):
    """Karte 26 — Mindest-Behältervolumen Restmüll."""

    template_name = "waste_atlas/karte26_residual_required_bin_capacity.html"
    map_title = "Mindest-Behältervolumen für Restmüll (L/Bezugseinheit)"


class WasteRatioMapView(AtlasMapView):
    """Karte 19 — Sammelmengen-Verhältnis."""

    template_name = "waste_atlas/karte19_waste_ratio.html"
    map_title = "Verhältnis Bioabfall zu Gesamtabfall"
