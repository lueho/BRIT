from django.test import TestCase

from .models import *


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
