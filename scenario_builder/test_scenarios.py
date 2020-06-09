from django.test import TestCase

from gis_source_manager.models import HamburgGreenAreas
from .models import Catchment, Region, Scenario, InventoryAlgorithm
from .scenarios import GisInventory


class GisInventoryTestCase(TestCase):
    fixtures = ['regions.json', 'catchments.json', 'scenarios.json', 'trees.json', 'parks.json']

    def setUp(self):
        scenario = Scenario.objects.create(
            name='Test scenario',
            region=Region.objects.get(name='Hamburg'),
            catchment=Catchment.objects.get(name='Wandsbek'),
        )
        scenario.add_inventory_algorithm(InventoryAlgorithm.objects.get(function_name='avg_point_yield'))
        scenario.add_inventory_algorithm(InventoryAlgorithm.objects.get(function_name='avg_area_yield'))
        self.inventory = GisInventory(scenario)

    def test_avg_point_yield(self):
        self.assertEqual(self.inventory.catchment.name, 'Wandsbek')

    def test_save_results_in_database(self):
        pass

    def test_clip_polygons(self):
        input_qs = HamburgGreenAreas.objects.all()
        mask_qs = Catchment.objects.filter(name='Harburg')
        clipped = GisInventory.clip_polygons(input_qs, mask_qs)
        self.assertEqual(len(clipped), 372)

    def test_run(self):
        self.assertIsNone(self.inventory.results)
        self.inventory.run()
        self.assertIsNotNone(self.inventory.results)
