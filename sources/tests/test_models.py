import importlib
from unittest.mock import MagicMock, patch

from django.apps import apps
from django.test import SimpleTestCase

from sources.contracts import SourceDomainExport
from sources.greenhouses.models import (
    Culture,
    Greenhouse,
    GreenhouseGrowthCycle,
    GrowthShare,
    GrowthTimeStepSet,
    NantesGreenhouses,
)
from sources.registry import (
    _validate_source_domain_plugin,
    _validate_source_domain_plugins,
    get_source_domain_plugin,
    get_source_domain_plugins,
)
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
                "greenhouses",
                "roadside_trees",
                "urban_green_spaces",
                "waste_collection",
            ),
        )

    def test_registered_source_domain_plugins_can_resolve_app_modules(self):
        self.assertEqual(
            get_source_domain_plugin("greenhouses").get_app_module(),
            "sources.greenhouses",
        )
        self.assertEqual(
            get_source_domain_plugin("waste_collection").get_app_module(),
            "sources.waste_collection",
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

    def test_builtin_source_plugins_publish_export_metadata_through_exports_module(
        self,
    ):
        from sources.greenhouses.exports import EXPORTS as greenhouse_exports
        from sources.roadside_trees.exports import EXPORTS as roadside_exports
        from sources.waste_collection.exports import EXPORTS as waste_collection_exports

        for exports in (
            greenhouse_exports,
            roadside_exports,
            waste_collection_exports,
        ):
            self.assertTrue(exports)
            self.assertTrue(
                all(isinstance(export, SourceDomainExport) for export in exports)
            )


class SourceDomainPluginValidationTestCase(SimpleTestCase):
    def test_validation_rejects_duplicate_plugin_slugs(self):
        duplicate_a = get_source_domain_plugin("greenhouses")
        duplicate_b = get_source_domain_plugin("waste_collection")
        duplicate_b = duplicate_b.__class__(
            slug=duplicate_a.slug,
            verbose_name=duplicate_b.verbose_name,
            app_config=duplicate_b.app_config,
            urlconf=duplicate_b.urlconf,
            capabilities=duplicate_b.capabilities,
            mount_in_hub=duplicate_b.mount_in_hub,
            mount_path=duplicate_b.mount_path,
            published_count_getter=duplicate_b.published_count_getter,
            explorer_card=duplicate_b.explorer_card,
            legacy_redirects=duplicate_b.legacy_redirects,
        )

        with self.assertRaisesMessage(
            ValueError, "Duplicate source-domain plugin slug"
        ):
            _validate_source_domain_plugins((duplicate_a, duplicate_b))

    def test_validation_rejects_duplicate_hub_mount_paths(self):
        roadside_trees = get_source_domain_plugin("roadside_trees")
        greenhouses = get_source_domain_plugin("greenhouses")
        greenhouses = greenhouses.__class__(
            slug=greenhouses.slug,
            verbose_name=greenhouses.verbose_name,
            app_config=greenhouses.app_config,
            urlconf=greenhouses.urlconf,
            capabilities=greenhouses.capabilities,
            mount_in_hub=True,
            mount_path=roadside_trees.mount_path,
            published_count_getter=greenhouses.published_count_getter,
            explorer_card=greenhouses.explorer_card,
            legacy_redirects=greenhouses.legacy_redirects,
        )

        with self.assertRaisesMessage(
            ValueError, "Duplicate source-domain hub mount_path"
        ):
            _validate_source_domain_plugins((roadside_trees, greenhouses))

    def test_validation_rejects_mount_path_without_hub_mount(self):
        plugin = get_source_domain_plugin("greenhouses")
        plugin = plugin.__class__(
            slug=plugin.slug,
            verbose_name=plugin.verbose_name,
            app_config=plugin.app_config,
            urlconf=plugin.urlconf,
            capabilities=plugin.capabilities,
            mount_in_hub=False,
            mount_path="greenhouses/",
            published_count_getter=plugin.published_count_getter,
            explorer_card=plugin.explorer_card,
            legacy_redirects=plugin.legacy_redirects,
        )

        with self.assertRaisesMessage(ValueError, "mount_path requires mount_in_hub"):
            _validate_source_domain_plugin(
                plugin, discovered_app_name="sources.greenhouses"
            )

    def test_validation_rejects_incomplete_explorer_metadata(self):
        plugin = get_source_domain_plugin("greenhouses")
        plugin = plugin.__class__(
            slug=plugin.slug,
            verbose_name=plugin.verbose_name,
            app_config=plugin.app_config,
            urlconf=plugin.urlconf,
            capabilities=plugin.capabilities,
            mount_in_hub=plugin.mount_in_hub,
            mount_path=plugin.mount_path,
            published_count_getter=None,
            explorer_card=plugin.explorer_card,
            legacy_redirects=plugin.legacy_redirects,
        )

        with self.assertRaisesMessage(
            ValueError,
            "explorer_card requires a published_count_getter",
        ):
            _validate_source_domain_plugin(
                plugin, discovered_app_name="sources.greenhouses"
            )

    def test_validation_rejects_app_config_pointing_to_other_app(self):
        plugin = get_source_domain_plugin("greenhouses")
        plugin = plugin.__class__(
            slug=plugin.slug,
            verbose_name=plugin.verbose_name,
            app_config="sources.waste_collection.apps.WasteCollectionConfig",
            urlconf=plugin.urlconf,
            capabilities=plugin.capabilities,
            mount_in_hub=plugin.mount_in_hub,
            mount_path=plugin.mount_path,
            published_count_getter=plugin.published_count_getter,
            explorer_card=plugin.explorer_card,
            legacy_redirects=plugin.legacy_redirects,
        )

        with self.assertRaisesMessage(
            ValueError, "app_config must point back to the discovered app"
        ):
            _validate_source_domain_plugin(
                plugin, discovered_app_name="sources.greenhouses"
            )

    @patch("sources.registry.import_module")
    def test_validation_rejects_exports_capability_without_exports_module(
        self, mock_import_module
    ):
        missing_module = "example.fake.exports"

        def import_side_effect(module_name):
            if module_name == missing_module:
                raise ModuleNotFoundError(name=missing_module)
            return MagicMock()

        mock_import_module.side_effect = import_side_effect

        plugin = get_source_domain_plugin("greenhouses").__class__(
            slug="fake",
            verbose_name="Fake",
            app_config="example.fake.apps.FakeConfig",
            urlconf="example.fake.urls",
            capabilities=("exports",),
        )

        with self.assertRaisesMessage(
            ValueError,
            "declares 'exports' capability but example.fake.exports is missing",
        ):
            _validate_source_domain_plugin(plugin, discovered_app_name="example.fake")


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
