from django.test import TestCase

from .models import (Catchment,
                     GeoDataset,
                     InventoryAlgorithm,
                     InventoryAlgorithmParameter,
                     InventoryAlgorithmParameterValue,
                     Material,
                     Region,
                     Scenario,
                     ScenarioInventoryConfiguration, )


class MaterialTestCase(TestCase):
    fixtures = ['regions.json', 'scenarios.json', 'catchments.json']

    def setUp(self):
        pass

    def test_create(self):
        material = Material.objects.get(name='Tree prunings (winter)')
        self.assertEqual(material.name, 'Tree prunings (winter)')


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

    def setUp(self):
        scenario = Scenario(
            name='Test scenario',
            region=Region.objects.get(name='Hamburg'),
            catchment=Catchment.objects.get(name='Wandsbek'),
            use_default_configuration=True
        )
        scenario.save()
        scenario.feedstocks.add(Material.objects.get(name='Tree prunings (winter)'))

    def test_create(self):
        scenario = Scenario.objects.get(name='Test scenario')
        self.assertIsInstance(scenario, Scenario)
        feedstocks = scenario.feedstocks.all()
        self.assertEqual(len(feedstocks), 1)
        self.assertEqual(feedstocks[0].name, 'Tree prunings (winter)')
        algorithms = InventoryAlgorithm.objects.filter(feedstock=feedstocks[0],
                                                       geodataset__region=scenario.region,
                                                       default=True)
        self.assertEqual(len(algorithms), 2)
        self.assertEqual(algorithms[0].function_name, 'avg_point_yield')
        parameters = InventoryAlgorithmParameter.objects.filter(inventory_algorithm=algorithms[0])
        self.assertEqual(len(parameters), 1)
        self.assertTrue(scenario.use_default_configuration)

    def test_create_default_configuration(self):
        scenario = Scenario.objects.get(name='Test scenario')
        scenario.create_default_configuration()  # TODO: Where can this be automated?
        config = ScenarioInventoryConfiguration.objects.filter(scenario=scenario)
        self.assertIsNotNone(config)
        self.assertEqual(len(config), 2)
        for entry in config:
            self.assertTrue(entry.inventory_value.default)
            self.assertIn(entry.inventory_parameter.short_name, ['point_yield', 'area_yield', ])
