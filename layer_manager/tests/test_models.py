from django.apps import apps
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Point, Polygon
from django.db import connection
from django.db.models.query import QuerySet
from django.test import TestCase

from case_studies.flexibi_hamburg.models import HamburgGreenAreas
from distributions.models import TemporalDistribution, Timestep
from inventories.models import InventoryAlgorithm, Scenario
from layer_manager.models import (
    DistributionSet,
    DistributionShare,
    Layer,
    LayerAggregatedDistribution,
    LayerField,
)
from maps.models import Catchment, GeoDataset, Region
from materials.models import Material, MaterialComponent, SampleSeries
from materials.utils import ensure_initial_data


class LayerTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        Point(12, 34)
        region = Region.objects.create(name="Test Region")
        catchment = Catchment.objects.create(name="Test Catchment", region=region)
        Scenario.objects.create(
            name="Test Scenario", region=region, catchment=catchment
        )

        geodataset = GeoDataset.objects.create(name="Test Geodataset", region=region)

        feedstock = Material.objects.create(name="Test Feedstock")

        InventoryAlgorithm.objects.create(
            name="Average Point Yield",
            function_name="avg_point_yield",
            geodataset=geodataset,
        )

        InventoryAlgorithm.objects.create(
            name="Average Area Yield",
            function_name="avg_area_yield",
            geodataset=geodataset,
        )

        HamburgGreenAreas.objects.create(
            geom=MultiPolygon(
                [
                    Polygon(((0, 0), (0, 1), (1, 1), (0, 0))),
                    Polygon(((1, 1), (1, 2), (2, 2), (1, 1))),
                ]
            )
        )
        SampleSeries.objects.create(material=feedstock, name="Feedstock Test Series")

    def setUp(self):
        self.scenario = Scenario.objects.get(name="Test Scenario")
        # self.feedstock = Material.objects.get(name='Test Feedstock')
        self.feedstock_sample_series = SampleSeries.objects.get(
            name="Feedstock Test Series"
        )

        self.testkwargs = {
            "name": "test name",
            "scenario": self.scenario,
            "algorithm": InventoryAlgorithm.objects.get(
                function_name="avg_point_yield"
            ),
            "geom_type": "Point",
            "table_name": "test_table_name",
            "feedstock": self.feedstock_sample_series,
        }
        self.fields = {"field1": "float", "field2": "int"}

    def test_update_or_create_feature_collection(self):
        kwargs = self.testkwargs
        layer = Layer.objects.create(**kwargs)
        layer.add_layer_fields(self.fields)
        feature_collection = layer.update_or_create_feature_collection()
        feature_table_fields = [field.name for field in feature_collection._meta.fields]
        for field in self.fields:
            self.assertIn(field, feature_table_fields)
        self.assertEqual(
            feature_collection._meta.db_table, self.testkwargs["table_name"]
        )

    def test_create_feature_table(self):
        kwargs = self.testkwargs
        layer = Layer.objects.create(**kwargs)
        layer.add_layer_fields(self.fields)
        layer.update_or_create_feature_collection()
        layer.create_feature_table()

    def test_create_or_replace(self):

        results = {
            "avg_area_yield": {
                "aggregated_values": [
                    {"name": "Total production", "value": 10000, "unit": "kg"}
                ],
                "features": [],
            }
        }
        areas = HamburgGreenAreas.objects.all()
        for area in areas:
            results["avg_area_yield"]["features"].append(
                {"geom": area.geom, "yield": 12.5}
            )

        # Test creation of completely new layer
        algorithm = InventoryAlgorithm.objects.get(function_name="avg_area_yield")
        layer, feature_collection = Layer.objects.create_or_replace(
            name="new layer",
            scenario=self.scenario,
            feedstock=self.feedstock_sample_series,
            algorithm=algorithm,
            results=results["avg_area_yield"],
        )

        # Is the table name generated correctly?
        self.assertEqual(
            layer.table_name,
            f"result_of_scenario_{self.scenario.id}_algorithm_{algorithm.id}_feedstock_{self.feedstock_sample_series.id}",
        )
        # Have all fields been created correctly?
        stored_fields = {}
        for field in layer.layer_fields.all():
            stored_fields[field.field_name] = field.data_type
        expected_fields = {"yield": "float"}
        self.assertDictEqual(stored_fields, expected_fields)
        # Was the new table created in the database?
        table_name = f"result_of_scenario_{self.scenario.id}_algorithm_{algorithm.id}_feedstock_{self.feedstock_sample_series.id}"
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT to_regclass('{table_name}')")
            self.assertTrue(cursor.fetchone()[0])
        # Was the model registered in the app?
        self.assertTrue(apps.all_models["layer_manager"][table_name])
        del apps.all_models["layer_manager"][table_name]

        # Test creation of layer that already exists but has equal shape

        Layer.objects.create_or_replace(
            name="second new layer",
            scenario=self.scenario,
            feedstock=self.feedstock_sample_series,
            algorithm=algorithm,
            results=results["avg_area_yield"],
        )
        del apps.all_models["layer_manager"][table_name]

    def test_get_feature_collection(self):

        results = {
            "avg_area_yield": {
                "aggregated_values": [
                    {"name": "Total production", "value": 10000, "unit": "kg"}
                ],
                "features": [],
            }
        }
        areas = HamburgGreenAreas.objects.all()
        for area in areas:
            results["avg_area_yield"]["features"].append(
                {"geom": area.geom, "avg_yield": 12.5}
            )

        algorithm = InventoryAlgorithm.objects.get(function_name="avg_area_yield")
        Layer.objects.create_or_replace(
            name="second layer",
            scenario=self.scenario,
            feedstock=self.feedstock_sample_series,
            algorithm=algorithm,
            results=results["avg_area_yield"],
        )

        # If the model is found in registry
        layer = Layer.objects.get(name="second layer")
        self.assertEqual(
            layer.table_name,
            f"result_of_scenario_{self.scenario.id}_algorithm_{algorithm.id}_feedstock_{self.feedstock_sample_series.id}",
        )
        self.assertIn(layer.table_name, apps.all_models["layer_manager"])
        layer_model = layer.get_feature_collection()
        self.assertIn(layer_model._meta.db_table, apps.all_models["layer_manager"])
        layer_fields = [field.name for field in layer_model._meta.fields]
        expected_layer_fields = ["id", "geom", "avg_yield"]
        self.assertListEqual(layer_fields, expected_layer_fields)

        # If the model is not registered and needs to be recreated
        del apps.all_models["layer_manager"][
            f"result_of_scenario_{self.scenario.id}_algorithm_{algorithm.id}_feedstock_{self.feedstock_sample_series.id}"
        ]
        recreated_model = Layer.objects.get(
            name="second layer"
        ).get_feature_collection()
        layer_fields = [field.name for field in recreated_model._meta.fields]
        expected_layer_fields = ["id", "geom", "avg_yield"]
        self.assertListEqual(layer_fields, expected_layer_fields)

        recreated_model.objects.create(
            geom=GEOSGeometry(
                "MULTIPOLYGON (((10.17167457379291 53.60625338138375,"
                "10.17167507310276 53.60625067078598,"
                " 10.17159493630427 53.60625228240507,"
                " 10.17167457379291 53.60625338138375)))"
            ),
            avg_yield=12.5,
        )
        table_name = f"result_of_scenario_{self.scenario.id}_algorithm_{algorithm.id}_feedstock_{self.feedstock_sample_series.id}"
        query = f"""
            -- noinspection SqlResolve
            SELECT avg_yield FROM {table_name}
        """

        with connection.cursor() as cursor:
            cursor.execute(query)
            features = cursor.fetchall()

        self.assertEqual(features[1][0], 12.5)

    def test_is_defined_by(self):
        kwargs = {
            "table_name": "test_table",
            "geom_type": "point",
            "feedstock": self.feedstock_sample_series,
            "scenario": self.scenario,
            "algorithm": InventoryAlgorithm.objects.get(name="Average Point Yield"),
        }
        layer = Layer.objects.create(**kwargs)

        field_definitions = {"field1": "float", "field2": "int"}
        for field_name, data_type in field_definitions.items():
            layer.layer_fields.add(
                LayerField.objects.create(field_name=field_name, data_type=data_type)
            )

        kwargs["fields"] = field_definitions
        self.assertTrue(layer.is_defined_by(**kwargs))


class LayerAggregatedDistributionTestCase(TestCase):

    def setUp(self):
        self.component = MaterialComponent.objects.default()
        self.timestep = Timestep.objects.default()
        self.distribution = TemporalDistribution.objects.default()
        self.aggregated_distribution = LayerAggregatedDistribution.objects.create(
            name="Test distribution", distribution=self.distribution
        )
        self.distribution_set = DistributionSet.objects.create(
            aggregated_distribution=self.aggregated_distribution,
            timestep=self.timestep,
        )
        self.share = DistributionShare.objects.create(
            distribution_set=self.distribution_set,
            component=self.component,
            average=1.23,
            standard_deviation=0.02,
        )

    def test_shares(self):
        shares = self.aggregated_distribution.shares
        self.assertIsInstance(shares, QuerySet)
        self.assertEqual(shares.count(), 1)
        share = shares.first()
        self.assertEqual(share.average, 1.23)

    def test_components(self):
        components = self.aggregated_distribution.components
        self.assertIsInstance(components, QuerySet)
        self.assertEqual(components.count(), 1)
        component = components.first()
        self.assertEqual(component.name, self.component.name)

    def test_serialized(self):
        expected = [
            {
                "label": self.component.name,
                "data": {"Average": self.share.average},
                "unit": "Mg/a",
            }
        ]
        self.assertListEqual(expected, self.aggregated_distribution.serialized)
