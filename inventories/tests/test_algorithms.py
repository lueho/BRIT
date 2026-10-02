"""Tests for the generic dataset-agnostic inventory algorithms."""

from unittest.mock import patch

from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.test import TestCase

from inventories.algorithms import InventoryAlgorithms
from inventories.models import (
    InventoryAlgorithm,
    InventoryAlgorithmParameter,
    InventoryAlgorithmParameterValue,
    Scenario,
    ScenarioInventoryConfiguration,
)
from maps.models import (
    Catchment,
    GeoDataset,
    GeoDatasetRuntimeConfiguration,
    Region,
)
from materials.models import Material
from sources.greenhouses.models import NantesGreenhouses
from sources.urban_green_spaces.models import HamburgGreenAreas

# Catchment covers lon/lat [-1, 1] x [-1, 1] around the equator.
CATCHMENT_WKT = "POLYGON((-1 -1, 1 -1, 1 1, -1 1, -1 -1))"


def aggregated_value(result, name):
    return next(entry for entry in result["aggregated_values"] if entry["name"] == name)


class GenericAlgorithmBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(name="Generic Region", country="DE")
        cls.region.geom = MultiPolygon(
            Polygon(((-1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1)), srid=4326)
        )
        cls.region.save()
        cls.catchment = Catchment.objects.create(
            name="Generic Catchment", region=cls.region
        )
        cls.material = Material.objects.create(name="Generic Material")
        cls.feedstock = cls.material
        cls.scenario = Scenario.objects.create(
            name="Generic Scenario",
            region=cls.region,
            catchment=cls.catchment,
        )

    def base_kwargs(self, geodataset):
        return {
            "geodataset_id": geodataset.id,
            "catchment_id": self.catchment.id,
            "scenario_id": self.scenario.id,
            "feedstock_id": self.feedstock.id,
        }


class CountBasedProductionModelBackendTestCase(GenericAlgorithmBase):
    """count_based_production on a model-backed point dataset."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.dataset = GeoDataset.objects.create(
            name="Greenhouses",
            region=cls.region,
            model_name="NantesGreenhouses",
        )
        NantesGreenhouses.objects.create(
            geom=Point(0.5, 0.5, srid=4326), culture_1="Tomato"
        )
        NantesGreenhouses.objects.create(
            geom=Point(-0.5, 0.2, srid=4326), culture_1="Cucumber"
        )
        NantesGreenhouses.objects.create(
            geom=Point(5, 5, srid=4326), culture_1="Tomato"
        )

    def test_counts_features_and_applies_factor_chain(self):
        result = InventoryAlgorithms.count_based_production(
            **self.base_kwargs(self.dataset),
            unit_yield={"value": 25.0, "standard_deviation": None, "unit": "kg / year"},
            collection_share={"value": 0.5, "standard_deviation": None, "unit": ""},
        )
        # 2 features in catchment * 25 kg/year * 0.5 = 25 kg/year = 0.025 Mg/a
        self.assertEqual(aggregated_value(result, "Count")["value"], 2)
        production = aggregated_value(result, "Total production")
        self.assertAlmostEqual(production["value"], 0.025)
        self.assertEqual(production["unit"], "Mg/a")
        self.assertEqual(len(result["features"]), 2)

    def test_unitless_factors_are_dimensionless(self):
        result = InventoryAlgorithms.count_based_production(
            **self.base_kwargs(self.dataset),
            unit_yield={"value": 25.0, "standard_deviation": None, "unit": "kg"},
            collection_share={"value": 0.5},
        )
        # 2 * 25 * 0.5 = 25 kg = 0.025 Mg (no per-year unit in the chain)
        production = aggregated_value(result, "Total production")
        self.assertAlmostEqual(production["value"], 0.025)
        self.assertEqual(production["unit"], "Mg")

    def test_no_parameters_means_raw_count_as_production(self):
        result = InventoryAlgorithms.count_based_production(
            **self.base_kwargs(self.dataset),
        )
        self.assertEqual(aggregated_value(result, "Count")["value"], 2)
        self.assertEqual(aggregated_value(result, "Total production")["value"], 2)

    def test_empty_catchment_returns_empty_features_with_geom_type(self):
        outside_region = Region.objects.create(name="Far Away", country="DE")
        outside_region.geom = MultiPolygon(
            Polygon(((10, 10), (11, 10), (11, 11), (10, 11), (10, 10)), srid=4326)
        )
        outside_region.save()
        outside_catchment = Catchment.objects.create(
            name="Far Catchment", region=outside_region
        )
        result = InventoryAlgorithms.count_based_production(
            geodataset_id=self.dataset.id,
            catchment_id=outside_catchment.id,
            scenario_id=self.scenario.id,
            feedstock_id=self.feedstock.id,
            unit_yield={"value": 25.0, "unit": "kg / year"},
        )
        self.assertEqual(result["features"], [])
        self.assertEqual(result["geom_type"], "Point")
        self.assertEqual(aggregated_value(result, "Count")["value"], 0)
        self.assertEqual(aggregated_value(result, "Total production")["value"], 0)

    def test_missing_geodataset_id_raises(self):
        kwargs = self.base_kwargs(self.dataset)
        del kwargs["geodataset_id"]
        with self.assertRaises(ImproperlyConfigured):
            InventoryAlgorithms.count_based_production(**kwargs)

    def test_feature_filter_restricts_features(self):
        """A feature_filter kwarg limits the counted features to rows whose
        attribute matches — e.g. one crop of many in a parcels dataset."""
        result = InventoryAlgorithms.count_based_production(
            **self.base_kwargs(self.dataset),
            feature_filter={"selection": "culture_1=Tomato"},
            unit_yield={"value": 10.0, "unit": "kg / year"},
        )
        # Only the single in-catchment Tomato greenhouse counts.
        self.assertEqual(aggregated_value(result, "Count")["value"], 1)
        self.assertAlmostEqual(
            aggregated_value(result, "Total production")["value"], 0.01
        )

    def test_feature_filter_accepts_plain_string(self):
        result = InventoryAlgorithms.count_based_production(
            **self.base_kwargs(self.dataset),
            feature_filter="culture_1=Cucumber",
        )
        self.assertEqual(aggregated_value(result, "Count")["value"], 1)

    def test_feature_filter_rejects_unknown_column(self):
        with self.assertRaises(ImproperlyConfigured):
            InventoryAlgorithms.count_based_production(
                **self.base_kwargs(self.dataset),
                feature_filter="no_such_column=x",
            )


class CountBasedProductionLocalRelationTestCase(GenericAlgorithmBase):
    """count_based_production on a local_relation dataset."""

    relation_name = "generic_inv_test_points"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.dataset = GeoDataset.objects.create(name="Local points", region=cls.region)
        GeoDatasetRuntimeConfiguration.objects.create(
            dataset=cls.dataset,
            backend_type="local_relation",
            schema_name="public",
            relation_name=cls.relation_name,
            geometry_column="geom",
            primary_key_column="feature_id",
        )

    def setUp(self):
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS public.{self.relation_name}")
            cursor.execute(
                f"""
                CREATE TABLE public.{self.relation_name} (
                    feature_id integer PRIMARY KEY,
                    crop varchar(40),
                    geom geometry(Point, 4326)
                )
                """
            )
            cursor.execute(
                f"""
                INSERT INTO public.{self.relation_name} (feature_id, crop, geom) VALUES
                (1, 'Wheat', ST_GeomFromText('POINT(0.5 0.5)', 4326)),
                (2, 'Barley', ST_GeomFromText('POINT(-0.5 0.2)', 4326)),
                (3, 'Wheat', ST_GeomFromText('POINT(5 5)', 4326))
                """
            )

    def tearDown(self):
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS public.{self.relation_name}")

    def test_counts_features_in_local_relation(self):
        result = InventoryAlgorithms.count_based_production(
            **self.base_kwargs(self.dataset),
            unit_yield={"value": 10.0, "unit": "kg / year"},
        )
        self.assertEqual(aggregated_value(result, "Count")["value"], 2)
        production = aggregated_value(result, "Total production")
        self.assertAlmostEqual(production["value"], 0.02)  # 20 kg/a
        self.assertEqual(len(result["features"]), 2)

    def test_feature_filter_on_local_relation(self):
        result = InventoryAlgorithms.count_based_production(
            **self.base_kwargs(self.dataset),
            feature_filter={"selection": "crop=Wheat"},
            unit_yield={"value": 10.0, "unit": "kg / year"},
        )
        # Only the in-catchment Wheat feature counts.
        self.assertEqual(aggregated_value(result, "Count")["value"], 1)

    def test_feature_columns_on_local_relation(self):
        columns = InventoryAlgorithms.feature_columns(self.dataset)
        names = {c["name"] for c in columns}
        self.assertIn("crop", names)
        crop_values = next(c["values"] for c in columns if c["name"] == "crop")
        self.assertIn("Wheat", crop_values)
        self.assertIn("Barley", crop_values)
        # Geometry and primary key are not filterable feature columns.
        self.assertNotIn("geom", names)
        self.assertNotIn("feature_id", names)


class AreaBasedProductionModelBackendTestCase(GenericAlgorithmBase):
    """area_based_production on a model-backed polygon dataset."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.dataset = GeoDataset.objects.create(
            name="Green areas", region=cls.region, model_name="HamburgGreenAreas"
        )
        # A parcel fully inside the catchment (~0.25 deg^2 ~ 308 000 ha).
        HamburgGreenAreas.objects.create(
            geom=MultiPolygon(
                Polygon(((0, 0), (0.5, 0), (0.5, 0.5), (0, 0.5), (0, 0)), srid=4326)
            )
        )
        # A parcel fully outside the catchment.
        HamburgGreenAreas.objects.create(
            geom=MultiPolygon(
                Polygon(((5, 5), (6, 5), (6, 6), (5, 6), (5, 5)), srid=4326)
            )
        )

    def _adapter(self, dataset):
        from maps.runtime_adapters import DatasetRuntimeAdapter

        return DatasetRuntimeAdapter(
            dataset=dataset,
            runtime_model_name="HamburgGreenAreas",
            model=HamburgGreenAreas,
            filterset_class=None,
            template_name="",
            features_api_basename="",
        )

    def _run(self, **params):
        with patch(
            "inventories.algorithms.get_dataset_runtime_adapter",
            return_value=self._adapter(self.dataset),
        ):
            return InventoryAlgorithms.area_based_production(
                **self.base_kwargs(self.dataset), **params
            )

    def test_clips_polygons_and_applies_factor_chain(self):
        result = self._run(
            area_yield={"value": 9.0, "unit": "kg / hectare / year"},
            recovery={"value": 0.5},
        )
        area = aggregated_value(result, "Total area")
        self.assertEqual(area["unit"], "ha")
        self.assertGreater(area["value"], 250_000)
        self.assertLess(area["value"], 360_000)
        production = aggregated_value(result, "Total production")
        expected_mg_a = area["value"] * 9.0 * 0.5 / 1000
        self.assertAlmostEqual(production["value"], expected_mg_a)
        self.assertEqual(production["unit"], "Mg/a")
        # Only the inner parcel contributes
        self.assertEqual(len(result["features"]), 1)
        self.assertEqual(result["geom_type"], "MultiPolygon")

    def test_area_is_clipped_to_catchment(self):
        # A parcel twice as wide as the catchment: the half east of
        # lon = 1 must be clipped away.
        HamburgGreenAreas.objects.create(
            geom=MultiPolygon(
                Polygon(((0, 0), (2, 0), (2, 1), (0, 1), (0, 0)), srid=4326)
            )
        )
        full_area = (
            MultiPolygon(
                Polygon(((0, 0), (2, 0), (2, 1), (0, 1), (0, 0)), srid=4326),
                srid=4326,
            )
            .transform(6933, clone=True)
            .area
        )
        result = self._run(area_yield={"value": 1.0, "unit": "kg / hectare / year"})
        area = aggregated_value(result, "Total area")
        clipped_expected = (full_area / 2) / 10000  # ha
        # The run also picks up the inner parcel from setUpTestData.
        inner_area = (
            MultiPolygon(
                Polygon(((0, 0), (0.5, 0), (0.5, 0.5), (0, 0.5), (0, 0)), srid=4326),
                srid=4326,
            )
            .transform(6933, clone=True)
            .area
            / 10000
        )
        expected = clipped_expected + inner_area
        self.assertAlmostEqual(area["value"], expected, delta=expected * 0.02)


class GeometryAccessorTestCase(TestCase):
    def test_direct_geometry_field(self):
        self.assertEqual(
            InventoryAlgorithms._geometry_accessor(HamburgGreenAreas), "geom"
        )

    def test_related_geometry_field(self):
        # Region keeps its geometry on the related GeoPolygon via 'borders'.
        self.assertEqual(
            InventoryAlgorithms._geometry_accessor(Region), "borders__geom"
        )


class AreaBasedProductionLocalRelationTestCase(GenericAlgorithmBase):
    """area_based_production on a local_relation polygon dataset."""

    relation_name = "generic_inv_test_parcels"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.dataset = GeoDataset.objects.create(name="Local parcels", region=cls.region)
        GeoDatasetRuntimeConfiguration.objects.create(
            dataset=cls.dataset,
            backend_type="local_relation",
            schema_name="public",
            relation_name=cls.relation_name,
            geometry_column="geom",
            primary_key_column="feature_id",
        )

    def setUp(self):
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS public.{self.relation_name}")
            cursor.execute(
                f"""
                CREATE TABLE public.{self.relation_name} (
                    feature_id integer PRIMARY KEY,
                    geom geometry(Polygon, 4326)
                )
                """
            )
            cursor.execute(
                f"""
                INSERT INTO public.{self.relation_name} (feature_id, geom) VALUES
                (1, ST_GeomFromText('POLYGON((0 0, 0.5 0, 0.5 0.5, 0 0.5, 0 0))', 4326)),
                (2, ST_GeomFromText('POLYGON((5 5, 6 5, 6 6, 5 6, 5 5))', 4326))
                """
            )

    def tearDown(self):
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS public.{self.relation_name}")

    def test_clips_local_relation_polygons(self):
        result = InventoryAlgorithms.area_based_production(
            **self.base_kwargs(self.dataset),
            area_yield={"value": 9.0, "unit": "kg / hectare / year"},
        )
        area = aggregated_value(result, "Total area")
        self.assertEqual(area["unit"], "ha")
        self.assertGreater(area["value"], 250_000)
        self.assertLess(area["value"], 360_000)
        production = aggregated_value(result, "Total production")
        self.assertAlmostEqual(production["value"], area["value"] * 9.0 / 1000)
        self.assertEqual(len(result["features"]), 1)
        self.assertEqual(result["geom_type"], "MultiPolygon")

    def test_empty_result_reports_factor_chain_unit(self):
        """An empty layer must report the same unit a populated layer of the
        same factor chain would — otherwise scenario totals raise
        UnitMismatchError when mixing with nonempty layers."""
        with connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM public.{self.relation_name}")
        result = InventoryAlgorithms.area_based_production(
            **self.base_kwargs(self.dataset),
            area_yield={"value": 9.0, "unit": "kg / hectare"},
        )
        production = aggregated_value(result, "Total production")
        self.assertEqual(production["value"], 0)
        # kg/hectare * m^2 -> kg -> Mg (not the hard-coded Mg/a default)
        self.assertEqual(production["unit"], "Mg")
        self.assertEqual(result["geom_type"], "MultiPolygon")


class ExecutionPlanUnitWiringTestCase(GenericAlgorithmBase):
    """The execution plan must pass each parameter's unit to the algorithm."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.dataset = GeoDataset.objects.create(
            name="Wiring dataset", region=cls.region
        )
        cls.algorithm = InventoryAlgorithm.objects.create(
            name="Generic count",
            source_module="inventories.algorithms",
            function_name="count_based_production",
            geodataset=cls.dataset,
        )
        cls.algorithm.feedstocks.add(cls.material)
        cls.parameter = InventoryAlgorithmParameter.objects.create(
            descriptive_name="Unit yield",
            short_name="unit_yield",
            unit="kg / year",
            is_required=True,
        )
        cls.parameter.inventory_algorithm.add(cls.algorithm)
        cls.value = InventoryAlgorithmParameterValue.objects.create(
            name="Default yield",
            parameter=cls.parameter,
            value=25.0,
            default=True,
        )
        ScenarioInventoryConfiguration.objects.create(
            scenario=cls.scenario,
            feedstock=cls.feedstock,
            geodataset=cls.dataset,
            inventory_algorithm=cls.algorithm,
            inventory_parameter=cls.parameter,
            inventory_value=cls.value,
        )

    def test_execution_plan_passes_parameter_unit(self):
        plan = self.scenario.inventory_execution_plan()
        self.assertEqual(len(plan), 1)
        kwargs = plan[0]["kwargs"]
        self.assertEqual(kwargs["unit_yield"]["unit"], "kg / year")
        self.assertEqual(kwargs["unit_yield"]["value"], 25.0)

    def test_execute_injects_geodataset_id(self):
        with patch.object(
            InventoryAlgorithms,
            "count_based_production",
            return_value={"features": []},
        ) as mock_run:
            self.algorithm.execute(
                catchment_id=self.catchment.id,
                scenario_id=self.scenario.id,
                feedstock_id=self.feedstock.id,
            )
        called_kwargs = mock_run.call_args.kwargs
        self.assertEqual(called_kwargs["geodataset_id"], self.dataset.id)

    def test_execution_plan_passes_selection_name(self):
        """Selection-typed values carry their name into the kwargs so
        e.g. feature_filter can encode 'column=value'."""
        filter_param = InventoryAlgorithmParameter.objects.create(
            descriptive_name="Feature filter", short_name="feature_filter"
        )
        filter_param.inventory_algorithm.add(self.algorithm)
        filter_value = InventoryAlgorithmParameterValue.objects.create(
            name="crop=Wheat",
            parameter=filter_param,
            value=1.0,
            type=InventoryAlgorithmParameterValue.ValueType.SELECTION,
        )
        ScenarioInventoryConfiguration.objects.create(
            scenario=self.scenario,
            feedstock=self.feedstock,
            geodataset=self.dataset,
            inventory_algorithm=self.algorithm,
            inventory_parameter=filter_param,
            inventory_value=filter_value,
        )
        plan = self.scenario.inventory_execution_plan()
        kwargs = plan[0]["kwargs"]
        self.assertEqual(kwargs["feature_filter"]["selection"], "crop=Wheat")


class GeometryFamilyTestCase(GenericAlgorithmBase):
    """geometry_family + generic_functions drive the add-inventory form."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.point_dataset = GeoDataset.objects.create(
            name="Point dataset", region=cls.region, model_name="NantesGreenhouses"
        )
        cls.polygon_dataset = GeoDataset.objects.create(
            name="Polygon dataset", region=cls.region, model_name="NutsRegion"
        )
        cls.unknown_dataset = GeoDataset.objects.create(
            name="Broken dataset", region=cls.region, model_name="NoSuchModel"
        )
        cls.relation_dataset = GeoDataset.objects.create(
            name="Relation lines", region=cls.region
        )
        GeoDatasetRuntimeConfiguration.objects.create(
            dataset=cls.relation_dataset,
            backend_type="local_relation",
            schema_name="public",
            relation_name="generic_inv_test_lines",
            geometry_column="geom",
            primary_key_column="feature_id",
        )

    def setUp(self):
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS public.generic_inv_test_lines")
            cursor.execute(
                """
                CREATE TABLE public.generic_inv_test_lines (
                    feature_id integer PRIMARY KEY,
                    geom geometry(LineString, 4326)
                )
                """
            )
            cursor.execute(
                "INSERT INTO public.generic_inv_test_lines (feature_id, geom) "
                "VALUES (1, ST_GeomFromText('LINESTRING(0 0, 0.5 0.5)', 4326))"
            )

    def tearDown(self):
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS public.generic_inv_test_lines")

    def test_point_model_dataset_is_point_family(self):
        self.assertEqual(
            InventoryAlgorithms.geometry_family(self.point_dataset), "point"
        )

    def test_polygon_model_dataset_is_polygon_family(self):
        self.assertEqual(
            InventoryAlgorithms.geometry_family(self.polygon_dataset), "polygon"
        )

    def test_unresolvable_dataset_returns_none(self):
        self.assertIsNone(InventoryAlgorithms.geometry_family(self.unknown_dataset))

    def test_relation_geometry_family_from_geometry_columns(self):
        self.assertEqual(
            InventoryAlgorithms.geometry_family(self.relation_dataset), "line"
        )

    def test_generic_functions_for_point_dataset(self):
        self.assertEqual(
            InventoryAlgorithms.generic_functions(self.point_dataset),
            ["count_based_production"],
        )

    def test_generic_functions_for_polygon_dataset(self):
        self.assertEqual(
            InventoryAlgorithms.generic_functions(self.polygon_dataset),
            ["area_based_production"],
        )

    def test_generic_functions_for_line_dataset(self):
        """Line geometries have no polygon area — only counting applies."""
        self.assertEqual(
            InventoryAlgorithms.generic_functions(self.relation_dataset),
            ["count_based_production"],
        )


class GenericModuleRegistrationTestCase(TestCase):
    def test_inventories_module_is_available(self):
        self.assertIn("inventories.algorithms", InventoryAlgorithm.available_modules())

    def test_generic_functions_are_listed(self):
        functions = InventoryAlgorithm.available_functions("inventories.algorithms")
        self.assertIn("count_based_production", functions)
        self.assertIn("area_based_production", functions)
