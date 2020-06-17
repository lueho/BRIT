from django.test import TestCase

from layer_manager.models import Layer
from scenario_builder.models import Scenario
from scenario_builder.views import run_inventory
from scenario_evaluator.evaluations import ScenarioResult


class ScenarioResultTestCase(TestCase):
    fixtures = ['regions.json', 'catchments.json', 'trees.json', 'parks.json', 'scenarios.json', 'layers.json']

    def test_total_annual_production(self):
        scenario = Scenario.objects.get(name='Hamburg standard')
        result = ScenarioResult(scenario)
        total_production = result.total_annual_production()
        self.assertEqual(int(total_production), 10996)

    def test_total_production_per_feedstock(self):
        scenario = Scenario.objects.get(name='Hamburg standard')
        result = ScenarioResult(scenario)
        production = result.total_production_per_feedstock()
        expected_result = {'Tree prunings (winter)': 10996.527193793003}
        self.assertDictEqual(production, expected_result)

    def test_production_values_for_plot(self):
        scenario = Scenario.objects.get(name='Hamburg standard')
        result = ScenarioResult(scenario)
        labels, values = result.production_values_for_plot()
        self.assertListEqual(labels, ["Tree prunings (winter)"])
        self.assertListEqual(values, [10996.527193793003])

    def test_async_run_inventory(self):
        scenario = Scenario.objects.get(id=4)
        # Must delete layers first because there is no result table connected to it.
        layers = Layer.objects.filter(scenario=scenario)
        for layer in layers:
            layer.delete()
        self.assertEqual(scenario.name, 'Hamburg standard')
        result = run_inventory(4)
        self.assertEqual(result, 'Inventory for scenario 4 completed.')
