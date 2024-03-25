from django.contrib.gis.geos import Point
from django.urls import reverse

from maps.models import Catchment, GeoDataset, GeoPolygon, Region
from utils.tests.testcases import ViewSetWithPermissionsTestCase, ViewWithPermissionsTestCase
from ..models import HamburgRoadsideTrees


class HamburgRoadsideTreesMapViewTestCase(ViewSetWithPermissionsTestCase):
    member_permissions = ['view_geodataset']

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.dataset = GeoDataset.objects.create(
            name='Hamburg Roadside Trees',
            description='Roadside trees in Hamburg',
            model_name='HamburgRoadsideTrees',
            region=Region.objects.create(name='Hamburg', country='Germany')
        )
        cls.tree = HamburgRoadsideTrees.objects.create(
            geom=Point(0, 0, srid=4326)
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('HamburgRoadsideTrees'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('HamburgRoadsideTrees'))
        self.assertEqual(response.status_code, 200)

    def test_get_object(self):
        response = self.client.get(reverse('HamburgRoadsideTrees'))
        self.assertEqual(response.context['object'], self.dataset)


class HamburgRoadSideTreeAPITestCase(ViewSetWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        HamburgRoadsideTrees.objects.create(
            geom=Point(0, 0, srid=4326)
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('data.hamburg_roadside_trees'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('data.hamburg_roadside_trees'))
        self.assertEqual(response.status_code, 200)

    def test_no_query_params_return_all_entries(self):
        response = self.client.get(reverse('data.hamburg_roadside_trees'))
        json = response.json()
        self.assertIn('geoJson', json)
        self.assertIn('features', json['geoJson'])
        self.assertIn('summaries', json)
        self.assertIn('tree_count', json['summaries'][0])
        self.assertEqual(1, len(json['geoJson']['features']))
        self.assertEqual(1, json['summaries'][0]['tree_count']['value'])


class HamburgRoadsideTreeCatchmentAutocompleteViewTests(ViewWithPermissionsTestCase):
    member_permissions = ['view_geodataset']

    @classmethod
    def setUpTestData(cls):
        # Create a GeoDataset and GeoPolygon for the borders
        borders = GeoPolygon.objects.create(geom='MULTIPOLYGON(((0 0, 0 100, 100 100, 100 0, 0 0)))')
        region = Region.objects.create(name='Hamburg', country='DE', borders=borders)
        cls.hamburg_catchment = Catchment.objects.create(name='Hamburg', region=region)
        cls.dataset = GeoDataset.objects.create(
            name='Hamburg Roadside Trees',
            description='Roadside trees in Hamburg',
            model_name='HamburgRoadsideTrees',
            region=region
        )

        # Create a region within dataset borders
        inside = GeoPolygon.objects.create(geom='MULTIPOLYGON(((10 10, 10 90, 90 90, 90 10, 10 10)))')
        inside_region = Region.objects.create(name='Inside', country='DE', borders=inside)
        cls.inside_catchment_1 = Catchment.objects.create(name='Inside 1', region=inside_region)

        # Create a second region within dataset borders
        inside_2 = GeoPolygon.objects.create(geom='MULTIPOLYGON(((20 20, 20 80, 80 80, 80 20, 20 20)))')
        inside_region_2 = Region.objects.create(name='Inside 2', country='DE', borders=inside_2)
        cls.inside_catchment_2 = Catchment.objects.create(name='Inside 2', region=inside_region_2)

        # Create a region completely outside dataset borders
        outside = GeoPolygon.objects.create(geom='MULTIPOLYGON(((200 200, 200 300, 300 300, 300 200, 200 200)))')
        outside_region = Region.objects.create(name='Outside', country='DE', borders=outside)
        cls.outside_catchment = Catchment.objects.create(name='Outside', region=outside_region)

        # Create a region partially outside dataset borders
        partial = GeoPolygon.objects.create(geom='MULTIPOLYGON(((50 50, 50 150, 150 150, 150 50, 50 50)))')
        partial_region = Region.objects.create(name='Partial', country='DE', borders=partial)
        cls.partial_catchment = Catchment.objects.create(name='Partial', region=partial_region)

    def test_only_inside_catchments_in_initial_queryset(self):
        response = self.client.get(reverse('hamburgroadsidetrees-catchment-autocomplete'))
        self.assertEqual(
            [
                {'id': f'{self.hamburg_catchment.id}', 'selected_text': 'Hamburg', 'text': 'Hamburg'},
                {'id': f'{self.inside_catchment_1.id}', 'selected_text': 'Inside 1', 'text': 'Inside 1'},
                {'id': f'{self.inside_catchment_2.id}', 'selected_text': 'Inside 2', 'text': 'Inside 2'}
            ],
            list(response.json()['results'])
        )
