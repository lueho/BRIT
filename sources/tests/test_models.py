import importlib
from django.test import SimpleTestCase
from unittest.mock import MagicMock, patch

from case_studies.flexibi_hamburg.models import (
    HamburgGreenAreas as LegacyHamburgGreenAreas,
    HamburgRoadsideTrees as LegacyHamburgRoadsideTrees,
)
from case_studies.flexibi_nantes.models import (
    Culture as LegacyCulture,
    Greenhouse as LegacyGreenhouse,
    GreenhouseGrowthCycle as LegacyGreenhouseGrowthCycle,
    GrowthShare as LegacyGrowthShare,
    GrowthTimeStepSet as LegacyGrowthTimeStepSet,
    NantesGreenhouses as LegacyNantesGreenhouses,
)
from sources.greenhouses.models import (
    Culture,
    Greenhouse,
    GreenhouseGrowthCycle,
    GrowthShare,
    GrowthTimeStepSet,
    NantesGreenhouses,
)
from sources.roadside_trees.models import HamburgGreenAreas, HamburgRoadsideTrees


class SourcesModelAdapterTestCase(SimpleTestCase):
    def test_roadside_tree_model_adapters_reexport_legacy_models(self):
        self.assertIs(HamburgGreenAreas, LegacyHamburgGreenAreas)
        self.assertIs(HamburgRoadsideTrees, LegacyHamburgRoadsideTrees)

    def test_greenhouse_model_adapters_reexport_legacy_models(self):
        self.assertIs(Culture, LegacyCulture)
        self.assertIs(Greenhouse, LegacyGreenhouse)
        self.assertIs(GreenhouseGrowthCycle, LegacyGreenhouseGrowthCycle)
        self.assertIs(GrowthShare, LegacyGrowthShare)
        self.assertIs(GrowthTimeStepSet, LegacyGrowthTimeStepSet)
        self.assertIs(NantesGreenhouses, LegacyNantesGreenhouses)

    def test_greenhouse_selectors_import_greenhouse_from_sources_model_adapter(self):
        from sources.greenhouses import selectors

        greenhouse_model = MagicMock()
        greenhouse_model.objects.filter.return_value.count.return_value = 7

        with patch("sources.greenhouses.models.Greenhouse", greenhouse_model):
            importlib.reload(selectors)

        try:
            self.assertIs(selectors.Greenhouse, greenhouse_model)
            self.assertEqual(selectors.published_greenhouse_count(), 7)
            greenhouse_model.objects.filter.assert_called_once_with(
                publication_status="published"
            )
        finally:
            importlib.reload(selectors)

    def test_roadside_tree_geojson_imports_model_from_sources_adapter(self):
        from sources.roadside_trees import geojson

        roadside_tree_model = object()

        with patch(
            "sources.roadside_trees.models.HamburgRoadsideTrees", roadside_tree_model
        ):
            importlib.reload(geojson)

        try:
            self.assertIs(geojson.HamburgRoadsideTrees, roadside_tree_model)
        finally:
            importlib.reload(geojson)
