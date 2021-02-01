from django.test import RequestFactory, tag, TestCase

from .models import (Catchment,
                     GeoDataset,
                     InventoryAlgorithm,
                     InventoryAlgorithmParameter,
                     InventoryAlgorithmParameterValue,
                     Material,
                     MaterialComponentGroup,
                     MaterialComponentShare,
                     Region,
                     Scenario,
                     ScenarioInventoryConfiguration,
                     WrongParameterForInventoryAlgorithm)
from .views import MaterialAddComponentGroupView


# ----------- Materials ------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

@tag('material', 'model')
class MaterialTestCase(TestCase):
    fixtures = ['material_fixtures.json']

    def setUp(self):
        pass

    def test_create(self):
        feedstock = Material.objects.get(is_feedstock=True)
        self.assertEqual(feedstock.name, 'Test Feedstock')

        # Feedstock filter
        # self.assertQuerysetEqual(Material.objects.feedstocks(), Material.objects.filter(is_feedstock=True)) # TODO

        pass

    def test_grouped_component_shares(self):
        scenario = Scenario.objects.get(id=1)
        material = Material.objects.get(id=1)
        group = MaterialComponentGroup.objects.get(id=1)
        share = MaterialComponentShare.objects.get(id=1)
        grouped_shares = {
            group: {
                'dynamic': False,
                'shares': [
                    share
                ]
            }
        }
        self.assertDictEqual(grouped_shares, material.grouped_component_shares(scenario=scenario))


@tag('view', 'material')
class MaterialAddComponentGroupViewTestCase(TestCase):
    fixtures = ['material_fixtures']

    def test_environment_set_in_context(self):
        request = RequestFactory().get('/')
        view = MaterialAddComponentGroupView()
        view.setup(request)

        context = view.get_context_data()
        self.assertIn('form', context)


class RegionTestCase(TestCase):
    fixtures = ['regions.json', 'catchments.json', 'scenarios.json']

    def setUp(self):
        pass

    def test_create(self):
        region = Region.objects.get(name='Hamburg')
        self.assertEqual(region.name, 'Hamburg')


class CatchmentTestCase(TestCase):
    fixtures = ['regions.json', 'catchments.json', 'scenarios.json']

    def test_create(self):
        catchment = Catchment.objects.get(name='Wandsbek')
        self.assertEqual(catchment.name, 'Wandsbek')


class GeoDatasetTestCase(TestCase):
    fixtures = ['regions.json', 'catchments.json', 'scenarios.json']

    def test_create(self):
        ds = GeoDataset.objects.get(id=1)
        self.assertEqual(ds.name, 'Hamburg Roadsidetrees')


class InventoryAlgorithmTestCase(TestCase):
    fixtures = ['regions.json', 'catchments.json', 'scenarios.json']

    def test_create(self):
        alg = InventoryAlgorithm.objects.get(id=1)
        self.assertEqual(alg.name, 'Average point yield')


class InventoryAlgorithmParameterTestCase(TestCase):
    fixtures = ['regions.json', 'catchments.json', 'scenarios.json']

    def test_create(self):
        param = InventoryAlgorithmParameter.objects.get(id=1)
        self.assertEqual(param.short_name, 'point_yield')


class InventoryAlgorithmParameterValueTestCase(TestCase):
    fixtures = ['regions.json', 'catchments.json', 'scenarios.json']

    def test_create(self):
        param_value = InventoryAlgorithmParameterValue.objects.get(id=1)
        self.assertEqual(param_value.value, 10.5)
        self.assertEqual(param_value.standard_deviation, 0.5)


class ScenarioTestCase(TestCase):
    fixtures = ['regions.json', 'catchments.json', 'scenarios.json']

    def test_add_inventory_algorithm(self):
        scenario = Scenario.objects.get(name='Hamburg standard')
        algorithm = InventoryAlgorithm.objects.get(name='Average point yield')

        # run with defaults and non existing entries
        old_config_entries = ScenarioInventoryConfiguration.objects.filter(scenario=scenario,
                                                                           inventory_algorithm=algorithm)
        values = InventoryAlgorithmParameterValue.objects.filter(parameter__inventory_algorithm=algorithm,
                                                                 default=True)
        values.delete()
        scenario.add_inventory_algorithm(algorithm)
        config_entries = ScenarioInventoryConfiguration.objects.filter(scenario=scenario,
                                                                       inventory_algorithm=algorithm)
        self.assertQuerysetEqual(old_config_entries, config_entries)

        # run when overwriting existing entry
        # new_values = [v for v in InventoryAlgorithmParameterValue.objects.filter(name='Educated guess')]
        parameter = InventoryAlgorithmParameter.objects.filter(inventory_algorithm=algorithm)[0]
        new_value = InventoryAlgorithmParameterValue.objects.create(name='test', parameter=parameter, value=10)
        scenario.add_inventory_algorithm(algorithm, [new_value, ])
        config_entries = ScenarioInventoryConfiguration.objects.filter(scenario=scenario,
                                                                       inventory_algorithm=algorithm)
        self.assertEqual(config_entries.count(), 1)
        value = config_entries[0].inventory_value
        self.assertEqual(new_value, value)

        # run with wrong custom values

        def wrong_parameter():
            parameter = InventoryAlgorithmParameter.objects.get(short_name='area_yield')
            value = InventoryAlgorithmParameterValue.objects.create(name='test', parameter=parameter, value=10)
            scenario.add_inventory_algorithm(algorithm, [value, ])

        self.assertRaises(WrongParameterForInventoryAlgorithm, wrong_parameter)

    def test_create(self):
        params = {
            'name': 'test scenario',
            'region': Region.objects.get(name='Hamburg'),
            'catchment': Catchment.objects.get(name='Harburg')

        }
        scenario = Scenario.objects.create(**params)
        self.assertIsInstance(scenario, Scenario)

    def test_create_default_configuration(self):
        scenario = Scenario.objects.get(name='Hamburg standard')
        scenario.create_default_configuration()  # TODO: Where can this be automated?
        config = ScenarioInventoryConfiguration.objects.filter(scenario=scenario)
        self.assertIsNotNone(config)
        self.assertEqual(len(config), 2)
        for entry in config:
            self.assertTrue(entry.inventory_value.default)
            self.assertIn(entry.inventory_parameter.short_name, ['point_yield', 'area_yield', ])
