from django.contrib.gis.geos import GEOSGeometry, Point
from django.db.models import QuerySet
from django.test import TestCase

from maps.models import GeoPolygon, Location
from ..models import Catchment, LauRegion, NutsRegion, Region


class TestLocationModel(TestCase):

    def setUp(self):
        self.location = Location.objects.create(
            name="Test Location",
            geom=Point(5, 23),
            address="123 Test St."
        )

    def tearDown(self):
        self.location.delete()

    def test_location_created(self):
        self.assertIsInstance(self.location, Location)

    def test_location_name(self):
        self.assertEqual(self.location.name, "Test Location")

    def test_location_geom(self):
        self.assertEqual((self.location.geom.x, self.location.geom.y), (5, 23))

    def test_location_address(self):
        self.assertEqual(self.location.address, "123 Test St.")

    def test_location_str(self):
        self.assertEqual(str(self.location), "Test Location at 123 Test St.")

    def test_location_without_address_str(self):
        self.location.address = None
        self.location.save()
        self.assertEqual(str(self.location), "Test Location")


class RegionTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        country_wkt = "MULTIPOLYGON(((0 0, 0 1, 1 1, 1 0, 0 0)))"
        cls.country_borders = GeoPolygon.objects.create(
            geom=GEOSGeometry(country_wkt, srid=4326)
        )
        cls.country_region = NutsRegion.objects.create(
            name="Country",
            levl_code=0,
            cntr_code="DE",
            borders=cls.country_borders
        )

        # Create a catchment polygon that is almost entirely within the country.
        # Its coordinates are chosen so that without the buffer it might not be strictly contained,
        # but with the buffer (0.001°) the geometry becomes fully contained.
        catchment_wkt = (
            "MULTIPOLYGON((("
            "0 0, "  # bottom left
            "0 1, "  # top left
            "1 1, "  # top right (inside)
            "1.004 0.5, "  # tiny bump to the right (outside)
            "1 0, "  # bottom right (inside)
            "0 0"  # close the ring
            ")))"
        )
        cls.catchment_borders = GeoPolygon.objects.create(
            geom=GEOSGeometry(catchment_wkt, srid=4326)
        )

    def test_region_geom(self):
        self.assertEqual(self.country_borders.geom, self.country_region.geom)

    def test_country_field_automatically_set(self):
        catchment_region = Region.objects.create(name='Catchment Region', borders=self.catchment_borders)
        self.assertEqual('DE', catchment_region.country, )


class CatchmentPostDeleteTestCase(TestCase):

    def setUp(self):
        self.region = Region.objects.create(name='Test Region To Delete')
        self.fix_region = Region.objects.create(name='Test Region To Stay')
        self.catchment = Catchment.objects.create(name='Test Catchment', type='custom', region=self.region)
        self.catchment_2 = Catchment.objects.create(name='Test Catchment 2', type='administrative',
                                                    region=self.fix_region)

    def test_after_deleting_catchment_unused_custom_region_is_also_deleted(self):
        self.catchment.delete()
        with self.assertRaises(Region.DoesNotExist):
            Region.objects.get(name='Test Region To Delete')

    def test_non_custom_regions_are_exempted_from_deletion(self):
        self.catchment_2.delete()
        Region.objects.get(name='Test Region To Stay')


class CatchmentPedigreeTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        region = Region.objects.create(name='Test Region')
        cls.catchment = Catchment.objects.create(name='Test Catchment', region=region)
        cls.child_catchment_1 = Catchment.objects.create(name='Child 1', parent=cls.catchment)
        cls.child_catchment_2 = Catchment.objects.create(name='Child 2', parent=cls.catchment)
        cls.grandchild_catchment_1_1 = Catchment.objects.create(name='Grandchild 1 1', parent=cls.child_catchment_1)
        cls.grandchild_catchment_1_2 = Catchment.objects.create(name='Grandchild 1 2', parent=cls.child_catchment_1)
        cls.grandchild_catchment_2_1 = Catchment.objects.create(name='Grandchild 2 1', parent=cls.child_catchment_2)
        cls.great_grandchild_catchment_1_1_1 = Catchment.objects.create(name='Great Grandchild 1 1 1',
                                                                        parent=cls.grandchild_catchment_1_1)
        cls.great_grandchild_catchment_2_1_1 = Catchment.objects.create(name='Great Grandchild 2 1 1',
                                                                        parent=cls.grandchild_catchment_2_1)
        cls.unrelated_catchment = Catchment.objects.create(name='Unrelated Catchment', region=region)

    def test_downstream_pedigree_returns_catchment_queryset(self):
        pedigree = self.catchment.descendants(include_self=True)
        self.assertIsInstance(pedigree, QuerySet)
        self.assertEqual(pedigree.model, Catchment)

    def test_downstream_pedigree_includes_self(self):
        pedigree = self.catchment.descendants(include_self=True)
        self.assertIn(self.catchment, pedigree)

    def test_downstream_pedigree_includes_children(self):
        pedigree = self.catchment.descendants(include_self=True)
        self.assertIn(self.child_catchment_1, pedigree)
        self.assertIn(self.child_catchment_2, pedigree)

    def test_downstream_pedigree_includes_grandchildren_of_all_children(self):
        pedigree = self.catchment.descendants(include_self=True)
        self.assertIn(self.grandchild_catchment_1_1, pedigree)
        self.assertIn(self.grandchild_catchment_1_2, pedigree)
        self.assertIn(self.grandchild_catchment_2_1, pedigree)

    def test_downstream_pedigree_includes_great_grandchildren_of_all_grandchildren(self):
        pedigree = self.catchment.descendants(include_self=True)
        self.assertIn(self.great_grandchild_catchment_1_1_1, pedigree)
        self.assertIn(self.great_grandchild_catchment_2_1_1, pedigree)

    def test_downstream_pedigree_excludes_unrelated_catchment(self):
        pedigree = self.catchment.descendants(include_self=True)
        self.assertNotIn(self.unrelated_catchment, pedigree)


class NutsRegionTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        nuts0 = NutsRegion.objects.create(
            nuts_id='UK',
            levl_code=0,
            name_latn='United Kingdom'
        )
        nuts1 = NutsRegion.objects.create(
            nuts_id='UKH',
            levl_code=1,
            name_latn='East of England',
            parent=nuts0
        )
        nuts2 = NutsRegion.objects.create(
            nuts_id='UKH1',
            levl_code=2,
            name_latn='East Anglia',
            parent=nuts1
        )
        NutsRegion.objects.create(
            nuts_id='UKH2',
            levl_code=2,
            name_latn='Bedfordshire and Hertfordshire',
            parent=nuts1
        )
        NutsRegion.objects.create(
            nuts_id='UKH11',
            levl_code=3,
            name_latn='Peterborough',
            parent=nuts2
        )
        nuts3 = NutsRegion.objects.create(
            nuts_id='UKH14',
            levl_code=3,
            name_latn='Suffolk',
            parent=nuts2
        )
        LauRegion.objects.create(
            lau_id='E07000200',
            lau_name='Babergh',
            nuts_parent=nuts3
        )
        LauRegion.objects.create(
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
