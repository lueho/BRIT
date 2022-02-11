from django.contrib.auth.models import User
from django.db.models import QuerySet
from django.test import TestCase

from ..models import LauRegion, NutsRegion


class NutsRegionTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = User.objects.create(username='owner', password='very-secure!')
        nuts0 = NutsRegion.objects.create(
            owner=owner,
            nuts_id='UK',
            levl_code=0,
            name_latn='United Kingdom'
        )
        nuts1 = NutsRegion.objects.create(
            owner=owner,
            nuts_id='UKH',
            levl_code=1,
            name_latn='East of England',
            parent=nuts0
        )
        nuts2 = NutsRegion.objects.create(
            owner=owner,
            nuts_id='UKH1',
            levl_code=2,
            name_latn='East Anglia',
            parent=nuts1
        )
        NutsRegion.objects.create(
            owner=owner,
            nuts_id='UKH2',
            levl_code=2,
            name_latn='Bedfordshire and Hertfordshire',
            parent=nuts1
        )
        NutsRegion.objects.create(
            owner=owner,
            nuts_id='UKH11',
            levl_code=3,
            name_latn='Peterborough',
            parent=nuts2
        )
        nuts3 = NutsRegion.objects.create(
            owner=owner,
            nuts_id='UKH14',
            levl_code=3,
            name_latn='Suffolk',
            parent=nuts2
        )
        LauRegion.objects.create(
            owner=owner,
            lau_id='E07000200',
            lau_name='Babergh',
            nuts_parent=nuts3
        )
        LauRegion.objects.create(
            owner=owner,
            lau_id='E07000202',
            lau_name='Ipswich',
            nuts_parent=nuts3
        )

    def setUp(self):
        pass

    def test_pedigree_starting_from_lvl_0(self):
        region = NutsRegion.objects.get(levl_code=0)
        expected = {
            'qs_0': NutsRegion.objects.filter(levl_code=0),
            'qs_1': NutsRegion.objects.filter(levl_code=1),
            'qs_2': NutsRegion.objects.filter(levl_code=2),
            'qs_3': NutsRegion.objects.filter(levl_code=3),
        }
        pedigree = region.pedigree
        self.assertEqual(set(pedigree.keys()), set(expected.keys()))
        for key, value in pedigree.items():
            self.assertIsInstance(value, QuerySet)
            self.assertEqual(set(pedigree[key]), set(expected[key]))

    def test_pedigree_starting_from_lvl_1(self):
        region = NutsRegion.objects.get(levl_code=1)
        expected = {
            'qs_0': NutsRegion.objects.filter(levl_code=0),
            'qs_1': NutsRegion.objects.filter(levl_code=1),
            'qs_2': NutsRegion.objects.filter(levl_code=2),
            'qs_3': NutsRegion.objects.filter(levl_code=3),
        }
        pedigree = region.pedigree
        self.assertEqual(set(pedigree.keys()), set(expected.keys()))
        for key, value in pedigree.items():
            self.assertIsInstance(value, QuerySet)
            self.assertEqual(set(pedigree[key]), set(expected[key]))

    def test_pedigree_starting_from_lvl_2(self):
        region = NutsRegion.objects.get(nuts_id='UKH1')
        expected = {
            'qs_0': NutsRegion.objects.filter(nuts_id='UK'),
            'qs_1': NutsRegion.objects.filter(nuts_id='UKH'),
            'qs_2': NutsRegion.objects.filter(nuts_id='UKH1'),
            'qs_3': NutsRegion.objects.filter(levl_code=3),
        }
        pedigree = region.pedigree
        self.assertEqual(set(pedigree.keys()), set(expected.keys()))
        for key, value in pedigree.items():
            self.assertIsInstance(value, QuerySet)
            self.assertEqual(set(pedigree[key]), set(expected[key]))

    def test_pedigree_starting_from_lvl_3(self):
        region = NutsRegion.objects.get(nuts_id='UKH14')
        expected = {
            'qs_0': NutsRegion.objects.filter(nuts_id='UK'),
            'qs_1': NutsRegion.objects.filter(nuts_id='UKH'),
            'qs_2': NutsRegion.objects.filter(nuts_id='UKH1'),
            'qs_3': NutsRegion.objects.filter(nuts_id='UKH14'),
            'qs_4': LauRegion.objects.all()
        }
        pedigree = region.pedigree
        self.assertEqual(set(pedigree.keys()), set(expected.keys()))
        for key, value in pedigree.items():
            self.assertIsInstance(value, QuerySet)
            self.assertEqual(set(pedigree[key]), set(expected[key]))
