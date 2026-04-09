import importlib
from unittest.mock import MagicMock, patch

from django.apps import apps
from django.test import SimpleTestCase

from sources.greenhouses.models import (
    Culture,
    Greenhouse,
    GreenhouseGrowthCycle,
    GrowthShare,
    GrowthTimeStepSet,
    NantesGreenhouses,
)
from sources.registry import get_source_domain_plugin, get_source_domain_plugins
from sources.roadside_trees.models import HamburgRoadsideTrees
from sources.urban_green_spaces.models import HamburgGreenAreas
from sources.waste_collection.models import (
    Collection,
    CollectionPropertyValue,
    Collector,
    WasteFlyer,
)


class SourceDomainPluginContractTestCase(SimpleTestCase):
    def test_registered_source_domain_plugins_expose_stable_slugs(self):
        self.assertEqual(
            tuple(plugin.slug for plugin in get_source_domain_plugins()),
            (
                "roadside_trees",
                "urban_green_spaces",
                "greenhouses",
                "waste_collection",
            ),
        )

    def test_registered_source_domain_plugins_declare_app_configs(self):
        self.assertEqual(
            get_source_domain_plugin("roadside_trees").app_config,
            "sources.roadside_trees.apps.RoadsideTreesConfig",
        )
        self.assertEqual(
            get_source_domain_plugin("urban_green_spaces").app_config,
            "sources.urban_green_spaces.apps.UrbanGreenSpacesConfig",
        )
        self.assertEqual(
            get_source_domain_plugin("greenhouses").app_config,
            "sources.greenhouses.apps.GreenhousesConfig",
        )
        self.assertEqual(
            get_source_domain_plugin("waste_collection").app_config,
            "sources.waste_collection.apps.WasteCollectionConfig",
        )

    def test_registered_source_domain_plugins_expose_urlconfs(self):
        for slug in (
            "roadside_trees",
            "urban_green_spaces",
            "greenhouses",
            "waste_collection",
        ):
            self.assertTrue(get_source_domain_plugin(slug).get_urlpatterns())

    def test_registered_source_domain_plugins_declare_capabilities(self):
        self.assertIn(
            "legacy_redirects",
            get_source_domain_plugin("roadside_trees").capabilities,
        )
        self.assertIn(
            "legacy_redirects",
            get_source_domain_plugin("urban_green_spaces").capabilities,
        )
        self.assertIn("forms", get_source_domain_plugin("greenhouses").capabilities)
        self.assertIn(
            "signals",
            get_source_domain_plugin("waste_collection").capabilities,
        )


class SourcesModelAdapterTestCase(SimpleTestCase):
    def test_roadside_tree_models_use_sources_app_label_and_preserve_db_tables(self):
        self.assertEqual(
            apps.get_app_config("roadside_trees").name,
            "sources.roadside_trees",
        )
        self.assertEqual(HamburgRoadsideTrees._meta.app_label, "roadside_trees")
        self.assertEqual(
            HamburgRoadsideTrees._meta.db_table,
            "roadside_trees_hamburgroadsidetrees",
        )

    def test_urban_green_spaces_model_uses_new_app_label_and_preserves_db_table(self):
        self.assertEqual(
            apps.get_app_config("urban_green_spaces").name,
            "sources.urban_green_spaces",
        )
        self.assertEqual(HamburgGreenAreas._meta.app_label, "urban_green_spaces")
        self.assertEqual(
            HamburgGreenAreas._meta.db_table,
            "urban_green_spaces_hamburggreenareas",
        )

    def test_greenhouse_models_use_sources_app_label(self):
        self.assertEqual(apps.get_app_config("greenhouses").name, "sources.greenhouses")
        self.assertEqual(Culture._meta.app_label, "greenhouses")
        self.assertEqual(Greenhouse._meta.app_label, "greenhouses")
        self.assertEqual(GreenhouseGrowthCycle._meta.app_label, "greenhouses")
        self.assertEqual(GrowthTimeStepSet._meta.app_label, "greenhouses")
        self.assertEqual(GrowthShare._meta.app_label, "greenhouses")
        self.assertEqual(NantesGreenhouses._meta.app_label, "greenhouses")
        # Table names use Django's implicit naming: greenhouses_<modelname>

    def test_waste_collection_models_use_sources_app_label_and_preserve_db_tables(self):
        self.assertEqual(
            apps.get_app_config("waste_collection").name,
            "sources.waste_collection",
        )
        self.assertEqual(Collection._meta.app_label, "waste_collection")
        self.assertEqual(Collection._meta.db_table, "waste_collection_collection")
        self.assertEqual(CollectionPropertyValue._meta.app_label, "waste_collection")
        self.assertEqual(
            CollectionPropertyValue._meta.db_table,
            "waste_collection_collectionpropertyvalue",
        )
        self.assertEqual(Collector._meta.app_label, "waste_collection")
        self.assertEqual(Collector._meta.db_table, "waste_collection_collector")
        self.assertEqual(WasteFlyer._meta.app_label, "waste_collection")
        self.assertTrue(WasteFlyer._meta.proxy)

    def test_waste_collection_app_config_is_owned_by_sources(self):
        self.assertEqual(
            apps.get_app_config("waste_collection").name,
            "sources.waste_collection",
        )

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

    def test_waste_collection_selectors_import_collection_from_sources_model_adapter(
        self,
    ):
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
