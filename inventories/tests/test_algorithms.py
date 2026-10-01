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
from materials.models import Material, SampleSeries
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
        cls.feedstock = SampleSeries.objects.create(
            name="Generic Series", material=cls.material
        )
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
        NantesGreenhouses.objects.create(geom=Point(0.5, 0.5, srid=4326))
        NantesGreenhouses.objects.create(geom=Point(-0.5, 0.2, srid=4326))
        NantesGreenhouses.objects.create(geom=Point(5, 5, srid=4326))

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
                    geom geometry(Point, 4326)
                )
                """
            )
            cursor.execute(
                f"""
                INSERT INTO public.{self.relation_name} (feature_id, geom) VALUES
                (1, ST_GeomFromText('POINT(0.5 0.5)', 4326)),
                (2, ST_GeomFromText('POINT(-0.5 0.2)', 4326)),
                (3, ST_GeomFromText('POINT(5 5)', 4326))
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


class GenericModuleRegistrationTestCase(TestCase):
    def test_inventories_module_is_available(self):
        self.assertIn("inventories.algorithms", InventoryAlgorithm.available_modules())

    def test_generic_functions_are_listed(self):
        functions = InventoryAlgorithm.available_functions("inventories.algorithms")
        self.assertIn("count_based_production", functions)
        self.assertIn("area_based_production", functions)
