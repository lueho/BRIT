import importlib
from unittest.mock import patch

from django.test import SimpleTestCase

from sources.greenhouses.filters import (
    CultureListFilter,
    GreenhouseTypeFilter,
    NantesGreenhousesFilterSet,
)
from sources.greenhouses.forms import (
    CultureModalModelForm,
    CultureModelForm,
    GreenhouseGrowthCycleModelForm,
    GreenhouseModalModelForm,
    GreenhouseModelForm,
    GrowthCycleCreateForm,
    GrowthShareFormSetHelper,
    GrowthTimestepInline,
    InlineGrowthShare,
    UpdateGreenhouseGrowthCycleValuesForm,
)
from sources.greenhouses.renderers import (
    NantesGreenhousesCSVRenderer,
    NantesGreenhousesXLSXRenderer,
)
from sources.greenhouses.serializers import (
    NantesGreenhousesFlatSerializer,
    NantesGreenhousesGeometrySerializer,
    NantesGreenhousesModelSerializer,
)
from sources.roadside_trees.filters import HamburgRoadsideTreesFilterSet
from sources.roadside_trees.renderers import (
    HamburgRoadsideTreesCSVRenderer,
    HamburgRoadsideTreesXLSXRenderer,
)
from sources.roadside_trees.serializers import (
    HamburgRoadsideTreeFlatSerializer,
    HamburgRoadsideTreeGeometrySerializer,
    HamburgRoadsideTreeSimpleModelSerializer,
)
from sources.waste_collection.filters import (
    CollectionFilterSet,
    CollectionFrequencyListFilter,
    CollectionSystemListFilter,
    CollectorFilter,
    FeeSystemListFilter,
    WasteCategoryListFilter,
    WasteComponentListFilter,
    WasteFlyerFilter,
)
from sources.waste_collection.forms import (
    CONNECTION_TYPE_CHOICES,
    REQUIRED_BIN_CAPACITY_REFERENCE_CHOICES,
    AggregatedCollectionPropertyValueModelForm,
    BinConfigurationModalModelForm,
    BinConfigurationModelForm,
    CollectionAddPredecessorForm,
    CollectionAddWasteSampleForm,
    CollectionFrequencyModalModelForm,
    CollectionFrequencyModelForm,
    CollectionModelForm,
    CollectionPropertyValueModelForm,
    CollectionRemovePredecessorForm,
    CollectionRemoveWasteSampleForm,
    CollectionSeasonForm,
    CollectionSeasonFormHelper,
    CollectionSeasonFormSet,
    CollectionSystemModalModelForm,
    CollectionSystemModelForm,
    CollectorModalModelForm,
    CollectorModelForm,
    FeeSystemModalModelForm,
    FeeSystemModelForm,
    WasteCategoryModalModelForm,
    WasteCategoryModelForm,
    WasteComponentModalModelForm,
    WasteComponentModelForm,
    WasteFlyerFormSet,
    WasteFlyerFormSetHelper,
    WasteFlyerModalModelForm,
    WasteFlyerModelForm,
)
from sources.waste_collection.renderers import (
    CollectionCSVRenderer,
    CollectionXLSXRenderer,
)
from sources.waste_collection.serializers import (
    GEOMETRY_SIMPLIFY_TOLERANCE,
    CollectionFlatSerializer,
    WasteCollectionGeometrySerializer,
)
from sources.waste_collection.tasks import check_wasteflyer_url, check_wasteflyer_urls


class SourcesSerializerAdapterTestCase(SimpleTestCase):
    def test_waste_collection_serializers_are_owned_by_sources(self):
        self.assertGreater(GEOMETRY_SIMPLIFY_TOLERANCE, 0)
        self.assertEqual(
            CollectionFlatSerializer.__module__, "sources.waste_collection.serializers"
        )
        self.assertEqual(
            WasteCollectionGeometrySerializer.__module__,
            "sources.waste_collection.serializers",
        )

    def test_roadside_tree_serializers_are_owned_by_sources(self):
        self.assertEqual(
            HamburgRoadsideTreeFlatSerializer.__module__,
            "sources.roadside_trees.serializers",
        )
        self.assertEqual(
            HamburgRoadsideTreeGeometrySerializer.__module__,
            "sources.roadside_trees.serializers",
        )
        self.assertEqual(
            HamburgRoadsideTreeSimpleModelSerializer.__module__,
            "sources.roadside_trees.serializers",
        )

    def test_greenhouse_serializers_are_owned_by_sources(self):
        self.assertEqual(
            NantesGreenhousesFlatSerializer.__module__,
            "sources.greenhouses.serializers",
        )
        self.assertEqual(
            NantesGreenhousesGeometrySerializer.__module__,
            "sources.greenhouses.serializers",
        )
        self.assertEqual(
            NantesGreenhousesModelSerializer.__module__,
            "sources.greenhouses.serializers",
        )

    def test_waste_collection_filters_and_renderers_are_owned_by_sources(self):
        self.assertEqual(
            CollectionFrequencyListFilter.__module__, "sources.waste_collection.filters"
        )
        self.assertEqual(
            CollectionFilterSet.__module__, "sources.waste_collection.filters"
        )
        self.assertEqual(
            CollectionSystemListFilter.__module__, "sources.waste_collection.filters"
        )
        self.assertEqual(CollectorFilter.__module__, "sources.waste_collection.filters")
        self.assertEqual(
            FeeSystemListFilter.__module__, "sources.waste_collection.filters"
        )
        self.assertEqual(
            WasteCategoryListFilter.__module__, "sources.waste_collection.filters"
        )
        self.assertEqual(
            WasteComponentListFilter.__module__, "sources.waste_collection.filters"
        )
        self.assertEqual(
            WasteFlyerFilter.__module__, "sources.waste_collection.filters"
        )
        self.assertEqual(
            CollectionCSVRenderer.__module__, "sources.waste_collection.renderers"
        )
        self.assertEqual(
            CollectionXLSXRenderer.__module__, "sources.waste_collection.renderers"
        )

    def test_waste_collection_filters_are_owned_by_sources(self):
        self.assertEqual(
            CollectionFilterSet.__module__, "sources.waste_collection.filters"
        )
        self.assertEqual(
            CollectionSystemListFilter.__module__,
            "sources.waste_collection.filters",
        )
        self.assertEqual(CollectorFilter.__module__, "sources.waste_collection.filters")
        self.assertEqual(
            WasteFlyerFilter.__module__, "sources.waste_collection.filters"
        )

    def test_waste_collection_renderers_are_owned_by_sources(self):
        self.assertEqual(
            CollectionCSVRenderer.__module__, "sources.waste_collection.renderers"
        )
        self.assertEqual(
            CollectionXLSXRenderer.__module__,
            "sources.waste_collection.renderers",
        )

    def test_roadside_tree_filters_and_serializers_are_owned_by_sources(self):
        self.assertEqual(
            HamburgRoadsideTreesFilterSet.__module__, "sources.roadside_trees.filters"
        )
        self.assertEqual(
            HamburgRoadsideTreeFlatSerializer.__module__,
            "sources.roadside_trees.serializers",
        )
        self.assertEqual(
            HamburgRoadsideTreeGeometrySerializer.__module__,
            "sources.roadside_trees.serializers",
        )
        self.assertEqual(
            HamburgRoadsideTreeSimpleModelSerializer.__module__,
            "sources.roadside_trees.serializers",
        )
        self.assertEqual(
            HamburgRoadsideTreesCSVRenderer.__module__,
            "sources.roadside_trees.renderers",
        )
        self.assertEqual(
            HamburgRoadsideTreesXLSXRenderer.__module__,
            "sources.roadside_trees.renderers",
        )

    def test_greenhouse_filters_serializers_and_renderers_are_owned_by_sources(self):
        self.assertEqual(CultureListFilter.__module__, "sources.greenhouses.filters")
        self.assertEqual(GreenhouseTypeFilter.__module__, "sources.greenhouses.filters")
        self.assertEqual(
            NantesGreenhousesFilterSet.__module__,
            "sources.greenhouses.filters",
        )
        self.assertEqual(
            NantesGreenhousesFlatSerializer.__module__,
            "sources.greenhouses.serializers",
        )
        self.assertEqual(
            NantesGreenhousesGeometrySerializer.__module__,
            "sources.greenhouses.serializers",
        )
        self.assertEqual(
            NantesGreenhousesModelSerializer.__module__,
            "sources.greenhouses.serializers",
        )
        self.assertEqual(
            NantesGreenhousesCSVRenderer.__module__,
            "sources.greenhouses.renderers",
        )
        self.assertEqual(
            NantesGreenhousesXLSXRenderer.__module__,
            "sources.greenhouses.renderers",
        )

    def test_greenhouse_forms_are_owned_by_sources(self):
        self.assertEqual(CultureModalModelForm.__module__, "sources.greenhouses.forms")
        self.assertEqual(CultureModelForm.__module__, "sources.greenhouses.forms")
        self.assertEqual(
            GreenhouseGrowthCycleModelForm.__module__,
            "sources.greenhouses.forms",
        )
        self.assertEqual(
            GreenhouseModalModelForm.__module__,
            "sources.greenhouses.forms",
        )
        self.assertEqual(GreenhouseModelForm.__module__, "sources.greenhouses.forms")
        self.assertEqual(GrowthCycleCreateForm.__module__, "sources.greenhouses.forms")
        self.assertEqual(
            GrowthShareFormSetHelper.__module__,
            "sources.greenhouses.forms",
        )
        self.assertEqual(GrowthTimestepInline.__module__, "sources.greenhouses.forms")
        self.assertEqual(InlineGrowthShare.__module__, "sources.greenhouses.forms")
        self.assertEqual(
            UpdateGreenhouseGrowthCycleValuesForm.__module__,
            "sources.greenhouses.forms",
        )

    def test_waste_collection_forms_are_owned_by_sources(self):
        self.assertTrue(CONNECTION_TYPE_CHOICES)
        self.assertTrue(REQUIRED_BIN_CAPACITY_REFERENCE_CHOICES)
        self.assertEqual(
            AggregatedCollectionPropertyValueModelForm.__module__,
            "sources.waste_collection.forms",
        )
        self.assertEqual(
            CollectionAddPredecessorForm.__module__,
            "sources.waste_collection.forms",
        )
        self.assertEqual(
            CollectionAddWasteSampleForm.__module__,
            "sources.waste_collection.forms",
        )
        self.assertEqual(
            CollectionFrequencyModalModelForm.__module__,
            "sources.waste_collection.forms",
        )
        self.assertEqual(
            CollectionFrequencyModelForm.__module__,
            "sources.waste_collection.forms",
        )
        self.assertEqual(
            CollectionModelForm.__module__, "sources.waste_collection.forms"
        )
        self.assertEqual(
            CollectionPropertyValueModelForm.__module__,
            "sources.waste_collection.forms",
        )
        self.assertEqual(
            CollectionRemovePredecessorForm.__module__,
            "sources.waste_collection.forms",
        )
        self.assertEqual(
            CollectionRemoveWasteSampleForm.__module__,
            "sources.waste_collection.forms",
        )
        self.assertEqual(
            CollectionSeasonForm.__module__, "sources.waste_collection.forms"
        )
        self.assertEqual(
            CollectionSeasonFormHelper.__module__,
            "sources.waste_collection.forms",
        )
        self.assertEqual(
            CollectionSeasonFormSet.__module__,
            "sources.waste_collection.forms",
        )
        self.assertEqual(
            CollectionSystemModalModelForm.__module__,
            "sources.waste_collection.forms",
        )
        self.assertEqual(
            CollectionSystemModelForm.__module__,
            "sources.waste_collection.forms",
        )
        self.assertEqual(
            CollectorModalModelForm.__module__,
            "sources.waste_collection.forms",
        )
        self.assertEqual(
            CollectorModelForm.__module__, "sources.waste_collection.forms"
        )
        self.assertEqual(
            FeeSystemModalModelForm.__module__,
            "sources.waste_collection.forms",
        )
        self.assertEqual(
            FeeSystemModelForm.__module__, "sources.waste_collection.forms"
        )
        self.assertEqual(
            BinConfigurationModalModelForm.__module__,
            "sources.waste_collection.forms",
        )
        self.assertEqual(WasteFlyerFormSet.__module__, "sources.waste_collection.forms")
        self.assertEqual(
            WasteFlyerFormSetHelper.__module__,
            "sources.waste_collection.forms",
        )
        self.assertEqual(
            WasteFlyerModalModelForm.__module__,
            "sources.waste_collection.forms",
        )
        self.assertEqual(
            WasteFlyerModelForm.__module__, "sources.waste_collection.forms"
        )
        self.assertEqual(
            WasteCategoryModalModelForm.__module__,
            "sources.waste_collection.forms",
        )
        self.assertEqual(
            WasteCategoryModelForm.__module__, "sources.waste_collection.forms"
        )
        self.assertEqual(
            WasteComponentModalModelForm.__module__,
            "sources.waste_collection.forms",
        )
        self.assertEqual(
            WasteComponentModelForm.__module__, "sources.waste_collection.forms"
        )
        self.assertEqual(
            BinConfigurationModelForm.__module__,
            "sources.waste_collection.forms",
        )

    def test_waste_collection_tasks_are_owned_by_sources(self):
        self.assertEqual(
            check_wasteflyer_url.run.__module__,
            "sources.waste_collection.tasks",
        )
        self.assertEqual(
            check_wasteflyer_urls.run.__module__,
            "sources.waste_collection.tasks",
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
            self.assertIs(
                geojson.WasteCollectionGeometrySerializer, geometry_serializer
            )
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
            self.assertIs(
                geojson.HamburgRoadsideTreeGeometrySerializer, geometry_serializer
            )
        finally:
            importlib.reload(geojson)

    def test_waste_collection_exports_import_flat_serializer_from_sources_adapter(self):
        from sources.waste_collection import exports

        flat_serializer = object()
        filterset = object()
        csv_renderer = object()
        xlsx_renderer = object()

        with (
            patch(
                "sources.waste_collection.serializers.CollectionFlatSerializer",
                flat_serializer,
            ),
            patch(
                "sources.waste_collection.filters.CollectionFilterSet",
                filterset,
            ),
            patch(
                "sources.waste_collection.renderers.CollectionCSVRenderer",
                csv_renderer,
            ),
            patch(
                "sources.waste_collection.renderers.CollectionXLSXRenderer",
                xlsx_renderer,
            ),
        ):
            importlib.reload(exports)

        try:
            self.assertIs(exports.CollectionFlatSerializer, flat_serializer)
            self.assertIs(exports.CollectionFilterSet, filterset)
            self.assertIs(exports.CollectionCSVRenderer, csv_renderer)
            self.assertIs(exports.CollectionXLSXRenderer, xlsx_renderer)
        finally:
            importlib.reload(exports)

    def test_roadside_tree_exports_import_flat_serializer_from_sources_adapter(self):
        from sources.roadside_trees import exports

        flat_serializer = object()
        filterset = object()
        csv_renderer = object()
        xlsx_renderer = object()

        with (
            patch(
                "sources.roadside_trees.serializers.HamburgRoadsideTreeFlatSerializer",
                flat_serializer,
            ),
            patch(
                "sources.roadside_trees.filters.HamburgRoadsideTreesFilterSet",
                filterset,
            ),
            patch(
                "sources.roadside_trees.renderers.HamburgRoadsideTreesCSVRenderer",
                csv_renderer,
            ),
            patch(
                "sources.roadside_trees.renderers.HamburgRoadsideTreesXLSXRenderer",
                xlsx_renderer,
            ),
        ):
            importlib.reload(exports)

        try:
            self.assertIs(exports.HamburgRoadsideTreeFlatSerializer, flat_serializer)
            self.assertIs(exports.HamburgRoadsideTreesFilterSet, filterset)
            self.assertIs(exports.HamburgRoadsideTreesCSVRenderer, csv_renderer)
            self.assertIs(exports.HamburgRoadsideTreesXLSXRenderer, xlsx_renderer)
        finally:
            importlib.reload(exports)

    def test_greenhouse_exports_import_flat_serializer_from_sources_adapter(self):
        from sources.greenhouses import exports

        flat_serializer = object()
        filterset = object()
        csv_renderer = object()
        xlsx_renderer = object()

        with (
            patch(
                "sources.greenhouses.serializers.NantesGreenhousesFlatSerializer",
                flat_serializer,
            ),
            patch(
                "sources.greenhouses.filters.NantesGreenhousesFilterSet",
                filterset,
            ),
            patch(
                "sources.greenhouses.renderers.NantesGreenhousesCSVRenderer",
                csv_renderer,
            ),
            patch(
                "sources.greenhouses.renderers.NantesGreenhousesXLSXRenderer",
                xlsx_renderer,
            ),
        ):
            importlib.reload(exports)

        try:
            self.assertIs(exports.NantesGreenhousesFlatSerializer, flat_serializer)
            self.assertIs(exports.NantesGreenhousesFilterSet, filterset)
            self.assertIs(exports.NantesGreenhousesCSVRenderer, csv_renderer)
            self.assertIs(exports.NantesGreenhousesXLSXRenderer, xlsx_renderer)
        finally:
            importlib.reload(exports)
