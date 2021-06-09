from django.contrib.auth.models import User
from django.db.models.query import QuerySet
from django.test import TestCase

from flexibi_dst.models import TemporalDistribution, Timestep
from material_manager.models import Material, MaterialComponent, MaterialComponentGroup, MaterialSettings
from users.models import ReferenceUsers
from .models import (Catchment,
                     InventoryAlgorithm,
                     InventoryAlgorithmParameter,
                     InventoryAlgorithmParameterValue,
                     GeoDataset,
                     Region,
                     Scenario,
                     ScenarioInventoryConfiguration,
                     WrongParameterForInventoryAlgorithm)


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
            is_feedstock=True
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
            is_feedstock=True
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
        algos = self.scenario.remaining_inventory_algorithm_options(feedstock=self.material.standard_settings, geodataset=self.gds)
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