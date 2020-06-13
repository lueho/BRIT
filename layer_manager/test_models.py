from django.apps import apps
from django.contrib.gis.geos import GEOSGeometry
from django.db import connection
from django.test import TestCase

from gis_source_manager.models import HamburgGreenAreas
from scenario_builder.models import Scenario, InventoryAlgorithm
from .models import Layer, LayerField


class LayerTestCase(TestCase):
    fixtures = ['regions.json', 'scenarios.json', 'layers.json', 'catchments.json', 'parks.json']

    def setUp(self):

        self.testkwargs = {
            'name': 'test name',
            'scenario': Scenario.objects.get(name='Hamburg standard'),
            'algorithm': InventoryAlgorithm.objects.get(function_name='avg_point_yield'),
            'geom_type': 'Point',
            'table_name': 'test_table_name',
        }
        self.fields = {'field1': 'float', 'field2': 'int'}

    def test_update_or_create_feature_collection(self):
        kwargs = self.testkwargs
        layer = Layer.objects.create(**kwargs)
        layer.add_layer_fields(self.fields)
        feature_collection = layer.update_or_create_feature_collection()
        feature_table_fields = [field.name for field in feature_collection._meta.fields]
        for field in self.fields:
            self.assertIn(field, feature_table_fields)
        self.assertEqual(feature_collection._meta.db_table, self.testkwargs['table_name'])

    def test_create_feature_table(self):
        kwargs = self.testkwargs
        layer = Layer.objects.create(**kwargs)
        layer.add_layer_fields(self.fields)
        layer.update_or_create_feature_collection()
        layer.create_feature_table()

    def test_create_or_replace(self):

        results = {
            'avg_area_yield': {
                'aggregated_values': [
                    {
                        'name': 'Total production',
                        'value': 10000,
                        'unit': 'kg'
                    }
                ],
                'features': []
            }
        }
        areas = HamburgGreenAreas.objects.filter(ortsteil=123)
        for area in areas:
            results['avg_area_yield']['features'].append({'geom': area.geom, 'yield': 12.5})

        # Test creation of completely new layer
        scenario = Scenario.objects.get(name='Hamburg standard')
        algorithm = InventoryAlgorithm.objects.get(function_name='avg_area_yield')
        layer, feature_collection = Layer.objects.create_or_replace(name='new layer',
                                                                    scenario=scenario,
                                                                    algorithm=algorithm,
                                                                    results=results['avg_area_yield'])

        # Is the table name generated correctly?
        self.assertEqual(layer.table_name, 'result_of_scenario_4_algorithm_3')
        # Have all fields been created correctly?
        stored_fields = {}
        for field in layer.layer_fields.all():
            stored_fields[field.field_name] = field.data_type
        expected_fields = {'yield': 'float'}
        self.assertDictEqual(stored_fields, expected_fields)
        # Was the new table created in the database?
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT to_regclass('result_of_scenario_4_algorithm_3')")
            self.assertTrue(cursor.fetchone()[0])
        # Was the model registered in the app?
        self.assertTrue(apps.all_models['layer_manager']['result_of_scenario_4_algorithm_3'])
        del apps.all_models['layer_manager']['result_of_scenario_4_algorithm_3']

        # Test creation of layer that already exists but has equal shape

        Layer.objects.create_or_replace(name='second new layer',
                                        scenario=scenario,
                                        algorithm=algorithm,
                                        results=results['avg_area_yield'])
        del apps.all_models['layer_manager']['result_of_scenario_4_algorithm_3']

    def test_get_feature_collection(self):

        results = {
            'avg_area_yield': {
                'aggregated_values': [
                    {
                        'name': 'Total production',
                        'value': 10000,
                        'unit': 'kg'
                    }
                ],
                'features': []
            }
        }
        areas = HamburgGreenAreas.objects.filter(ortsteil=123)
        for area in areas:
            results['avg_area_yield']['features'].append({'geom': area.geom, 'avg_yield': 12.5})

        scenario = Scenario.objects.get(name='Hamburg standard')
        algorithm = InventoryAlgorithm.objects.get(function_name='avg_area_yield')
        Layer.objects.create_or_replace(name='second layer',
                                        scenario=scenario,
                                        algorithm=algorithm,
                                        results=results['avg_area_yield'])

        # If the model is found in registry
        layer = Layer.objects.get(name='second layer')
        self.assertEqual(layer.table_name, 'result_of_scenario_4_algorithm_3')
        self.assertIn(layer.table_name, apps.all_models['layer_manager'])
        layer_model = layer.get_feature_collection()
        self.assertIn(layer_model._meta.db_table, apps.all_models['layer_manager'])
        layer_fields = [field.name for field in layer_model._meta.fields]
        expected_layer_fields = ['id', 'geom', 'avg_yield']
        self.assertListEqual(layer_fields, expected_layer_fields)

        # If the model is not registered and needs to be recreated
        del apps.all_models['layer_manager']['result_of_scenario_4_algorithm_3']
        recreated_model = Layer.objects.get(name='second layer').get_feature_collection()
        layer_fields = [field.name for field in recreated_model._meta.fields]
        expected_layer_fields = ['id', 'geom', 'avg_yield']
        self.assertListEqual(layer_fields, expected_layer_fields)

        recreated_model.objects.create(geom=GEOSGeometry('MULTIPOLYGON (((10.17167457379291 53.60625338138375,'
                                                         '10.17167507310276 53.60625067078598,'
                                                         ' 10.17159493630427 53.60625228240507,'
                                                         ' 10.17167457379291 53.60625338138375)))'),
                                       avg_yield=12.5
                                       )

        query = """
            -- noinspection SqlResolve
            SELECT avg_yield FROM result_of_scenario_4_algorithm_3
        """

        with connection.cursor() as cursor:
            cursor.execute(query)
            features = cursor.fetchall()

        self.assertEqual(features[1][0], 12.5)

    def test_is_defined_by(self):
        kwargs = {
            'table_name': 'test_table',
            'geom_type': 'point',
            'scenario': Scenario.objects.get(name='Hamburg standard'),
            'algorithm': InventoryAlgorithm.objects.get(name='Average point yield'),
        }
        layer = Layer.objects.create(**kwargs)

        field_definitions = {'field1': 'float',
                             'field2': 'int'}
        for field_name, data_type in field_definitions.items():
            layer.layer_fields.add(LayerField.objects.create(field_name=field_name, data_type=data_type))

        kwargs['fields'] = field_definitions
        self.assertTrue(layer.is_defined_by(**kwargs))
