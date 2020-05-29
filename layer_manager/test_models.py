from django.apps import apps
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.geos import Point
from django.db import models, connection
from django.test import TestCase

from scenario_builder.models import Scenario, InventoryAlgorithm
from .models import Layer, LayerField
from .models import ModelAlreadyRegistered, TableAlreadyExists


class LayerTestCase(TestCase):
    fixtures = ['regions.json', 'scenarios.json', 'layers.json', 'catchments.json']

    def setUp(self):
        self.fields = {'field1': 'float',
                       'fieldnumber2': 'int'
                       }
        self.name = 'name'
        self.geom_type = 'Point'

    def test_create_layer_model(self):
        model = Layer.objects._create_layer_model(fields=self.fields,
                                                  geom_type='Point',
                                                  table_name='test_table_name')
        model_fields = [field.name for field in model._meta.fields]
        for field in self.fields:
            self.assertIn(field, model_fields)
        self.assertEqual(model._meta.db_table, 'test_table_name')

        def create_duplicate():
            Layer.objects._create_layer_model(fields=self.fields,
                                              geom_type='point',
                                              table_name='test_table_name')

        self.assertRaises(ModelAlreadyRegistered, create_duplicate)
        # del apps.all_models['layer_manager']['result_of_scenario_1_algorithm_1']

    def test_create_layer_table(self):
        Layer.objects._create_layer_table(type('test_model', (models.Model,), {'__module__': 'layer_manager.models'}))
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT to_regclass('layer_manager_test_model')")
            self.assertTrue(cursor.fetchone()[0])

        def create_duplicate_table():
            model = type('test_model_2', (models.Model,), {'__module__': 'layer_manager.models'})
            model._meta.db_table = 'layer_manager_test_model'
            Layer.objects._create_layer_table(model)

        self.assertRaises(TableAlreadyExists, create_duplicate_table)

    def test_create_or_replace_layer(self):

        # Test creation of completely new layer
        scenario = Scenario.objects.get(name='Hamburg standard')
        algorithm = InventoryAlgorithm.objects.get(name='Average point yield')
        layer = Layer.objects.create_or_replace_layer(name='new layer',
                                                      geom_type=Point,
                                                      scenario=scenario,
                                                      algorithm=algorithm,
                                                      fields=self.fields)

        # Is the table name generated correctly?
        self.assertEqual(layer.table_name, 'result_of_scenario_4_algorithm_1')
        # Have all fields been created correctly?
        stored_fields = {}
        for field in layer.layer_fields.all():
            stored_fields[field.field_name] = field.data_type
        expected_fields = self.fields
        self.assertDictEqual(stored_fields, expected_fields)
        # Was the new table created in the database?
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT to_regclass('result_of_scenario_4_algorithm_1')")
            self.assertTrue(cursor.fetchone()[0])
        # Was the model registered in the app?
        self.assertTrue(apps.all_models['layer_manager']['result_of_scenario_4_algorithm_1'])
        del apps.all_models['layer_manager']['result_of_scenario_4_algorithm_1']

        # Test creation of layer that already exists but has equal shape

        Layer.objects.create_or_replace_layer(name='second new layer',
                                              geom_type=Point,
                                              scenario=scenario,
                                              algorithm=algorithm,
                                              fields=self.fields)
        del apps.all_models['layer_manager']['result_of_scenario_4_algorithm_1']

        # Test creation of layer that already exists with a different shape
        other_fields = {'other field 1': 'int',
                        'other field 2': 'float',
                        'new field 3': 'str'}
        Layer.objects.create_or_replace_layer(name='second new layer',
                                              geom_type=Point,
                                              scenario=scenario,
                                              algorithm=algorithm,
                                              fields=other_fields)
        del apps.all_models['layer_manager']['result_of_scenario_4_algorithm_1']

    def test_get_layer_model(self):
        scenario = Scenario.objects.get(name='Hamburg standard')
        algorithm = InventoryAlgorithm.objects.get(name='Average point yield')
        Layer.objects.create_or_replace_layer(name='second layer',
                                              geom_type=Point,
                                              scenario=scenario,
                                              algorithm=algorithm,
                                              fields=self.fields)

        # If the model is found in registry
        layer = Layer.objects.get(name='second layer')
        self.assertEqual(layer.table_name, 'result_of_scenario_4_algorithm_1')
        self.assertIn(layer.table_name, apps.all_models['layer_manager'])
        layer_model = layer.get_layer_model()
        self.assertIn(layer_model._meta.db_table, apps.all_models['layer_manager'])
        layer_fields = [field.name for field in layer_model._meta.fields]
        expected_layer_fields = ['id', 'geom', 'field1', 'fieldnumber2']
        self.assertListEqual(layer_fields, expected_layer_fields)

        # If the model is not registered and needs to be recreated
        del apps.all_models['layer_manager']['result_of_scenario_4_algorithm_1']
        recreated_model = Layer.objects.get(name='second layer').get_layer_model()
        layer_fields = [field.name for field in recreated_model._meta.fields]
        expected_layer_fields = ['id', 'geom', 'field1', 'fieldnumber2']
        self.assertListEqual(layer_fields, expected_layer_fields)

        recreated_model.objects.create(geom=GEOSGeometry('POINT (10.120232 53.712156)'),
                                       field1=1.5,
                                       fieldnumber2=2.3)

        query = """
            -- noinspection SqlResolve
            SELECT field1 FROM result_of_scenario_4_algorithm_1
        """

        with connection.cursor() as cursor:
            cursor.execute()
            features = cursor.fetchall(query)

        self.assertEqual(features[0][0], 1.5)

    def test_store_field_definitions(self):
        pass

    def test_is_identical_layer(self):
        kwargs = {
            'table_name': 'test_table',
            'geom_type': 'point',
            'scenario': Scenario.objects.get(name='Hamburg standard'),
            'algorithm': InventoryAlgorithm.objects.get(name='Average point yield'),
        }
        layer = Layer.objects.create(**kwargs)

        field_definitions = {'field1': 'float',
                             'fieldnumber2': 'int'}
        for field_name, data_type in field_definitions.items():
            layer.layer_fields.add(LayerField.objects.create(field_name=field_name, data_type=data_type))

        kwargs['fields'] = field_definitions
        self.assertTrue(Layer.objects._is_identical_layer(layer, **kwargs))
