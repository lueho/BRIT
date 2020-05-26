from django.test import TestCase

from scenario_builder.models import Scenario, Region, Catchment, Material
from scenario_builder.scenarios import GisInventory
from scenario_evaluation.models import ScenarioResultLayer


class BaseScenarioResultTestCase(TestCase):
    def setUp(self):
        super(BaseScenarioResultTestCase, self).setUp()


class InventoryResultPointLayerTestCase(TestCase):
    fixtures = ['scenarios.json', 'trees.json']

    def setUp(self):
        scenario = Scenario(
            name='Test scenario',
            region=Region.objects.get(name='Hamburg'),
            catchment=Catchment.objects.get(name='Wandsbek'),
            use_default_configuration=True
        )
        scenario.save()
        scenario.feedstocks.add(Material.objects.get(name='prunings'))
        scenario.create_default_configuration()
        self.inventory = GisInventory(scenario)

    def test_inheritance(self):
        pass
        # algorithm = InventoryAlgorithm.objects.get(function_name='avg_point_yield')
        # scenario = Scenario.objects.get(id=1)
        # self.inventory = GisInventory(scenario)
        # self.inventory.run()
        # self.model = self.inventory._create_result_model(algorithm.function_name)
        # model_name = 'scenario_evaluation_result_of_scenario_' + str(scenario.id) + '_algorithm_' + str(algorithm.id)
        # self.assertEqual(self.model._meta.db_table, model_name)

    def test_get_layer_model(self):
        layer = ScenarioResultLayer.objects.create(
            name='existing layer',
            scenario=self.inventory.scenario,
            base_class='InventoryResultPointLayer',
            table_name='non_existing_name'
        )
        self.assertIsInstance(layer, ScenarioResultLayer)
        self.assertRaises(
            ScenarioResultLayer.TableDoesNotExist,
            layer.get_layer_model
        )
        layer.table_name = 'scenario_evaluation_result_of_scenario_4_algorithm_1'
        self.assertEqual(layer.table_name, 'scenario_evaluation_result_of_scenario_4_algorithm_1')
