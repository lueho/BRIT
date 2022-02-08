import importlib

from django.test import TestCase

from case_studies.flexibi_nantes.models import Greenhouse, NantesGreenhouses
from distributions.models import TemporalDistribution
from inventories.models import Scenario


class InventoryAlgorithmsTestCase(TestCase):
    fixtures = ['user.json', 'regions.json', 'catchments.json', 'greenhouses.json', 'greenhouse_types.json']

    def setUp(self):
        pass

    def test_filtering(self):
        count = 0
        considered_greenhouses = NantesGreenhouses.objects.none()
        for greenhouse in Greenhouse.objects.all():
            greenhouse_group = NantesGreenhouses.objects.filter(**greenhouse.filter_kwargs)
            count += greenhouse_group.count()
            considered_greenhouses = considered_greenhouses.union(greenhouse_group)
        self.assertQuerysetEqual(NantesGreenhouses.objects.all(), considered_greenhouses, ordered=False)
        self.assertEqual(count, NantesGreenhouses.objects.count())

    def test_nantes_greenhouse_production(self):

        scenario = Scenario.objects.first()

        source_module = 'case_studies.flexibi_nantes.algorithms'
        function_name = 'nantes_greenhouse_production'
        module = importlib.import_module(source_module)
        inventory_function = getattr(module.InventoryAlgorithms, function_name)
        kwargs = {
            'scenario_id': scenario.id
        }
        results = inventory_function(**kwargs)
        features = results.pop('features')
        self.assertEqual(len(features), 121)
        aggregated_values = results.pop('aggregated_values')
        for av in aggregated_values:
            if av['name'] == 'feedstocks':
                feedstocks = av
            if av['name'] == 'total_surface':
                total_surface = av
            if av['name'] == 'components':
                components = av
        self.assertListEqual(['Tomato Greenhouse Residue'], feedstocks['value'])
        self.assertEqual(total_surface['unit'], 'ha')
        self.assertAlmostEqual(total_surface['value'], 156.5, places=1)
        self.assertEqual({'Stems', 'Leaves'}, components['value'])
        aggregated_distributions = results.pop('aggregated_distributions')
        aggdist = aggregated_distributions[0]
        temporal_distribution = TemporalDistribution.objects.get(name='Months of the year')
        self.assertEqual(aggdist['name'], 'Macro Components')
        self.assertEqual(aggdist['distribution'], temporal_distribution.id)
        self.assertEqual(len(aggdist['sets']), temporal_distribution.timestep_set.count())
        self.assertDictEqual({}, results)


# class GrowthShareTestCase(TestCase):
#
#     def setUp(self):
#         self.owner = ReferenceUsers.objects.get.standard_owner
#         self.component = BaseObjects.objects.get.base_component
#
#     def test_create(self):
#         share = GrowthShare.objects.create(
#             owner=self.owner,
#             component=self.component,
#             average=1.1,
#             standard_deviation=0.1
#         )
#         self.assertIsInstance(share, GrowthShare)
#         self.assertEqual(GrowthShare.objects.all().count(), 1)
#
#
# class GreenhouseGrowthCycleTestCase(TestCase):
#
#     def setUp(self):
#         self.owner = ReferenceUsers.objects.get.standard_owner
#         self.component = BaseObjects.objects.get.base_component
#         self.share = GrowthShare.objects.create(
#             owner=self.owner,
#             component=self.component,
#             average=1.1,
#             standard_deviation=0.1
#         )
#         self.residue = Material.objects.create(
#             owner=self.owner,
#             name='Residue Material'
#         )
#         self.residue_settings = self.residue.standard_settings
#         self.culture1 = Culture.objects.create(
#             owner=self.owner,
#             name='culture1',
#             residue=self.residue_settings
#         )
#         self.greenhouse1 = Greenhouse.objects.create(
#             owner=self.owner,
#             name='Type 1',
#             heated=True,
#             lighted=False,
#             high_wire=True,
#             above_ground=True
#         )
#         self.cycle1 = GreenhouseGrowthCycle.objects.create(
#             owner=self.owner,
#             cycle_number=1,
#             culture=self.culture1,
#             greenhouse=self.greenhouse1,
#         )
#         self.component = BaseObjects.objects.get.base_component
#         self.share1 = GrowthShare.objects.create(
#             owner=self.owner,
#             component=self.component,
#             average=1.1,
#             standard_deviation=0.1
#         )
#
#
# class GreenhouseTestCase(TestCase):
#
#     def setUp(self):
#         self.owner = ReferenceUsers.objects.get.standard_owner
#         self.greenhouse1 = Greenhouse.objects.create(
#             owner=self.owner,
#             name='Type 1',
#             heated=True,
#             lighted=False,
#             high_wire=True,
#             above_ground=True
#         )
#         self.residue = Material.objects.create(
#             owner=self.owner,
#             name='Residue Material'
#         )
#         self.residue_settings = self.residue.standard_settings
#         self.culture1 = Culture.objects.create(
#             owner=self.owner,
#             name='culture1',
#             residue=self.residue_settings
#         )
#
#     def test_create(self):
#         self.assertIsInstance(self.greenhouse1, Greenhouse)
#
#     def test_cultures(self):
#         cycle1 = GreenhouseGrowthCycle.objects.create(
#             owner=self.owner,
#             cycle_number=1,
#             culture=self.culture1,
#             greenhouse=self.greenhouse1,
#         )
#         self.assertEqual(cycle1, self.greenhouse1.growth_cycles.first())
#         expected_cultures = {
#             'culture_1': self.culture1.name,
#             'culture_2': None,
#             'culture_3': None
#         }
#         self.assertDictEqual(self.greenhouse1.cultures(), expected_cultures)
#
#     def test_types(self):
#         cycle1 = GreenhouseGrowthCycle.objects.create(
#             owner=self.owner,
#             cycle_number=1,
#             culture=self.culture1,
#             greenhouse=self.greenhouse1,
#         )
#         types = Greenhouse.objects.types()
#         self.assertEqual(cycle1, self.greenhouse1.growth_cycles.first())
#         expected_types = [{
#             'heated': True,
#             'lighted': False,
#             'high_wire': True,
#             'above_ground': True
#         }]
#         cycle = self.greenhouse1.growth_cycles.first()
#         expected_types[0].update({'culture_1': cycle.culture.name, 'culture_2': None, 'culture_3': None})
#         self.assertDictEqual(expected_types[0], types[0])
