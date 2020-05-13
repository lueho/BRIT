from django.contrib.gis.geos import GEOSGeometry
from django.db import connection

from gis_source_manager.models import HamburgRoadsideTrees
from .models import Catchment, Region, Scenario
from .scenarios import GisInventory
from .test_models import ScenarioTestCase


class GisInventoryTestCase(ScenarioTestCase):
    fixtures = ['trees.json']

    def setUp(self):
        super(GisInventoryTestCase, self).setUp()
        scenario = Scenario.objects.get(name='Test scenario')
        scenario.create_default_configuration()
        self.inventory = GisInventory(scenario)

    def test_init(self):
        self.assertIsInstance(self.inventory.scenario, Scenario)
        self.assertEqual(self.inventory.scenario.name, 'Test scenario')
        self.assertIsInstance(self.inventory.catchment, Catchment)
        self.assertEqual(self.inventory.catchment.name, 'Harburg')
        self.assertIsInstance(self.inventory.region, Region)
        self.assertEqual(self.inventory.region.name, 'Hamburg')

    def test_load_inventory_config(self):
        self.assertIsInstance(self.inventory, GisInventory)
        self.assertIsInstance(self.inventory.scenario, Scenario)
        self.assertEqual(self.inventory.scenario.name, 'Test scenario')
        self.assertIsInstance(self.inventory.config, dict)
        config = {
            'avg_point_yield': {
                'avg': 10.1
            }
        }
        self.assertDictEqual(self.inventory.config, config)

    def test_set_gis_source_model(self):
        self.inventory.set_gis_source_model('HamburgRoadsideTrees')
        self.assertIsInstance(self.inventory.gis_source_model(), HamburgRoadsideTrees)

    def test_avg_point_yield(self):
        self.assertEqual(self.inventory.catchment.name, 'Harburg')

    def test_run(self):
        self.assertIsNone(self.inventory.results)
        self.inventory.run()
        self.assertIsNotNone(self.inventory.results)

    # noinspection PyPep8Naming
    def test_create_result_model(self):
        ResultModel = self.inventory.create_result_model('avg_point_yield')
        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(ResultModel)
        ResultModel.objects.create(
            geom=GEOSGeometry('POINT (10.120232 53.712156)'),
            average=10.1,
            standard_deviation=0.2
        )
        result = ResultModel.objects.all()[:1]
        self.assertIsInstance(result[0], ResultModel)

    def test_save_result_table(self):
        self.inventory.run()
        self.inventory.save_result_table()
