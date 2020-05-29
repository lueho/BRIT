from django.contrib.gis.geos import GEOSGeometry
from django.test import TestCase

from gis_source_manager.models import HamburgRoadsideTrees, HamburgGreenAreas
from .models import Catchment, Material, Region, Scenario
from .scenarios import GisInventory


class GisInventoryTestCase(TestCase):
    fixtures = ['regions.json', 'catchments.json', 'scenarios.json', 'trees.json', 'parks.json']

    def setUp(self):
        scenario = Scenario(
            name='Test scenario',
            region=Region.objects.get(name='Hamburg'),
            catchment=Catchment.objects.get(name='Wandsbek'),
            use_default_configuration=True
        )
        scenario.save()
        scenario.feedstocks.add(Material.objects.get(name='Tree prunings (winter)'))
        scenario.create_default_configuration()
        self.inventory = GisInventory(scenario)

    def test_load_inventory_config(self):
        self.assertIsInstance(self.inventory, GisInventory)
        self.assertIsInstance(self.inventory.scenario, Scenario)
        self.assertEqual(self.inventory.scenario.name, 'Test scenario')
        self.assertIsInstance(self.inventory.config, dict)
        config = {
            'avg_point_yield': {
                'point_yield': {
                    'value': 10.5,
                    'standard_deviation': 0.5
                }
            },
            'avg_area_yield': {
                'area_yield': {
                    'value': 0.1,
                    'standard_deviation': 0.05
                }
            }
        }
        self.assertDictEqual(self.inventory.config, config)

    def test_set_gis_source_model(self):
        self.inventory.set_gis_source_model('HamburgRoadsideTrees')
        self.assertIsInstance(self.inventory.gis_source_model(), HamburgRoadsideTrees)

    def test_avg_point_yield(self):
        self.assertEqual(self.inventory.catchment.name, 'Wandsbek')

    def test_save_results_in_database(self):
        self.inventory.results = {
            'avg_point_yield': {
                'trees_count': 10000,
                'total_yield': 150000,
                'features': [
                    {
                        'geom': GEOSGeometry('POINT (10.120232 53.712156)'),
                        'point_yield_average': 15.0,
                        'point_yield_standard_deviation': 5.0
                    }
                ]
            }
        }

    def test_clip_polygons(self):
        input_qs = HamburgGreenAreas.objects.all()
        mask_qs = Catchment.objects.filter(name='Harburg')
        clipped = GisInventory.clip_polygons(input_qs, mask_qs)
        self.assertEqual(len(clipped), 372)

    def test_run(self):
        self.assertIsNone(self.inventory.results)
        self.inventory.run()
        self.assertIsNotNone(self.inventory.results)
