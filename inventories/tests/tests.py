from django.contrib.auth.models import User
from django.test import TestCase

from distributions.models import TemporalDistribution, Timestep
from inventories.models import (WrongParameterForInventoryAlgorithm)
from materials.models import MaterialComponent, MaterialComponentGroup, MaterialSettings


class RegionTestCase(TestCase):
    fixtures = ['regions.json']

    def setUp(self):
        pass

    def test_create(self):
        region = Region.objects.get(name='Hamburg')
        self.assertEqual(region.name, 'Hamburg')


class CatchmentTestCase(TestCase):
    fixtures = ['user.json', 'regions.json', 'catchments.json']

    def test_create(self):
        catchment = Catchment.objects.get(name='Wandsbek')
        self.assertEqual(catchment.name, 'Wandsbek')


class GeoDatasetTestCase(TestCase):
    fixtures = ['user.json', 'regions.json', 'catchments.json']

    def test_create(self):
        ds = GeoDataset.objects.create(
            name='Hamburg Roadside Trees',
            description='',
            region=Region.objects.get(name='Hamburg'),
            model_name='HamburgRoadsideTrees'
        )
        self.assertIsInstance(ds, GeoDataset)


class InventoryAlgorithmTestCase(TestCase):
    fixtures = ['user.json', 'regions.json', 'catchments.json']

    def setUp(self):
        self.superuser = User.objects.create_superuser(username='superuser')
        self.user = User.objects.create(username='standard_user')
        self.base_distribution = TemporalDistribution.objects.create(
            name='Average',
            owner=self.superuser
        )
        self.base_timestep = Timestep.objects.create(
            name='Average',
            owner=self.superuser,
            distribution=self.base_distribution
        )
        self.base_group = MaterialComponentGroup.objects.create(
            name='Total Material',
            owner=self.superuser
        )
        self.base_component = MaterialComponent.objects.create(
            name='Fresh Matter (FM)',
            owner=self.superuser
        )
        self.feedstock = Material.objects.create(
            name='Feedstock',
            owner=self.user,
        )
        self.gds = GeoDataset.objects.create(
            name='Hamburg Roadside Trees',
            description='',
            region=Region.objects.get(name='Hamburg'),
            model_name='HamburgRoadsideTrees'
        )

    def test_create(self):
        alg = InventoryAlgorithm.objects.create(
            name='TestAlgorithm',
            description='',
            source_module='flexibi_hamburg',
            function_name='hamburg_roadside_tree_production',
            geodataset=self.gds,
            default=True
        )
        self.assertIsInstance(alg, InventoryAlgorithm)
        alg.feedstock.add(self.feedstock)


# class InventoryAlgorithmParameterTestCase(TestCase):
#     fixtures = ['regions.json', 'catchments.json', 'scenarios.json']
#
#     def test_create(self):
#         param = InventoryAlgorithmParameter.objects.get(id=1)
#         self.assertEqual(param.short_name, 'point_yield')
#
#
# class InventoryAlgorithmParameterValueTestCase(TestCase):
#     fixtures = ['regions.json', 'catchments.json', 'scenarios.json']
#
#     def test_create(self):
#         param_value = InventoryAlgorithmParameterValue.objects.get(id=1)
#         self.assertEqual(param_value.value, 10.5)
#         self.assertEqual(param_value.standard_deviation, 0.5)

class ScenarioInventoryConfigurationTestCase(TestCase):
    fixtures = ['user.json', 'regions.json', 'catchments.json']

    def setUp(self):
        self.user = ReferenceUsers.objects.get.standard_owner
        self.material = Material.objects.create(
            name='First test material',
            owner=self.user,
        )
        self.scenario = Scenario.objects.create(
            name='Test scenario',
            description='Scenario for automated testing',
            region=Region.objects.get(name='Hamburg'),
            catchment=Catchment.objects.get(name='Harburg'),
            owner=self.user
        )
        self.gds = GeoDataset.objects.create(
            name='Hamburg Roadside Trees',
            description='',
            region=Region.objects.get(name='Hamburg'),
            model_name='HamburgRoadsideTrees'
        )
        self.alg = InventoryAlgorithm.objects.create(
            name='TestAlgorithm',
            description='',
            source_module='flexibi_hamburg',
            function_name='hamburg_roadside_tree_production',
            geodataset=self.gds,
            default=True
        )
        self.parameter = InventoryAlgorithmParameter.objects.create(
            descriptive_name='Parameter',
            short_name='short_name',
            is_required=True
        )
        self.parameter.inventory_algorithm.add(self.alg)
        self.value = InventoryAlgorithmParameterValue.objects.create(
            name='Parameter value',
            parameter=self.parameter,
            value=1.23,
            default=True
        )

    def test_create(self):
        entry = ScenarioInventoryConfiguration.objects.create(
            scenario=self.scenario,
            feedstock=self.material.standard_settings,
            geodataset=self.gds,
            inventory_algorithm=self.alg,
            inventory_parameter=self.parameter,
            inventory_value=self.value
        )
        self.assertIsInstance(entry, ScenarioInventoryConfiguration)


class ScenarioTestCase(TestCase):
    fixtures = ['user.json', 'regions.json', 'catchments.json']

    def setUp(self):
        self.user = ReferenceUsers.objects.get.standard_owner
        self.material = Material.objects.create(
            name='First test material',
            owner=self.user,
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
            short_name='short_name',
            is_required=True
        )
        self.parameter.inventory_algorithm.add(self.alg)
        self.value = InventoryAlgorithmParameterValue.objects.create(
            name='Parameter value',
            parameter=self.parameter,
            value=1.23,
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
        params = {
            'name': 'test scenario',
            'region': Region.objects.get(name='Hamburg'),
            'catchment': Catchment.objects.get(name='Harburg')

        }
        scenario = Scenario.objects.create(**params)
        self.assertIsInstance(scenario, Scenario)

    def test_available_feedstocks(self):
        feedstocks = self.scenario.available_feedstocks()
        self.assertIsInstance(feedstocks, QuerySet)
        self.assertEqual(feedstocks.count(), 1)
        feedstock = feedstocks[0]
        self.assertIsInstance(feedstock, MaterialSettings)
        self.assertEqual(feedstock, self.alg.feedstock.first().standard_settings)
        self.assertEqual(feedstock.material, self.material)

    def test_feedstocks(self):
        feedstocks = self.scenario.feedstocks()
        self.assertIsInstance(feedstocks, QuerySet)
        self.assertEqual(feedstocks.count(), 1)
        test_feedstock = feedstocks[0]
        self.assertIsInstance(test_feedstock, MaterialSettings)
        self.assertEqual(test_feedstock, self.material.standard_settings)
        self.assertEqual(test_feedstock.material, self.material)

    def test_available_geodatasets(self):
        datasets = self.scenario.available_geodatasets(feedstock=self.material)
        self.assertIsInstance(datasets, QuerySet)
        self.assertEqual(datasets.count(), 1)
        option = datasets[0]
        self.assertIsInstance(option, GeoDataset)
        self.assertEqual(option, self.gds)

    def test_evaluated_geodatasets(self):
        datasets = self.scenario.evaluated_geodatasets(feedstock=self.material)
        self.assertIsInstance(datasets, QuerySet)
        self.assertEqual(datasets.count(), 1)
        option = datasets[0]
        self.assertIsInstance(option, GeoDataset)
        self.assertEqual(option, self.gds)

    def test_remaining_geodataset_options(self):
        options = self.scenario.remaining_geodataset_options(feedstock=self.material)
        self.assertIsInstance(options, QuerySet)
        self.assertEqual(options.count(), 0)

    def test_available_inventory_algorithms(self):
        algos = self.scenario.available_inventory_algorithms(feedstock=self.material, geodataset=self.gds)
        self.assertIsInstance(algos, QuerySet)
        self.assertEqual(algos.count(), 1)
        algo = algos[0]
        self.assertIsInstance(algo, InventoryAlgorithm)
        self.assertEqual(algo, self.alg)

    def test_evaluated_inventory_algorithms(self):
        algos = self.scenario.evaluated_inventory_algorithms()
        self.assertIsInstance(algos, QuerySet)
        self.assertEqual(algos.count(), 1)
        algo = algos[0]
        self.assertIsInstance(algo, InventoryAlgorithm)
        self.assertEqual(algo, self.alg)

    def test_remaining_inventory_algorithm_options(self):
        algos = self.scenario.remaining_inventory_algorithm_options(feedstock=self.material.standard_settings,
                                                                    geodataset=self.gds)
        self.assertIsInstance(algos, QuerySet)
        self.assertEqual(algos.count(), 0)

    def test_add_inventory_algorithm(self):
        algorithm = self.alg

        # run with defaults and non existing entries
        old_config_entries = ScenarioInventoryConfiguration.objects.filter(scenario=self.scenario,
                                                                           inventory_algorithm=algorithm)
        values = InventoryAlgorithmParameterValue.objects.filter(parameter__inventory_algorithm=algorithm,
                                                                 default=True)
        values.delete()
        self.scenario.add_inventory_algorithm(algorithm)
        config_entries = ScenarioInventoryConfiguration.objects.filter(scenario=self.scenario,
                                                                       inventory_algorithm=algorithm)
        self.assertQuerysetEqual(old_config_entries, config_entries)

        # run when overwriting existing entry
        # new_values = [v for v in InventoryAlgorithmParameterValue.objects.filter(name='Educated guess')]
        parameter = InventoryAlgorithmParameter.objects.filter(inventory_algorithm=algorithm)[0]
        new_value = InventoryAlgorithmParameterValue.objects.create(name='test', parameter=parameter, value=10)
        self.scenario.add_inventory_algorithm(algorithm, [new_value, ])
        config_entries = ScenarioInventoryConfiguration.objects.filter(scenario=self.scenario,
                                                                       inventory_algorithm=algorithm)
        self.assertEqual(config_entries.count(), 1)
        value = config_entries[0].inventory_value
        self.assertEqual(new_value, value)

        # run with wrong custom values

        def wrong_parameter():
            parameter = InventoryAlgorithmParameter.objects.get(short_name='area_yield')
            value = InventoryAlgorithmParameterValue.objects.create(name='test', parameter=parameter, value=10)
            self.scenario.add_inventory_algorithm(algorithm, [value, ])

        self.assertRaises(WrongParameterForInventoryAlgorithm, wrong_parameter)

    # def test_create_default_configuration(self):
    #     self.scenario.create_default_configuration()  # TODO: Where can this be automated?
    #     config = ScenarioInventoryConfiguration.objects.filter(scenario=self.scenario)
    #     self.assertIsNotNone(config)
    #     self.assertEqual(len(config), 2)
    #     for entry in config:
    #         self.assertTrue(entry.inventory_value.default)
    #         self.assertIn(entry.inventory_parameter.short_name, ['point_yield', 'area_yield', ])


from unittest import TestCase as NativeTestCase

from django.db.models.query import QuerySet
from django.test import TestCase as DjangoTestCase, tag
from django_mock_queries.query import MockSet, MockModel
from mock import Mock, patch, PropertyMock, MagicMock

from distributions.plots import DataSet
from brit.exceptions import UnitMismatchError
from materials.models import Material, BaseObjects
from inventories.models import Scenario, InventoryAlgorithm, InventoryAlgorithmParameter, \
    InventoryAlgorithmParameterValue, ScenarioInventoryConfiguration
from maps.models import GeoDataset, Region, Catchment

from inventories.evaluations import ScenarioResult
from users.models import ReferenceUsers


class ScenarioResultTestCase(NativeTestCase):

    def setUp(self):
        self.scenario = MockModel(name='Test scenario', layer_set=MockSet())
        self.scenario.feedstocks = MagicMock(return_value=MockSet())

    def test_init_scenario(self):
        result = ScenarioResult(self.scenario)
        self.assertEqual(result.scenario.name, 'Test scenario')

    def test_init_layers(self):
        layer = MockModel(name='layer1', feedstock=MockModel())
        self.scenario.layer_set = MockSet(layer)
        result = ScenarioResult(self.scenario)
        self.assertEqual(result.layers.first(), layer)

    def test_init_feedstocks(self):
        feedstock = MockModel(id=5)
        scenario = MockModel(layer_set=MockSet())
        scenario.feedstocks = MagicMock(return_value=MockSet(feedstock))
        result = ScenarioResult(scenario)
        self.assertEqual(result.feedstocks.first(), feedstock)

    @patch('scenario_evaluator.evaluations.ScenarioResult.layers', new_callable=PropertyMock)
    def test_property_layers(self, mock_layers):
        result = ScenarioResult(Mock())
        layer = MockModel(name='test layer')
        layers = MockSet(layer)
        mock_layers.return_value = layers
        self.assertEqual(result.layers.first(), layer)

    def test_total_production(self):
        value1 = 100.4
        value2 = 87.3
        unit = 'kg/a'
        layers = MockSet(
            MockModel(
                feedstock=MockModel(),
                layeraggregatedvalue_set=MockSet(MockModel(name='Total production', value=value1, unit=unit))),
            MockModel(
                feedstock=MockModel(),
                layeraggregatedvalue_set=MockSet(
                    MockModel(name='Total production', value=value2, unit=unit),
                    MockModel(name='Imposter', value=value2, unit=unit)
                )
            )
        )
        self.scenario.layer_set = layers
        result = ScenarioResult(self.scenario)
        production = result.total_production()
        self.assertIsInstance(production, DataSet)
        self.assertEqual(production.label, 'Total production')
        self.assertEqual(production.unit, unit)
        self.assertEqual(len(production.data), 1)
        self.assertEqual(production.data['Total'], value1 + value2)

    def test_total_production_with_different_unit(self):
        value = 100
        unit = 'Mg/a'
        layers = MockSet(
            MockModel(
                feedstock=MockModel(),
                layeraggregatedvalue_set=MockSet(MockModel(name='Total production', value=value, unit=unit)))
        )
        self.scenario.layer_set = layers
        result = ScenarioResult(self.scenario)
        production = result.total_production()
        self.assertEqual(production.unit, unit)

    def test_total_production_raises_error_on_unit_mismatch(self):
        layers = MockSet(
            MockModel(
                feedstock=MockModel(),
                layeraggregatedvalue_set=MockSet(MockModel(name='Total production', value=1, unit='kg/a'))),
            MockModel(
                feedstock=MockModel(),
                layeraggregatedvalue_set=MockSet(MockModel(name='Total production', value=1, unit='Imposter')))
        )
        self.scenario.layer_set = layers
        result = ScenarioResult(self.scenario)
        with self.assertRaises(UnitMismatchError):
            result.total_production()

    def test_total_production_per_feedstock(self):
        unit = 'Mg/a'
        value1 = 10
        value2 = 20
        value3 = 13
        name = 'Total production'
        layers = MockSet(
            MockModel(
                feedstock=MockModel(name="Feedstock 1"),
                layeraggregatedvalue_set=MockSet(MockModel(name=name, value=value1, unit=unit))
            ),
            MockModel(
                feedstock=MockModel(name="Feedstock 2"),
                layeraggregatedvalue_set=MockSet(MockModel(name=name, value=value2, unit=unit))
            ),
            MockModel(
                feedstock=MockModel(name="Feedstock 3"),
                layeraggregatedvalue_set=MockSet(MockModel(name=name, value=value3, unit=unit))),
        )
        self.scenario.layer_set = layers
        result = ScenarioResult(self.scenario)
        production = result.total_production_per_feedstock()
        self.assertIsInstance(production, DataSet)
        self.assertEqual(production.unit, unit)
        self.assertDictEqual(production.data,
                             {
                                 'Feedstock 1': value1,
                                 'Feedstock 2': value2,
                                 'Feedstock 3': value3
                             })
        self.assertEqual(production.label, 'Total production per feedstock')

    def test_total_production_per_feedstock_with_two_layers_and_other_unit(self):
        unit = 'kg/a'
        value1 = 5000
        value2 = 1700
        name = 'Total production'
        layers = MockSet(
            MockModel(
                feedstock=MockModel(name="Feedstock 1"),
                layeraggregatedvalue_set=MockSet(MockModel(name=name, value=value1, unit=unit))
            ),
            MockModel(
                feedstock=MockModel(name="Feedstock 2"),
                layeraggregatedvalue_set=MockSet(MockModel(name=name, value=value2, unit=unit))
            ),
        )
        self.scenario.layer_set = layers
        result = ScenarioResult(self.scenario)
        production = result.total_production_per_feedstock()
        self.assertIsInstance(production, DataSet)
        self.assertEqual(production.unit, unit)
        self.assertDictEqual(production.data, {
            'Feedstock 1': value1,
            'Feedstock 2': value2,
        })
        self.assertEqual(production.label, 'Total production per feedstock')

    def test_total_production_per_feedstock_with_multiple_aggregated_values(self):
        unit = 'Mg/a'
        value1 = 100
        name = 'Total production'
        layers = MockSet(
            MockModel(
                feedstock=MockModel(name="Feedstock 1"),
                layeraggregatedvalue_set=MockSet(
                    MockModel(name=name, value=value1, unit=unit),
                    MockModel(name='Imposter', value=value1, unit=unit)
                )),
        )
        self.scenario.layer_set = layers
        result = ScenarioResult(self.scenario)
        production = result.total_production_per_feedstock()
        self.assertIsInstance(production, DataSet)
        self.assertEqual(production.unit, unit)
        self.assertDictEqual(production.data, {'Feedstock 1': value1})
        self.assertEqual(production.label, 'Total production per feedstock')

    def test_total_production_per_feedstock_with_two_feedstocks(self):
        value1 = 111
        value2 = 222
        layers = MockSet(
            MockModel(
                feedstock=MockModel(name='Feedstock 1'),
                layeraggregatedvalue_set=MockSet(MockModel(name='Total production', value=value1))
            ),
            MockModel(
                feedstock=MockModel(name='Feedstock 2'),
                layeraggregatedvalue_set=MockSet(MockModel(name='Total production', value=value2))
            ),
        )
        self.scenario.layer_set = layers
        result = ScenarioResult(self.scenario)
        production = result.total_production_per_feedstock()
        self.assertEqual(len(production.data), 2)
        self.assertDictEqual(production.data, {'Feedstock 1': value1, 'Feedstock 2': value2})

    # TODO: delete when ready
    # def test_total_production_per_material_component(self):
    #     feedstock1 = GeoreferencedRegion(component_groups=MockSet(GeoreferencedRegion(name='Group 1')))
    #     composition = {
    #         GeoreferencedRegion(name='Group 1'): 1
    #     }
    #     feedstock1.composition = MagicMock(return_value=composition)
    #     self.scenario.feedstocks = MockSet(feedstock1)
    #     result = ScenarioResult(self.scenario)
    #     datasets = result.total_production_per_material_component()
    #     self.assertIsInstance(datasets, dict)
    #     self.assertListEqual(list(datasets.keys()), ['Group 1'])


@tag('db')
class ScenarioResultTestCaseDB(DjangoTestCase):
    fixtures = ['user.json', 'regions.json', 'catchments.json']

    def setUp(self):
        self.user = ReferenceUsers.objects.get.standard_owner
        self.material = Material.objects.create(
            name='First test material',
            owner=self.user,
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
