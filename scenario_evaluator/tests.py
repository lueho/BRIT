from django.db.models.query import QuerySet
from django.test import TestCase

from material_manager.models import Material, BaseObjects
from scenario_builder.models import Scenario, GeoDataset, Region, Catchment, InventoryAlgorithm, \
    InventoryAlgorithmParameter, InventoryAlgorithmParameterValue, ScenarioInventoryConfiguration
from scenario_evaluator.evaluations import ScenarioResult
from users.models import ReferenceUsers


class ScenarioResultTestCase(TestCase):
    fixtures = ['user.json', 'regions.json', 'catchments.json']

    def setUp(self):
        self.user = ReferenceUsers.objects.get.standard_owner
        self.material = Material.objects.create(
            name='First test material',
            owner=self.user,
            is_feedstock=True
        )
        self.gds = GeoDataset.objects.create(
            name='Hamburg Roadside Trees',
            description='',
            region=Region.objects.get(name='Hamburg'),
            model_name='HamburgRoadsideTrees'
        )
        self.scenario = Scenario.objects.create(
            name='Test scenario',
            description='Scenario for automated testing',
            region=Region.objects.get(name='Hamburg'),
            catchment=Catchment.objects.get(name='Harburg'),
            owner=self.user
        )
        self.alg = InventoryAlgorithm.objects.create(
            name='TestAlgorithm',
            description='',
            source_module='flexibi_hamburg',
            function_name='hamburg_roadside_tree_production',
            geodataset=self.gds,
            default=True
        )
        self.alg.feedstock.add(self.material)
        self.parameter = InventoryAlgorithmParameter.objects.create(
            descriptive_name='Parameter',
            short_name='point_yield',
            is_required=True
        )
        self.parameter.inventory_algorithm.add(self.alg)
        self.value = InventoryAlgorithmParameterValue.objects.create(
            name='Parameter value',
            parameter=self.parameter,
            value=1.23,
            standard_deviation=0.0,
            default=True
        )
        self.config = ScenarioInventoryConfiguration.objects.create(
            scenario=self.scenario,
            feedstock=self.material.standard_settings,
            geodataset=self.gds,
            inventory_algorithm=self.alg,
            inventory_parameter=self.parameter,
            inventory_value=self.value
        )

    def test_create(self):
        result = ScenarioResult(self.scenario)
        self.assertIsInstance(result, ScenarioResult)
        self.assertIsInstance(result.scenario, Scenario)

    def test_material_component_groups(self):
        result = ScenarioResult(self.scenario)
        group_settings = result.material_component_groups()
        self.assertIsInstance(group_settings, list)
        self.assertEqual(len(group_settings), 0)

    def test_distributions(self):
        result = ScenarioResult(self.scenario)
        distributions = result.distributions()
        self.assertIsInstance(distributions, QuerySet)
        self.assertEqual(distributions.count(), 1)
        distribution = distributions.first()
        self.assertEqual(distribution.name, BaseObjects.objects.get.base_distribution)

    # def test_total_production_per_feedstock(self):
    #     run_inventory(self.scenario.id)
    #     res = ScenarioResult(self.scenario)
    #     self.assertEqual(Layer.objects.all().count(), 1)
    #     self.assertIsNotNone(res.layers)
    #     self.assertIsInstance(res.layers, list)
    #     self.assertIsInstance(res.layers[0].feedstock, MaterialSettings)


# class ScenarioResultTooTestCase(TestCase):
#     fixtures = ['regions.json', 'catchments.json', 'trees.json', 'parks.json', 'scenarios.json', 'layers.json']
#
#     def test_total_annual_production(self):
#         scenario = Scenario.objects.get(name='Hamburg standard')
#         result = ScenarioResult(scenario)
#         total_production = result.total_annual_production()
#         self.assertEqual(int(total_production), 10996)
#
#     def test_total_production_per_feedstock(self):
#         scenario = Scenario.objects.get(name='Hamburg standard')
#         result = ScenarioResult(scenario)
#         production = result.total_production_per_feedstock()
#         expected_result = {'Tree prunings (winter)': 10996.527193793003}
#         self.assertDictEqual(production, expected_result)
#
#     def test_production_values_for_plot(self):
#         scenario = Scenario.objects.get(name='Hamburg standard')
#         result = ScenarioResult(scenario)
#         labels, values = result.production_values_for_plot()
#         self.assertListEqual(labels, ["Tree prunings (winter)"])
#         self.assertListEqual(values, [10996.527193793003])
#
#     def test_async_run_inventory(self):
#         scenario = Scenario.objects.get(id=4)
#         # Must delete layers first because there is no result table connected to it.
#         layers = Layer.objects.filter(scenario=scenario)
#         for layer in layers:
#             layer.delete()
#         self.assertEqual(scenario.name, 'Hamburg standard')
#         result = run_inventory(4)
#         self.assertEqual(result, 'Inventory for scenario 4 completed.')
