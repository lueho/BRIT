import importlib
from django.apps import apps
from django.conf import settings
from django.test import SimpleTestCase
from unittest.mock import MagicMock, patch

from sources.roadside_trees.admin import (
    HamburgGreenAreasAdmin,
    HamburgRoadsideTreesAdmin,
)
from sources.greenhouses.admin import (
    CultureAdmin,
    GreenhouseAdmin,
    GreenhouseGrowthCycleAdmin,
    GrowthShareAdmin,
    GrowthTimeStepSetAdmin,
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
from sources.waste_collection.admin import (
    CollectionAdmin,
    CollectionPropertyValueAdmin,
    CollectorAdmin,
    WasteFlyerAdmin,
)
from sources.waste_collection.models import (
    Collection,
    CollectionPropertyValue,
    Collector,
    WasteFlyer,
)


class SourcesModelAdapterTestCase(SimpleTestCase):
    def test_roadside_tree_models_are_owned_by_sources_modules(self):
        self.assertEqual(HamburgGreenAreas.__module__, "sources.roadside_trees.models")
        self.assertEqual(
            HamburgRoadsideTrees.__module__, "sources.roadside_trees.models"
        )

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
            "sources.legacy_flexibi_hamburg.migrations",
        )

    def test_roadside_tree_admin_is_owned_by_sources_module(self):
        self.assertEqual(
            HamburgRoadsideTreesAdmin.__module__, "sources.roadside_trees.admin"
        )
        self.assertEqual(HamburgGreenAreasAdmin.__module__, "sources.roadside_trees.admin")

    def test_greenhouse_models_are_owned_by_sources_modules(self):
        self.assertEqual(Culture.__module__, "sources.greenhouses.models")
        self.assertEqual(Greenhouse.__module__, "sources.greenhouses.models")
        self.assertEqual(
            GreenhouseGrowthCycle.__module__, "sources.greenhouses.models"
        )
        self.assertEqual(GrowthShare.__module__, "sources.greenhouses.models")
        self.assertEqual(GrowthTimeStepSet.__module__, "sources.greenhouses.models")
        self.assertEqual(NantesGreenhouses.__module__, "sources.greenhouses.models")

    def test_greenhouse_models_use_sources_app_label_and_preserve_db_tables(self):
        self.assertEqual(Culture._meta.app_label, "greenhouses")
        self.assertEqual(Culture._meta.db_table, "flexibi_nantes_culture")
        self.assertEqual(Greenhouse._meta.app_label, "greenhouses")
        self.assertEqual(Greenhouse._meta.db_table, "flexibi_nantes_greenhouse")
        self.assertEqual(GreenhouseGrowthCycle._meta.app_label, "greenhouses")
        self.assertEqual(
            GreenhouseGrowthCycle._meta.db_table,
            "flexibi_nantes_greenhousegrowthcycle",
        )
        self.assertEqual(GrowthTimeStepSet._meta.app_label, "greenhouses")
        self.assertEqual(
            GrowthTimeStepSet._meta.db_table,
            "flexibi_nantes_growthtimestepset",
        )
        self.assertEqual(GrowthShare._meta.app_label, "greenhouses")
        self.assertEqual(GrowthShare._meta.db_table, "flexibi_nantes_growthshare")
        self.assertEqual(NantesGreenhouses._meta.app_label, "greenhouses")
        self.assertEqual(
            NantesGreenhouses._meta.db_table,
            "flexibi_nantes_nantesgreenhouses",
        )

    def test_flexibi_nantes_app_label_is_provided_by_migration_shim(self):
        app_config = apps.get_app_config("flexibi_nantes")

        self.assertEqual(
            app_config.__class__.__module__,
            "sources.legacy_flexibi_nantes.apps",
        )
        self.assertEqual(app_config.name, "sources.legacy_flexibi_nantes")
        self.assertEqual(
            settings.MIGRATION_MODULES["flexibi_nantes"],
            "sources.legacy_flexibi_nantes.migrations",
        )

    def test_greenhouse_admin_is_owned_by_sources_module(self):
        self.assertEqual(CultureAdmin.__module__, "sources.greenhouses.admin")
        self.assertEqual(GreenhouseAdmin.__module__, "sources.greenhouses.admin")
        self.assertEqual(
            GreenhouseGrowthCycleAdmin.__module__, "sources.greenhouses.admin"
        )
        self.assertEqual(GrowthShareAdmin.__module__, "sources.greenhouses.admin")
        self.assertEqual(
            GrowthTimeStepSetAdmin.__module__, "sources.greenhouses.admin"
        )

    def test_waste_collection_models_are_owned_by_sources_modules(self):
        self.assertEqual(Collection.__module__, "sources.waste_collection.models")
        self.assertEqual(
            CollectionPropertyValue.__module__, "sources.waste_collection.models"
        )
        self.assertEqual(Collector.__module__, "sources.waste_collection.models")
        self.assertEqual(WasteFlyer.__module__, "sources.waste_collection.models")

    def test_waste_collection_models_use_sources_app_label_and_preserve_db_tables(self):
        self.assertEqual(Collection._meta.app_label, "waste_collection")
        self.assertEqual(Collection._meta.db_table, "soilcom_collection")
        self.assertEqual(CollectionPropertyValue._meta.app_label, "waste_collection")
        self.assertEqual(
            CollectionPropertyValue._meta.db_table,
            "soilcom_collectionpropertyvalue",
        )
        self.assertEqual(Collector._meta.app_label, "waste_collection")
        self.assertEqual(Collector._meta.db_table, "soilcom_collector")
        self.assertEqual(WasteFlyer._meta.app_label, "waste_collection")
        self.assertTrue(WasteFlyer._meta.proxy)

    def test_soilcom_app_label_is_provided_by_migration_shim(self):
        app_config = apps.get_app_config("soilcom")

        self.assertEqual(app_config.__class__.__module__, "sources.legacy_soilcom.apps")
        self.assertEqual(app_config.name, "sources.legacy_soilcom")
        self.assertEqual(
            settings.MIGRATION_MODULES["soilcom"],
            "sources.legacy_soilcom.migrations",
        )

    def test_waste_collection_admin_is_owned_by_sources_module(self):
        self.assertEqual(CollectionAdmin.__module__, "sources.waste_collection.admin")
        self.assertEqual(
            CollectionPropertyValueAdmin.__module__, "sources.waste_collection.admin"
        )
        self.assertEqual(CollectorAdmin.__module__, "sources.waste_collection.admin")
        self.assertEqual(WasteFlyerAdmin.__module__, "sources.waste_collection.admin")

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
