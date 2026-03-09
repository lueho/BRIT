import importlib
from django.apps import apps
from django.conf import settings
from django.test import SimpleTestCase
from unittest.mock import MagicMock, patch

from case_studies.flexibi_hamburg.admin import (
    HamburgGreenAreasAdmin as LegacyHamburgGreenAreasAdmin,
    HamburgRoadsideTreesAdmin as LegacyHamburgRoadsideTreesAdmin,
)
from case_studies.flexibi_hamburg.models import (
    HamburgGreenAreas as LegacyHamburgGreenAreas,
    HamburgRoadsideTrees as LegacyHamburgRoadsideTrees,
)
from sources.roadside_trees.admin import (
    HamburgGreenAreasAdmin,
    HamburgRoadsideTreesAdmin,
)
from case_studies.flexibi_nantes.models import (
    Culture as LegacyCulture,
    Greenhouse as LegacyGreenhouse,
    GreenhouseGrowthCycle as LegacyGreenhouseGrowthCycle,
    GrowthShare as LegacyGrowthShare,
    GrowthTimeStepSet as LegacyGrowthTimeStepSet,
    NantesGreenhouses as LegacyNantesGreenhouses,
)
from case_studies.soilcom.models import (
    Collection as LegacyCollection,
    CollectionPropertyValue as LegacyCollectionPropertyValue,
    Collector as LegacyCollector,
    WasteFlyer as LegacyWasteFlyer,
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
from sources.waste_collection.models import (
    Collection,
    CollectionPropertyValue,
    Collector,
    WasteFlyer,
)


class SourcesModelAdapterTestCase(SimpleTestCase):
    def test_roadside_tree_model_adapters_reexport_legacy_models(self):
        self.assertIs(HamburgGreenAreas, LegacyHamburgGreenAreas)
        self.assertIs(HamburgRoadsideTrees, LegacyHamburgRoadsideTrees)

    def test_roadside_tree_models_use_sources_app_label_and_preserve_db_tables(self):
        self.assertEqual(HamburgGreenAreas._meta.app_label, "roadside_trees")
        self.assertEqual(
            HamburgGreenAreas._meta.db_table,
            "flexibi_hamburg_hamburggreenareas",
        )
        self.assertEqual(HamburgRoadsideTrees._meta.app_label, "roadside_trees")
        self.assertEqual(
            HamburgRoadsideTrees._meta.db_table,
            "flexibi_hamburg_hamburgroadsidetrees",
        )

    def test_flexibi_hamburg_app_label_is_provided_by_migration_shim(self):
        app_config = apps.get_app_config("flexibi_hamburg")

        self.assertEqual(app_config.name, "sources.legacy_flexibi_hamburg")
        self.assertEqual(
            settings.MIGRATION_MODULES["flexibi_hamburg"],
            "case_studies.flexibi_hamburg.migrations",
        )

    def test_roadside_tree_admin_adapters_reexport_source_owned_admin(self):
        self.assertIs(HamburgRoadsideTreesAdmin, LegacyHamburgRoadsideTreesAdmin)
        self.assertIs(HamburgGreenAreasAdmin, LegacyHamburgGreenAreasAdmin)

    def test_greenhouse_model_adapters_reexport_legacy_models(self):
        self.assertIs(Culture, LegacyCulture)
        self.assertIs(Greenhouse, LegacyGreenhouse)
        self.assertIs(GreenhouseGrowthCycle, LegacyGreenhouseGrowthCycle)
        self.assertIs(GrowthShare, LegacyGrowthShare)
        self.assertIs(GrowthTimeStepSet, LegacyGrowthTimeStepSet)
        self.assertIs(NantesGreenhouses, LegacyNantesGreenhouses)

    def test_waste_collection_model_adapters_reexport_legacy_models(self):
        self.assertIs(Collection, LegacyCollection)
        self.assertIs(CollectionPropertyValue, LegacyCollectionPropertyValue)
        self.assertIs(Collector, LegacyCollector)
        self.assertIs(WasteFlyer, LegacyWasteFlyer)

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

    def test_waste_collection_selectors_import_collection_from_sources_model_adapter(self):
        from sources.waste_collection import selectors

        collection_model = MagicMock()
        collection_model.objects.none.return_value = []
        collection_model.objects.filter.return_value.count.return_value = 11

        with patch("sources.waste_collection.models.Collection", collection_model):
            importlib.reload(selectors)

        try:
            self.assertIs(selectors.Collection, collection_model)
            self.assertEqual(selectors.empty_collection_queryset(), [])
            self.assertEqual(selectors.published_collection_count(), 11)
            collection_model.objects.none.assert_called_once_with()
            collection_model.objects.filter.assert_called_once_with(
                publication_status="published"
            )
        finally:
            importlib.reload(selectors)

    def test_waste_collection_geojson_imports_model_from_sources_adapter(self):
        from sources.waste_collection import geojson

        collection_model = object()

        with patch("sources.waste_collection.models.Collection", collection_model):
            importlib.reload(geojson)

        try:
            self.assertIs(geojson.Collection, collection_model)
        finally:
            importlib.reload(geojson)
