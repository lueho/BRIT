import importlib
from unittest.mock import patch

from django.test import SimpleTestCase

from case_studies.flexibi_hamburg.serializers import (
    HamburgRoadsideTreeFlatSerializer as LegacyHamburgRoadsideTreeFlatSerializer,
    HamburgRoadsideTreeGeometrySerializer as LegacyHamburgRoadsideTreeGeometrySerializer,
    HamburgRoadsideTreeSimpleModelSerializer as LegacyHamburgRoadsideTreeSimpleModelSerializer,
)
from case_studies.flexibi_nantes.serializers import (
    NantesGreenhousesFlatSerializer as LegacyNantesGreenhousesFlatSerializer,
    NantesGreenhousesGeometrySerializer as LegacyNantesGreenhousesGeometrySerializer,
    NantesGreenhousesModelSerializer as LegacyNantesGreenhousesModelSerializer,
)
from case_studies.soilcom.serializers import (
    GEOMETRY_SIMPLIFY_TOLERANCE as LegacyGeometrySimplifyTolerance,
    CollectionFlatSerializer as LegacyCollectionFlatSerializer,
    WasteCollectionGeometrySerializer as LegacyWasteCollectionGeometrySerializer,
)
from sources.greenhouses.serializers import (
    NantesGreenhousesFlatSerializer,
    NantesGreenhousesGeometrySerializer,
    NantesGreenhousesModelSerializer,
)
from sources.roadside_trees.serializers import (
    HamburgRoadsideTreeFlatSerializer,
    HamburgRoadsideTreeGeometrySerializer,
    HamburgRoadsideTreeSimpleModelSerializer,
)
from sources.waste_collection.serializers import (
    GEOMETRY_SIMPLIFY_TOLERANCE,
    CollectionFlatSerializer,
    WasteCollectionGeometrySerializer,
)


class SourcesSerializerAdapterTestCase(SimpleTestCase):
    def test_waste_collection_serializer_adapters_reexport_legacy_symbols(self):
        self.assertEqual(GEOMETRY_SIMPLIFY_TOLERANCE, LegacyGeometrySimplifyTolerance)
        self.assertIs(CollectionFlatSerializer, LegacyCollectionFlatSerializer)
        self.assertIs(
            WasteCollectionGeometrySerializer,
            LegacyWasteCollectionGeometrySerializer,
        )

    def test_roadside_tree_serializer_adapters_reexport_legacy_serializers(self):
        self.assertIs(
            HamburgRoadsideTreeFlatSerializer,
            LegacyHamburgRoadsideTreeFlatSerializer,
        )
        self.assertIs(
            HamburgRoadsideTreeGeometrySerializer,
            LegacyHamburgRoadsideTreeGeometrySerializer,
        )
        self.assertIs(
            HamburgRoadsideTreeSimpleModelSerializer,
            LegacyHamburgRoadsideTreeSimpleModelSerializer,
        )

    def test_greenhouse_serializer_adapters_reexport_legacy_serializers(self):
        self.assertIs(NantesGreenhousesFlatSerializer, LegacyNantesGreenhousesFlatSerializer)
        self.assertIs(
            NantesGreenhousesGeometrySerializer,
            LegacyNantesGreenhousesGeometrySerializer,
        )
        self.assertIs(
            NantesGreenhousesModelSerializer,
            LegacyNantesGreenhousesModelSerializer,
        )

    def test_waste_collection_geojson_imports_serializer_from_sources_adapter(self):
        from sources.waste_collection import geojson

        geometry_serializer = object()
        tolerance = 42

        with (
            patch(
                "sources.waste_collection.serializers.WasteCollectionGeometrySerializer",
                geometry_serializer,
            ),
            patch(
                "sources.waste_collection.serializers.GEOMETRY_SIMPLIFY_TOLERANCE",
                tolerance,
            ),
        ):
            importlib.reload(geojson)

        try:
            self.assertIs(geojson.WasteCollectionGeometrySerializer, geometry_serializer)
            self.assertEqual(geojson.GEOMETRY_SIMPLIFY_TOLERANCE, tolerance)
        finally:
            importlib.reload(geojson)

    def test_roadside_tree_geojson_imports_serializer_from_sources_adapter(self):
        from sources.roadside_trees import geojson

        geometry_serializer = object()

        with patch(
            "sources.roadside_trees.serializers.HamburgRoadsideTreeGeometrySerializer",
            geometry_serializer,
        ):
            importlib.reload(geojson)

        try:
            self.assertIs(geojson.HamburgRoadsideTreeGeometrySerializer, geometry_serializer)
        finally:
            importlib.reload(geojson)

    def test_waste_collection_exports_import_flat_serializer_from_sources_adapter(self):
        from sources.waste_collection import exports

        flat_serializer = object()

        with patch(
            "sources.waste_collection.serializers.CollectionFlatSerializer",
            flat_serializer,
        ):
            importlib.reload(exports)

        try:
            self.assertIs(exports.CollectionFlatSerializer, flat_serializer)
        finally:
            importlib.reload(exports)

    def test_roadside_tree_exports_import_flat_serializer_from_sources_adapter(self):
        from sources.roadside_trees import exports

        flat_serializer = object()

        with patch(
            "sources.roadside_trees.serializers.HamburgRoadsideTreeFlatSerializer",
            flat_serializer,
        ):
            importlib.reload(exports)

        try:
            self.assertIs(exports.HamburgRoadsideTreeFlatSerializer, flat_serializer)
        finally:
            importlib.reload(exports)

    def test_greenhouse_exports_import_flat_serializer_from_sources_adapter(self):
        from sources.greenhouses import exports

        flat_serializer = object()

        with patch(
            "sources.greenhouses.serializers.NantesGreenhousesFlatSerializer",
            flat_serializer,
        ):
            importlib.reload(exports)

        try:
            self.assertIs(exports.NantesGreenhousesFlatSerializer, flat_serializer)
        finally:
            importlib.reload(exports)
