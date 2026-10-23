from unittest.mock import MagicMock

from django.contrib.auth.models import User
from django.test import SimpleTestCase

from utils.file_export.contracts import SourceDomainExport

from ..export_registry import (
    EXPORT_REGISTRY,
    ExportSpec,
    get_export_spec,
    register_export,
)


class ExportRegistryTestCase(SimpleTestCase):
    """Tests for the export registry functions."""

    def setUp(self):
        self._original_registry = EXPORT_REGISTRY.copy()

    def tearDown(self):
        EXPORT_REGISTRY.clear()
        EXPORT_REGISTRY.update(self._original_registry)

    def test_register_and_retrieve_spec(self):
        """Registered spec can be retrieved by label."""
        filterset = MagicMock()
        serializer = MagicMock()
        renderers = {"csv": MagicMock()}

        register_export("auth.User", filterset, serializer, renderers)

        spec = get_export_spec("auth.User")
        self.assertIsInstance(spec, ExportSpec)
        self.assertIs(spec.model, User)
        self.assertIs(spec.filterset, filterset)
        self.assertIs(spec.serializer, serializer)
        self.assertEqual(spec.renderers, renderers)

    def test_material_sample_export_registers_renderer_classes(self):
        import materials.exports  # noqa: F401
        from materials.renderers import SampleCSVRenderer, SampleXLSXRenderer

        spec = get_export_spec("materials.Sample")

        self.assertIs(spec.renderers["csv"], SampleCSVRenderer)
        self.assertIs(spec.renderers["xlsx"], SampleXLSXRenderer)

    def test_greenhouses_export_is_registered(self):
        from sources.greenhouses.filters import NantesGreenhousesFilterSet
        from sources.greenhouses.renderers import (
            NantesGreenhousesCSVRenderer,
            NantesGreenhousesXLSXRenderer,
        )
        from sources.greenhouses.serializers import NantesGreenhousesFlatSerializer

        spec = get_export_spec("greenhouses.NantesGreenhouses")

        self.assertIs(spec.filterset, NantesGreenhousesFilterSet)
        self.assertIs(spec.serializer, NantesGreenhousesFlatSerializer)
        self.assertIs(spec.renderers["csv"], NantesGreenhousesCSVRenderer)
        self.assertIs(spec.renderers["xlsx"], NantesGreenhousesXLSXRenderer)

    def test_roadside_trees_export_is_registered(self):
        from sources.roadside_trees.filters import HamburgRoadsideTreesFilterSet
        from sources.roadside_trees.renderers import (
            HamburgRoadsideTreesCSVRenderer,
            HamburgRoadsideTreesXLSXRenderer,
        )
        from sources.roadside_trees.serializers import HamburgRoadsideTreeFlatSerializer

        spec = get_export_spec("roadside_trees.HamburgRoadsideTrees")

        self.assertIs(spec.filterset, HamburgRoadsideTreesFilterSet)
        self.assertIs(spec.serializer, HamburgRoadsideTreeFlatSerializer)
        self.assertIs(spec.renderers["csv"], HamburgRoadsideTreesCSVRenderer)
        self.assertIs(spec.renderers["xlsx"], HamburgRoadsideTreesXLSXRenderer)

    def test_waste_collection_export_is_registered(self):
        from sources.waste_collection.filters import CollectionFilterSet
        from sources.waste_collection.renderers import (
            CollectionCSVRenderer,
            CollectionXLSXRenderer,
        )
        from sources.waste_collection.serializers import CollectionFlatSerializer

        spec = get_export_spec("waste_collection.Collection")

        self.assertIs(spec.filterset, CollectionFilterSet)
        self.assertIs(spec.serializer, CollectionFlatSerializer)
        self.assertIs(spec.renderers["csv"], CollectionCSVRenderer)
        self.assertIs(spec.renderers["xlsx"], CollectionXLSXRenderer)

    def test_get_unknown_label_raises_key_error(self):
        """Requesting an unregistered label should raise KeyError."""
        with self.assertRaises(KeyError):
            get_export_spec("nonexistent.Model")

    def test_register_overwrites_existing_entry(self):
        """Re-registering the same label should overwrite the previous entry."""
        register_export("auth.User", MagicMock(), MagicMock(), {})
        new_serializer = MagicMock()
        register_export("auth.User", MagicMock(), new_serializer, {})

        spec = get_export_spec("auth.User")
        self.assertIs(spec.serializer, new_serializer)

    def test_source_domain_export_contract_carries_registry_arguments(self):
        filterset = object()
        serializer = object()
        renderers = {"xlsx": object(), "csv": object()}

        export = SourceDomainExport(
            model_label="greenhouses.NantesGreenhouses",
            filterset=filterset,
            serializer=serializer,
            renderers=renderers,
        )

        self.assertEqual(export.model_label, "greenhouses.NantesGreenhouses")
        self.assertIs(export.filterset, filterset)
        self.assertIs(export.serializer, serializer)
        self.assertEqual(export.renderers, renderers)
