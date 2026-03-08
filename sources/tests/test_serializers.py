import importlib
from unittest.mock import patch

from django.test import SimpleTestCase

from case_studies.flexibi_hamburg.serializers import (
    HamburgRoadsideTreeFlatSerializer as LegacyHamburgRoadsideTreeFlatSerializer,
    HamburgRoadsideTreeGeometrySerializer as LegacyHamburgRoadsideTreeGeometrySerializer,
    HamburgRoadsideTreeSimpleModelSerializer as LegacyHamburgRoadsideTreeSimpleModelSerializer,
)
from case_studies.flexibi_hamburg.filters import (
    HamburgRoadsideTreesFilterSet as LegacyHamburgRoadsideTreesFilterSet,
)
from case_studies.flexibi_hamburg.renderers import (
    HamburgRoadsideTreesCSVRenderer as LegacyHamburgRoadsideTreesCSVRenderer,
    HamburgRoadsideTreesXLSXRenderer as LegacyHamburgRoadsideTreesXLSXRenderer,
)
from case_studies.flexibi_nantes.serializers import (
    NantesGreenhousesFlatSerializer as LegacyNantesGreenhousesFlatSerializer,
    NantesGreenhousesGeometrySerializer as LegacyNantesGreenhousesGeometrySerializer,
    NantesGreenhousesModelSerializer as LegacyNantesGreenhousesModelSerializer,
)
from case_studies.flexibi_nantes.filters import (
    CultureListFilter as LegacyCultureListFilter,
    GreenhouseTypeFilter as LegacyGreenhouseTypeFilter,
    NantesGreenhousesFilterSet as LegacyNantesGreenhousesFilterSet,
)
from case_studies.flexibi_nantes.forms import (
    CultureModalModelForm as LegacyCultureModalModelForm,
    CultureModelForm as LegacyCultureModelForm,
    GreenhouseGrowthCycleModelForm as LegacyGreenhouseGrowthCycleModelForm,
    GreenhouseModalModelForm as LegacyGreenhouseModalModelForm,
    GreenhouseModelForm as LegacyGreenhouseModelForm,
    GrowthCycleCreateForm as LegacyGrowthCycleCreateForm,
    GrowthShareFormSetHelper as LegacyGrowthShareFormSetHelper,
    GrowthTimestepInline as LegacyGrowthTimestepInline,
    InlineGrowthShare as LegacyInlineGrowthShare,
    UpdateGreenhouseGrowthCycleValuesForm as LegacyUpdateGreenhouseGrowthCycleValuesForm,
)
from case_studies.flexibi_nantes.renderers import (
    NantesGreenhousesCSVRenderer as LegacyNantesGreenhousesCSVRenderer,
    NantesGreenhousesXLSXRenderer as LegacyNantesGreenhousesXLSXRenderer,
)
from case_studies.soilcom.serializers import (
    GEOMETRY_SIMPLIFY_TOLERANCE as LegacyGeometrySimplifyTolerance,
    CollectionFlatSerializer as LegacyCollectionFlatSerializer,
    WasteCollectionGeometrySerializer as LegacyWasteCollectionGeometrySerializer,
)
from case_studies.soilcom.filters import CollectionFilterSet as LegacyCollectionFilterSet
from case_studies.soilcom.filters import (
    CollectionFrequencyListFilter as LegacyCollectionFrequencyListFilter,
    CollectionSystemListFilter as LegacyCollectionSystemListFilter,
    CollectorFilter as LegacyCollectorFilter,
    FeeSystemListFilter as LegacyFeeSystemListFilter,
    WasteCategoryListFilter as LegacyWasteCategoryListFilter,
    WasteComponentListFilter as LegacyWasteComponentListFilter,
    WasteFlyerFilter as LegacyWasteFlyerFilter,
)
from case_studies.soilcom.forms import (
    AggregatedCollectionPropertyValueModelForm as LegacyAggregatedCollectionPropertyValueModelForm,
    CollectionAddPredecessorForm as LegacyCollectionAddPredecessorForm,
    CollectionAddWasteSampleForm as LegacyCollectionAddWasteSampleForm,
    CollectionFrequencyModalModelForm as LegacyCollectionFrequencyModalModelForm,
    CollectionFrequencyModelForm as LegacyCollectionFrequencyModelForm,
    CollectionModelForm as LegacyCollectionModelForm,
    CollectionPropertyValueModelForm as LegacyCollectionPropertyValueModelForm,
    CollectionRemovePredecessorForm as LegacyCollectionRemovePredecessorForm,
    CollectionRemoveWasteSampleForm as LegacyCollectionRemoveWasteSampleForm,
    CollectionSeasonForm as LegacyCollectionSeasonForm,
    CollectionSeasonFormHelper as LegacyCollectionSeasonFormHelper,
    CollectionSeasonFormSet as LegacyCollectionSeasonFormSet,
    CollectionSystemModalModelForm as LegacyCollectionSystemModalModelForm,
    CollectionSystemModelForm as LegacyCollectionSystemModelForm,
    CollectorModalModelForm as LegacyCollectorModalModelForm,
    CollectorModelForm as LegacyCollectorModelForm,
    FeeSystemModelForm as LegacyFeeSystemModelForm,
    WasteCategoryModalModelForm as LegacyWasteCategoryModalModelForm,
    WasteCategoryModelForm as LegacyWasteCategoryModelForm,
    WasteComponentModalModelForm as LegacyWasteComponentModalModelForm,
    WasteComponentModelForm as LegacyWasteComponentModelForm,
    WasteFlyerFormSet as LegacyWasteFlyerFormSet,
    WasteFlyerFormSetHelper as LegacyWasteFlyerFormSetHelper,
    WasteFlyerModalModelForm as LegacyWasteFlyerModalModelForm,
    WasteFlyerModelForm as LegacyWasteFlyerModelForm,
)
from case_studies.soilcom.renderers import (
    CollectionCSVRenderer as LegacyCollectionCSVRenderer,
    CollectionXLSXRenderer as LegacyCollectionXLSXRenderer,
)
from case_studies.soilcom.tasks import (
    check_wasteflyer_url as LegacyCheckWasteflyerUrl,
    check_wasteflyer_urls as LegacyCheckWasteflyerUrls,
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
from sources.greenhouses.filters import (
    CultureListFilter,
    GreenhouseTypeFilter,
    NantesGreenhousesFilterSet,
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
    AggregatedCollectionPropertyValueModelForm,
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
    def test_waste_collection_serializer_adapters_reexport_legacy_symbols(self):
        self.assertEqual(GEOMETRY_SIMPLIFY_TOLERANCE, LegacyGeometrySimplifyTolerance)
        self.assertIs(CollectionFlatSerializer, LegacyCollectionFlatSerializer)
        self.assertIs(
            WasteCollectionGeometrySerializer,
            LegacyWasteCollectionGeometrySerializer,
        )

    def test_waste_collection_serializers_are_owned_by_sources(self):
        self.assertEqual(CollectionFlatSerializer.__module__, "sources.waste_collection.serializers")
        self.assertEqual(
            WasteCollectionGeometrySerializer.__module__,
            "sources.waste_collection.serializers",
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

    def test_waste_collection_filter_and_renderer_adapters_reexport_legacy_symbols(self):
        self.assertIs(CollectionFrequencyListFilter, LegacyCollectionFrequencyListFilter)
        self.assertIs(CollectionFilterSet, LegacyCollectionFilterSet)
        self.assertIs(CollectionSystemListFilter, LegacyCollectionSystemListFilter)
        self.assertIs(CollectorFilter, LegacyCollectorFilter)
        self.assertIs(FeeSystemListFilter, LegacyFeeSystemListFilter)
        self.assertIs(WasteCategoryListFilter, LegacyWasteCategoryListFilter)
        self.assertIs(WasteComponentListFilter, LegacyWasteComponentListFilter)
        self.assertIs(WasteFlyerFilter, LegacyWasteFlyerFilter)
        self.assertIs(CollectionCSVRenderer, LegacyCollectionCSVRenderer)
        self.assertIs(CollectionXLSXRenderer, LegacyCollectionXLSXRenderer)

    def test_waste_collection_filters_are_owned_by_sources(self):
        self.assertEqual(CollectionFilterSet.__module__, "sources.waste_collection.filters")
        self.assertEqual(
            CollectionSystemListFilter.__module__,
            "sources.waste_collection.filters",
        )
        self.assertEqual(CollectorFilter.__module__, "sources.waste_collection.filters")
        self.assertEqual(WasteFlyerFilter.__module__, "sources.waste_collection.filters")

    def test_waste_collection_renderers_are_owned_by_sources(self):
        self.assertEqual(CollectionCSVRenderer.__module__, "sources.waste_collection.renderers")
        self.assertEqual(
            CollectionXLSXRenderer.__module__,
            "sources.waste_collection.renderers",
        )

    def test_roadside_tree_filter_and_renderer_adapters_reexport_legacy_symbols(self):
        self.assertIs(HamburgRoadsideTreesFilterSet, LegacyHamburgRoadsideTreesFilterSet)
        self.assertIs(HamburgRoadsideTreesCSVRenderer, LegacyHamburgRoadsideTreesCSVRenderer)
        self.assertIs(HamburgRoadsideTreesXLSXRenderer, LegacyHamburgRoadsideTreesXLSXRenderer)

    def test_roadside_tree_filters_and_serializers_are_owned_by_sources(self):
        self.assertEqual(HamburgRoadsideTreesFilterSet.__module__, "sources.roadside_trees.filters")
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

    def test_greenhouse_filter_and_renderer_adapters_reexport_legacy_symbols(self):
        self.assertIs(CultureListFilter, LegacyCultureListFilter)
        self.assertIs(GreenhouseTypeFilter, LegacyGreenhouseTypeFilter)
        self.assertIs(NantesGreenhousesFilterSet, LegacyNantesGreenhousesFilterSet)
        self.assertIs(NantesGreenhousesCSVRenderer, LegacyNantesGreenhousesCSVRenderer)
        self.assertIs(NantesGreenhousesXLSXRenderer, LegacyNantesGreenhousesXLSXRenderer)

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

    def test_greenhouse_form_adapters_reexport_legacy_symbols(self):
        self.assertIs(CultureModalModelForm, LegacyCultureModalModelForm)
        self.assertIs(CultureModelForm, LegacyCultureModelForm)
        self.assertIs(GreenhouseGrowthCycleModelForm, LegacyGreenhouseGrowthCycleModelForm)
        self.assertIs(GreenhouseModalModelForm, LegacyGreenhouseModalModelForm)
        self.assertIs(GreenhouseModelForm, LegacyGreenhouseModelForm)
        self.assertIs(GrowthCycleCreateForm, LegacyGrowthCycleCreateForm)
        self.assertIs(GrowthShareFormSetHelper, LegacyGrowthShareFormSetHelper)
        self.assertIs(GrowthTimestepInline, LegacyGrowthTimestepInline)
        self.assertIs(InlineGrowthShare, LegacyInlineGrowthShare)
        self.assertIs(
            UpdateGreenhouseGrowthCycleValuesForm,
            LegacyUpdateGreenhouseGrowthCycleValuesForm,
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

    def test_waste_collection_form_and_task_adapters_reexport_legacy_symbols(self):
        self.assertIs(
            AggregatedCollectionPropertyValueModelForm,
            LegacyAggregatedCollectionPropertyValueModelForm,
        )
        self.assertIs(CollectionAddPredecessorForm, LegacyCollectionAddPredecessorForm)
        self.assertIs(CollectionAddWasteSampleForm, LegacyCollectionAddWasteSampleForm)
        self.assertIs(
            CollectionFrequencyModalModelForm,
            LegacyCollectionFrequencyModalModelForm,
        )
        self.assertIs(CollectionFrequencyModelForm, LegacyCollectionFrequencyModelForm)
        self.assertIs(CollectionModelForm, LegacyCollectionModelForm)
        self.assertIs(
            CollectionPropertyValueModelForm,
            LegacyCollectionPropertyValueModelForm,
        )
        self.assertIs(
            CollectionRemovePredecessorForm,
            LegacyCollectionRemovePredecessorForm,
        )
        self.assertIs(
            CollectionRemoveWasteSampleForm,
            LegacyCollectionRemoveWasteSampleForm,
        )
        self.assertIs(CollectionSeasonForm, LegacyCollectionSeasonForm)
        self.assertIs(CollectionSeasonFormHelper, LegacyCollectionSeasonFormHelper)
        self.assertIs(CollectionSeasonFormSet, LegacyCollectionSeasonFormSet)
        self.assertIs(
            CollectionSystemModalModelForm,
            LegacyCollectionSystemModalModelForm,
        )
        self.assertIs(CollectionSystemModelForm, LegacyCollectionSystemModelForm)
        self.assertIs(CollectorModalModelForm, LegacyCollectorModalModelForm)
        self.assertIs(CollectorModelForm, LegacyCollectorModelForm)
        self.assertIs(FeeSystemModelForm, LegacyFeeSystemModelForm)
        self.assertIs(WasteCategoryModalModelForm, LegacyWasteCategoryModalModelForm)
        self.assertIs(WasteCategoryModelForm, LegacyWasteCategoryModelForm)
        self.assertIs(WasteComponentModalModelForm, LegacyWasteComponentModalModelForm)
        self.assertIs(WasteComponentModelForm, LegacyWasteComponentModelForm)
        self.assertIs(WasteFlyerFormSet, LegacyWasteFlyerFormSet)
        self.assertIs(WasteFlyerFormSetHelper, LegacyWasteFlyerFormSetHelper)
        self.assertIs(WasteFlyerModalModelForm, LegacyWasteFlyerModalModelForm)
        self.assertIs(WasteFlyerModelForm, LegacyWasteFlyerModelForm)
        self.assertIs(check_wasteflyer_url, LegacyCheckWasteflyerUrl)
        self.assertIs(check_wasteflyer_urls, LegacyCheckWasteflyerUrls)

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
