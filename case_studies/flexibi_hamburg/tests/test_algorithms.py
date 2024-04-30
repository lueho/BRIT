from django.test import TestCase

from case_studies.flexibi_hamburg.algorithms import InventoryAlgorithms
from case_studies.flexibi_hamburg.models import HamburgRoadsideTrees
from distributions.models import TemporalDistribution, Timestep
from inventories.models import Scenario
from maps.models import Catchment, GeoPolygon, Region
from materials.models import SampleSeries, Material, MaterialComponentGroup


class HamburgRoadsideTreesPointYieldTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        for i in range(10):
            HamburgRoadsideTrees.objects.create(
                geom=f'POINT({i} {i})'
            )
        borders = GeoPolygon.objects.create(geom='MULTIPOLYGON(((0 0, 0 10, 10 10, 10 0, 0 0)))')
        region = Region.objects.create(name='Test Region', borders=borders)
        cls.catchment = Catchment.objects.create(name='Test Catchment', region=region)
        cls.scenario = Scenario.objects.create(name='Test Scenario', catchment=cls.catchment)
        material = Material.objects.create(name='Test Material')
        cls.feedstock = SampleSeries.objects.create(name='Test Feedstock', material=material)
        temporal_distribution = TemporalDistribution.objects.create(name='Summer/Winter')
        Timestep.objects.create(name='Summer', distribution=temporal_distribution)
        Timestep.objects.create(name='Winter', distribution=temporal_distribution)
        MaterialComponentGroup.objects.create(name='Macro Components')

    def test_value_error_if_neither_catchment_nor_scenario_is_provided(self):
        with self.assertRaises(ValueError):
            InventoryAlgorithms.hamburg_roadside_tree_production()

    def test_value_error_if_scenario_id_does_not_match_catchment_id(self):
        with self.assertRaises(ValueError):
            InventoryAlgorithms.hamburg_roadside_tree_production(scenario_id=self.scenario.id, catchment_id=self.catchment.id + 999)

    def test_hamburg_roadside_tree_production(self):
        point_yield = {'value': 10, 'standard_deviation': 1}
        result = InventoryAlgorithms.hamburg_roadside_tree_production(
            scenario_id=self.scenario.id,
            feedstock_id=self.feedstock.id,
            point_yield=point_yield
        )
        self.assertIn('aggregated_values', result)
        self.assertIn('aggregated_distributions', result)
        aggregated_values_names = [value['name'] for value in result['aggregated_values']]
        self.assertIn('Count', aggregated_values_names)
        self.assertIn('Total production', aggregated_values_names)
        count = next(value for value in result['aggregated_values'] if value['name'] == 'Count')
        self.assertEqual(count['value'], 10)
        total_production = next(value for value in result['aggregated_values'] if value['name'] == 'Total production')
        self.assertEqual(total_production['unit'], 'Mg/a')
        self.assertEqual(total_production['value'], 0.1)