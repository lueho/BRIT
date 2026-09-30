from unittest.mock import Mock, patch

from django.contrib.gis.geos import GEOSGeometry
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.test import TestCase

from inventories.models import (
    InventoryAlgorithm,
    Scenario,
    ScenarioInventoryConfiguration,
)
from maps.models import (
    Catchment,
    GeoDataset,
    GeoDatasetColumnPolicy,
    GeoDatasetRuntimeConfiguration,
    Region,
)
from maps.runtime_adapters import DatasetRuntimeAdapter
from sources.sotasen.inventory.algorithms import (
    GRASSLAND_LAND_USE,
    LAND_USE_FIELD,
    InventoryAlgorithms,
)

POLYGON_GEOJSON = {
    "type": "Polygon",
    "coordinates": [
        [
            [13.0, 58.0],
            [13.1, 58.0],
            [13.1, 58.1],
            [13.0, 58.1],
            [13.0, 58.0],
        ]
    ],
}

SECOND_POLYGON_GEOJSON = {
    "type": "Polygon",
    "coordinates": [
        [
            [13.2, 58.0],
            [13.3, 58.0],
            [13.3, 58.1],
            [13.2, 58.1],
            [13.2, 58.0],
        ]
    ],
}


def make_feature(pk, area_ha, land_use=GRASSLAND_LAND_USE, geometry=None):
    return {
        "type": "Feature",
        "id": pk,
        "geometry": POLYGON_GEOJSON if geometry is None else geometry,
        "properties": {
            "land_use": land_use,
            "area_ha": area_ha,
        },
    }


def make_adapter(features):
    adapter = Mock()
    adapter.uses_local_relation = True
    adapter.get_geojson_feature_collection.return_value = {
        "type": "FeatureCollection",
        "features": features,
    }
    return adapter


def aggregated_value(result, name):
    return next(
        entry["value"] for entry in result["aggregated_values"] if entry["name"] == name
    )


class SotasenGrassToProteinTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(name="Töreboda", country="SE")
        cls.geodataset = GeoDataset.objects.create(
            name="Sötåsen Agricultural Land Use", region=cls.region
        )

    def run_algorithm(self, features, adapter=None, **kwargs):
        adapter = adapter or make_adapter(features)
        with patch(
            "sources.sotasen.inventory.algorithms.get_dataset_runtime_adapter",
            return_value=adapter,
        ) as mock_get_adapter:
            result = InventoryAlgorithms.sotasen_grass_to_protein(**kwargs)
        return result, adapter, mock_get_adapter

    def test_aggregates_match_expected_totals(self):
        features = [
            make_feature(1, 50.26),
            make_feature(2, 60.0, geometry=SECOND_POLYGON_GEOJSON),
        ]
        result, adapter, _ = self.run_algorithm(
            features,
            geodataset_id=self.geodataset.id,
            dry_matter_yield={"value": 9.0, "standard_deviation": None},
            crude_protein_fraction={"value": 0.20, "standard_deviation": None},
            protein_recovery_fraction={"value": 0.12, "standard_deviation": None},
        )

        self.assertAlmostEqual(
            aggregated_value(result, "Grassland area"), 110.26, places=6
        )
        self.assertAlmostEqual(
            aggregated_value(result, "Total production"), 992.34, places=6
        )
        self.assertAlmostEqual(
            aggregated_value(result, "Crude protein in biomass"), 198.468, places=6
        )
        self.assertAlmostEqual(
            aggregated_value(result, "Recovered protein"), 23.81616, places=6
        )
        units = {entry["name"]: entry["unit"] for entry in result["aggregated_values"]}
        self.assertEqual(units["Grassland area"], "ha")
        self.assertEqual(units["Total production"], "Mg/a")
        self.assertEqual(units["Recovered protein"], "Mg/a")

    def test_filters_dataset_to_grassland(self):
        features = [make_feature(1, 10.0)]
        _, adapter, _ = self.run_algorithm(features, geodataset_id=self.geodataset.id)

        adapter.get_geojson_feature_collection.assert_called_once_with(
            query_params={LAND_USE_FIELD: GRASSLAND_LAND_USE}
        )

    def test_features_contain_geos_geometry_and_properties(self):
        features = [make_feature(1, 10.0), make_feature(2, 5.0)]
        result, _, _ = self.run_algorithm(
            features,
            geodataset_id=self.geodataset.id,
            dry_matter_yield=9.0,
            crude_protein_fraction=0.2,
            protein_recovery_fraction=0.12,
        )

        self.assertEqual(len(result["features"]), 2)
        first = result["features"][0]
        self.assertIsInstance(first["geom"], GEOSGeometry)
        self.assertEqual(first["geom"].geom_type, "Polygon")
        self.assertEqual(first["geom"].srid, 4326)
        self.assertEqual(first["land_use"], "Grassland")
        self.assertEqual(first["area_ha"], 10.0)
        self.assertAlmostEqual(first["dry_matter_mg_a"], 90.0, places=6)
        self.assertAlmostEqual(first["recovered_protein_mg_a"], 2.16, places=6)

    def test_features_without_geometry_are_skipped_but_counted(self):
        features = [
            make_feature(1, 10.0),
            {
                "type": "Feature",
                "id": 2,
                "geometry": None,
                "properties": {"land_use": "Grassland", "area_ha": 5.0},
            },
        ]
        result, _, _ = self.run_algorithm(features, geodataset_id=self.geodataset.id)

        self.assertEqual(len(result["features"]), 1)
        self.assertAlmostEqual(
            aggregated_value(result, "Grassland area"), 15.0, places=6
        )

    def test_defaults_are_used_when_parameters_omitted(self):
        result, _, _ = self.run_algorithm(
            [make_feature(1, 100.0)], geodataset_id=self.geodataset.id
        )
        self.assertAlmostEqual(
            aggregated_value(result, "Total production"), 900.0, places=6
        )
        self.assertAlmostEqual(
            aggregated_value(result, "Recovered protein"), 21.6, places=6
        )

    def test_recovery_fraction_variants(self):
        features = [make_feature(1, 110.26)]
        expected = {0.04: 7.93872, 0.20: 39.6936, 0.42: 83.35656}
        for fraction, recovered in expected.items():
            result, _, _ = self.run_algorithm(
                features,
                geodataset_id=self.geodataset.id,
                protein_recovery_fraction={"value": fraction},
            )
            self.assertAlmostEqual(
                aggregated_value(result, "Recovered protein"),
                recovered,
                places=5,
            )

    def test_invalid_parameters_raise_value_error(self):
        cases = [
            {"dry_matter_yield": 0},
            {"dry_matter_yield": -1},
            {"crude_protein_fraction": 0},
            {"crude_protein_fraction": 1.5},
            {"protein_recovery_fraction": 0},
            {"protein_recovery_fraction": 2},
        ]
        for overrides in cases:
            with self.subTest(**overrides):
                with self.assertRaises((ValueError, TypeError)):
                    self.run_algorithm(
                        [make_feature(1, 10.0)],
                        geodataset_id=self.geodataset.id,
                        **overrides,
                    )

    def test_non_local_relation_adapter_is_rejected(self):
        adapter = Mock(spec=DatasetRuntimeAdapter)
        with self.assertRaises(ImproperlyConfigured):
            self.run_algorithm([], adapter=adapter, geodataset_id=self.geodataset.id)

    def test_resolves_geodataset_from_scenario_configuration(self):
        catchment = Catchment.objects.create(name="Töreboda (1473)", region=self.region)
        scenario = Scenario.objects.create(
            name="Sötåsen demo", region=self.region, catchment=catchment
        )
        algorithm = InventoryAlgorithm.objects.create(
            name="Sötåsen grass-to-protein",
            source_module="sources.sotasen.inventory.algorithms",
            function_name="sotasen_grass_to_protein",
            geodataset=self.geodataset,
        )
        ScenarioInventoryConfiguration.objects.create(
            scenario=scenario,
            geodataset=self.geodataset,
            inventory_algorithm=algorithm,
        )

        adapter = make_adapter([make_feature(1, 10.0)])
        with patch(
            "sources.sotasen.inventory.algorithms.get_dataset_runtime_adapter",
            return_value=adapter,
        ) as mock_get_adapter:
            InventoryAlgorithms.sotasen_grass_to_protein(scenario_id=scenario.id)

        mock_get_adapter.assert_called_once()
        self.assertEqual(mock_get_adapter.call_args.args[0].id, self.geodataset.id)

    def test_missing_geodataset_resolution_fails_clearly(self):
        with self.assertRaises(ImproperlyConfigured):
            self.run_algorithm([make_feature(1, 10.0)])

    def test_empty_feature_collection_returns_zero_totals(self):
        result, _, _ = self.run_algorithm([], geodataset_id=self.geodataset.id)
        self.assertEqual(result["features"], [])
        for entry in result["aggregated_values"]:
            self.assertEqual(entry["value"], 0)


class SotasenGrassToProteinLocalRelationTestCase(TestCase):
    """Exercises the real LocalRelationDatasetRuntimeAdapter against a test
    table; no production raw_data.sotasen_land_use is touched."""

    relation_name = "sotasen_test_land_use"

    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(name="Töreboda", country="SE")
        cls.dataset = GeoDataset.objects.create(
            name="Sötåsen Agricultural Land Use", region=cls.region
        )
        GeoDatasetRuntimeConfiguration.objects.create(
            dataset=cls.dataset,
            backend_type="local_relation",
            schema_name="public",
            relation_name=cls.relation_name,
            geometry_column="geom",
            primary_key_column="fid",
            label_field="land_use",
        )
        for column_name, filterable in (
            ("land_use", True),
            ("area_ha", False),
            ("area_m2", False),
        ):
            GeoDatasetColumnPolicy.objects.create(
                dataset=cls.dataset,
                column_name=column_name,
                is_visible=True,
                is_filterable=filterable,
            )

    def setUp(self):
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS public.{self.relation_name}")
            cursor.execute(
                f"""
                CREATE TABLE public.{self.relation_name} (
                    fid integer PRIMARY KEY,
                    land_use varchar(100),
                    area_ha double precision,
                    area_m2 double precision,
                    geom geometry(MultiPolygon, 4326)
                )
                """
            )
            cursor.execute(
                f"""
                INSERT INTO public.{self.relation_name} VALUES
                    (1, 'Grassland', 50.26, 502600.0,
                     ST_Multi(ST_GeomFromText('POLYGON((13.0 58.0, 13.1 58.0, 13.1 58.1, 13.0 58.1, 13.0 58.0))', 4326))),
                    (2, 'Grassland', 60.0, 600000.0,
                     ST_Multi(ST_GeomFromText('POLYGON((13.2 58.0, 13.3 58.0, 13.3 58.1, 13.2 58.1, 13.2 58.0))', 4326))),
                    (3, 'Barley', 25.0, 250000.0,
                     ST_Multi(ST_GeomFromText('POLYGON((13.4 58.0, 13.5 58.0, 13.5 58.1, 13.4 58.1, 13.4 58.0))', 4326)))
                """
            )

    def tearDown(self):
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS public.{self.relation_name}")

    def test_end_to_end_with_real_adapter(self):
        result = InventoryAlgorithms.sotasen_grass_to_protein(
            geodataset_id=self.dataset.id
        )

        self.assertEqual(len(result["features"]), 2)
        for feature in result["features"]:
            self.assertIsInstance(feature["geom"], GEOSGeometry)
            self.assertEqual(feature["geom"].geom_type, "MultiPolygon")
            self.assertEqual(feature["geom"].srid, 4326)
            self.assertEqual(feature["land_use"], "Grassland")

        self.assertAlmostEqual(
            aggregated_value(result, "Grassland area"), 110.26, places=6
        )
        self.assertAlmostEqual(
            aggregated_value(result, "Total production"), 992.34, places=6
        )
        self.assertAlmostEqual(
            aggregated_value(result, "Crude protein in biomass"), 198.468, places=6
        )
        self.assertAlmostEqual(
            aggregated_value(result, "Recovered protein"), 23.81616, places=6
        )
