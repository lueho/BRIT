import json
from unittest.mock import patch

from django.conf import settings
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.utils.http import urlencode

from maps.views import CatchmentCreateByMergeView
from utils.tests.testcases import ViewWithPermissionsTestCase, ViewSetWithPermissionsTestCase
from ..models import (Attribute, RegionAttributeValue, Catchment, LauRegion, NutsRegion, Region, GeoDataset, GeoPolygon,
    Location)
from ..views import MapMixin


class DummyBaseView:
    def get_context_data(self):
        return {}


class DummyMapView(MapMixin, DummyBaseView):
    pass


class MapMixinTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.view = DummyMapView()

    def test_get_map_title(self):
        self.view.map_title = "Test Title"
        self.assertEqual(self.view.get_map_title(), "Test Title")

    def test_get_load_region(self):
        request = self.factory.get('/?load_region=true')
        self.view.request = request
        self.assertTrue(self.view.get_load_region())

        request = self.factory.get('/?load_region=false')
        self.view.request = request
        self.assertFalse(self.view.get_load_region())

        request = self.factory.get('/')
        self.view.request = request
        self.view.load_region = False
        self.assertFalse(self.view.get_load_region())

    def test_get_load_catchment(self):
        request = self.factory.get('/?load_catchment=true')
        self.view.request = request
        self.assertTrue(self.view.get_load_catchment())

        request = self.factory.get('/?load_catchment=false')
        self.view.request = request
        self.assertFalse(self.view.get_load_catchment())

        request = self.factory.get('/')
        self.view.request = request
        self.view.load_catchment = False
        self.assertFalse(self.view.get_load_catchment())

    @patch('maps.views.reverse')
    def get_feature_details_url(self, mock_reverse):
        self.view.feature_details_url = 'test-url'
        self.assertEqual(self.view.get_feature_details_url(), 'test-url')

        self.view.feature_details_url = None
        self.view.api_basename = 'test-api'
        mock_reverse.return_value = '/mocked/url/0/'
        result = self.view.get_feature_details_url()
        mock_reverse.assert_called_once_with('test-api')
        self.assertEqual(result, '/mocked/url/')

    @patch('maps.views.reverse')
    def test_get_context_data(self, mock_reverse):
        request = self.factory.get('/')
        self.view.request = request
        mock_reverse.return_value = '/mocked/url/0/'

        self.view.map_title = 'Test title'
        self.view.load_region = True
        self.view.region_id = None
        self.view.region_url = None
        self.view.region_layer_style = None
        self.view.load_catchment = True
        self.view.catchment_url = None
        self.view.catchment_id = None
        self.view.catchment_layer_style = None
        self.view.load_features = True
        self.view.feature_url = None
        self.view.apply_filter_to_features = False
        self.view.feature_layer_style = {
            'color': '#63c36c',
            'fillOpacity': 1,
            'radius': 5,
            'stroke': False
        }
        self.view.adjust_bounds_to_features = True
        self.view.feature_summary_url = None
        self.view.api_basename = 'test-api'
        self.view.feature_details_url = None

        context = self.view.get_context_data()
        map_config = context['map_config']

        self.assertEqual(context['map_title'], 'Test title')
        self.assertTrue(map_config['loadRegion'])
        self.assertEqual(map_config['regionId'], None)
        self.assertEqual(map_config['regionUrl'], None)
        self.assertDictEqual(map_config['regionLayerStyle'], {'color': '#A1221C', 'fillOpacity': 0.0})
        self.assertEqual(map_config['loadCatchment'], True)
        self.assertEqual(map_config['catchmentUrl'], None)
        self.assertEqual(map_config['catchmentId'], None)
        self.assertDictEqual(map_config['catchmentLayerStyle'], {'color': '#A1221C', 'fillOpacity': 0.0})
        self.assertEqual(map_config['loadFeatures'], True)
        self.assertEqual(map_config['featureUrl'], None)
        self.assertEqual(map_config['applyFilterToFeatures'], False)
        self.assertDictEqual(map_config['featureLayerStyle'], {
            'color': '#63c36c',
            'fillOpacity': 1,
            'radius': 5,
            'stroke': False
        })
        self.assertEqual(map_config['adjustBoundsToFeatures'], True)
        self.assertEqual(map_config['featureSummaryUrl'], None)
        self.assertEqual(map_config['featureDetailsUrl'], '/mocked/url/')


# ----------- Location CRUD---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class LocationListViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['add_location', 'change_location']
    url = reverse('location-list')

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.location = Region.objects.create(name='Test Location')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(self.url)
        self.assertEqual(200, response.status_code)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(self.url)
        self.assertEqual(200, response.status_code)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url)
        self.assertEqual(200, response.status_code)

    def test_add_button_not_available_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(self.url)
        self.assertNotContains(response, reverse('location-create'))

    def test_add_button_available_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url)
        self.assertContains(response, reverse('location-create'))


class LocationCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_location'

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('location-create')
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, f'{settings.LOGIN_URL}?next={url}')

    def test_get_http_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('location-create'))
        self.assertEqual(403, response.status_code)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('location-create'))
        self.assertEqual(200, response.status_code)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('location-create'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('location-create')
        response = self.client.post(url, data={}, follow=True)
        self.assertRedirects(response, f'{settings.LOGIN_URL}?next={url}')

    def test_post_http_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('location-create'))
        self.assertEqual(403, response.status_code)

    def test_post_success_and_http_302_redirect_to_success_url_for_member(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Newly created location',
            'address': '123 Test St.',
            'geom': 'POINT (30 10)'
        }
        response = self.client.post(reverse('location-create'), data, follow=True)
        pk = Location.objects.get(name='Newly created location').pk
        self.assertRedirects(response, reverse('location-detail', kwargs={'pk': pk}))


class LocationDetailViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['change_location', 'delete_location']

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        location_data = {
            'name': 'Test Location',
            'address': 'Test Address',
            'geom': Point(0, 0)
        }
        cls.location = Location.objects.create(**location_data)

    def test_get_http_200_pk_for_anonymous(self):
        self.assertIsNotNone(self.location.pk)
        response = self.client.get(reverse('location-detail', kwargs={'pk': self.location.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'maps/location_detail.html')

    def test_edit_and_delete_button_not_available_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('location-detail', kwargs={'pk': self.location.pk}))
        self.assertNotContains(response, reverse('location-update', kwargs={'pk': self.location.pk}))
        self.assertNotContains(response, reverse('location-delete-modal', kwargs={'pk': self.location.pk}))

    def test_edit_button_available_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('location-detail', kwargs={'pk': self.location.pk}))
        self.assertContains(response, reverse('location-update', kwargs={'pk': self.location.pk}))
        self.assertContains(response, reverse('location-delete-modal', kwargs={'pk': self.location.pk}))


class LocationUpdateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'change_location'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        location_data = {
            'name': 'Test Location',
            'address': 'Test Address',
            'geom': Point(0, 0)
        }
        cls.location = Location.objects.create(**location_data)

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('location-update', kwargs={'pk': self.location.pk})
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, f'{settings.LOGIN_URL}?next={url}')

    def test_get_http_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('location-update', kwargs={'pk': self.location.pk}))
        self.assertEqual(403, response.status_code)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('location-update', kwargs={'pk': self.location.pk}))
        self.assertEqual(200, response.status_code)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('location-update', kwargs={'pk': self.location.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('location-update', kwargs={'pk': self.location.pk})
        response = self.client.post(url, data={}, follow=True)
        self.assertRedirects(response, f'{settings.LOGIN_URL}?next={url}')

    def test_post_http_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('location-update', kwargs={'pk': self.location.pk}), data={})
        self.assertEqual(403, response.status_code)

    def test_post_success_and_http_302_redirect_to_success_url_for_member(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Updated Test Location',
            'geom': 'POINT (30 10)'
        }
        response = self.client.post(reverse('location-update', kwargs={'pk': self.location.pk}), data, follow=True)
        self.assertRedirects(response, reverse('location-detail', kwargs={'pk': self.location.pk}))


class LocationModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'delete_location'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        location_data = {
            'name': 'Test Location',
            'address': 'Test Address',
            'geom': Point(0, 0)
        }
        cls.location = Location.objects.create(**location_data)

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('location-delete-modal', kwargs={'pk': self.location.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{settings.LOGIN_URL}?next={url}')

    def test_get_http_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('location-delete-modal', kwargs={'pk': self.location.pk}))
        self.assertEqual(403, response.status_code)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('location-delete-modal', kwargs={'pk': self.location.pk}))
        self.assertEqual(200, response.status_code)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('location-delete-modal', kwargs={'pk': self.location.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('location-delete-modal', kwargs={'pk': self.location.pk})
        response = self.client.post(url, data={})
        self.assertRedirects(response, f'{settings.LOGIN_URL}?next={url}')

    def test_post_http_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('location-delete-modal', kwargs={'pk': self.location.pk}), data={})
        self.assertEqual(403, response.status_code)

    def test_post_success_and_http_302_redirect_to_success_url_for_member(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('location-delete-modal', kwargs={'pk': self.location.pk}), {})
        self.assertRedirects(response, reverse('location-list'))
        with self.assertRaises(Region.DoesNotExist):
            Region.objects.get(pk=self.location.pk)


# ----------- Location CRUD---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class RegionListViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['add_region', 'change_region']
    url = reverse('region-list')

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.region = Region.objects.create(name='Test Region')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(self.url)
        self.assertEqual(200, response.status_code)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(self.url)
        self.assertEqual(200, response.status_code)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url)
        self.assertEqual(200, response.status_code)

    def test_add_button_not_available_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(self.url)
        self.assertNotContains(response, reverse('region-create'))

    def test_add_button_available_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url)
        self.assertContains(response, reverse('region-create'))


class RegionMapViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['add_region', 'change_region']
    url = reverse('region-map')

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.region = Region.objects.create(name='Test Region')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f'{settings.LOGIN_URL}?next={self.url}')

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(self.url)
        self.assertEqual(200, response.status_code)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url)
        self.assertEqual(200, response.status_code)

    def test_add_button_available_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url)
        self.assertContains(response, reverse('region-create'))


class RegionCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_region'

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('region-create')
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, f'{settings.LOGIN_URL}?next={url}')

    def test_get_http_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('region-create'))
        self.assertEqual(403, response.status_code)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('region-create'))
        self.assertEqual(200, response.status_code)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('region-create'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('region-create')
        response = self.client.post(url, data={}, follow=True)
        self.assertRedirects(response, f'{settings.LOGIN_URL}?next={url}')

    def test_post_http_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('region-create'))
        self.assertEqual(403, response.status_code)

    def test_post_success_and_http_302_redirect_to_success_url_for_member(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Newly created region',
            'country': 'DE',
            'geom': 'MULTIPOLYGON (((30 10, 40 40, 20 40, 10 20, 30 10)))'
        }
        response = self.client.post(reverse('region-create'), data, follow=True)
        pk = Region.objects.get(name='Newly created region').pk
        self.assertRedirects(response, reverse('region-detail', kwargs={'pk': pk}))


class RegionDetailViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['change_region', 'delete_region']

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.region = Region.objects.create(name='Test Region')

    def test_get_http_200_pk_for_anonymous(self):
        self.assertIsNotNone(self.region.pk)
        response = self.client.get(reverse('region-detail', kwargs={'pk': self.region.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'maps/region_detail.html')

    def test_edit_and_delete_button_not_available_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('region-detail', kwargs={'pk': self.region.pk}))
        self.assertNotContains(response, reverse('region-update', kwargs={'pk': self.region.pk}))
        self.assertNotContains(response, reverse('region-delete-modal', kwargs={'pk': self.region.pk}))

    def test_edit_button_available_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('region-detail', kwargs={'pk': self.region.pk}))
        self.assertContains(response, reverse('region-update', kwargs={'pk': self.region.pk}))
        self.assertContains(response, reverse('region-delete-modal', kwargs={'pk': self.region.pk}))


class RegionUpdateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'change_region'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.region = Region.objects.create(name='Test Region')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('region-update', kwargs={'pk': self.region.pk})
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, f'{settings.LOGIN_URL}?next={url}')

    def test_get_http_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('region-update', kwargs={'pk': self.region.pk}))
        self.assertEqual(403, response.status_code)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('region-update', kwargs={'pk': self.region.pk}))
        self.assertEqual(200, response.status_code)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('region-update', kwargs={'pk': self.region.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('region-update', kwargs={'pk': self.region.pk})
        response = self.client.post(url, data={}, follow=True)
        self.assertRedirects(response, f'{settings.LOGIN_URL}?next={url}')

    def test_post_http_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('region-update', kwargs={'pk': self.region.pk}), data={})
        self.assertEqual(403, response.status_code)

    def test_post_success_and_http_302_redirect_to_success_url_for_member(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Updated Test Region',
            'country': 'DE',
            'geom': 'MULTIPOLYGON (((30 10, 40 40, 20 40, 10 20, 30 10)))'
        }
        response = self.client.post(reverse('region-update', kwargs={'pk': self.region.pk}), data, follow=True)
        self.assertRedirects(response, reverse('region-detail', kwargs={'pk': self.region.pk}))


class RegionModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'delete_region'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.region = Region.objects.create(name='Test Region')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('region-delete-modal', kwargs={'pk': self.region.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{settings.LOGIN_URL}?next={url}')

    def test_get_http_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('region-delete-modal', kwargs={'pk': self.region.pk}))
        self.assertEqual(403, response.status_code)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('region-delete-modal', kwargs={'pk': self.region.pk}))
        self.assertEqual(200, response.status_code)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('region-delete-modal', kwargs={'pk': self.region.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('region-delete-modal', kwargs={'pk': self.region.pk})
        response = self.client.post(url, data={})
        self.assertRedirects(response, f'{settings.LOGIN_URL}?next={url}')

    def test_post_http_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('region-delete-modal', kwargs={'pk': self.region.pk}), data={})
        self.assertEqual(403, response.status_code)

    def test_post_success_and_http_302_redirect_to_success_url_for_member(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('region-delete-modal', kwargs={'pk': self.region.pk}), {})
        self.assertRedirects(response, reverse('region-list'))
        with self.assertRaises(Region.DoesNotExist):
            Region.objects.get(pk=self.region.pk)


# ----------- Catchment CRUD--------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CatchmentListViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['add_catchment', 'change_catchment']
    url = reverse('catchment-list')

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.catchment = Catchment.objects.create(name='Test Catchment')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(self.url)
        self.assertEqual(200, response.status_code)

    def test_add_and_dashboard_button_not_available_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(self.url)
        self.assertNotContains(response, reverse('catchment-create'))
        self.assertNotContains(response, reverse('maps-dashboard'))

    def test_add_and_dashboard_button_available_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url)
        self.assertContains(response, reverse('catchment-create'))
        self.assertContains(response, reverse('maps-dashboard'))


class CatchmentCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_catchment'

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('catchment-create')
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, f'{settings.LOGIN_URL}?next={url}')

    def test_get_http_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('catchment-create'))
        self.assertEqual(403, response.status_code)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('catchment-create'))
        self.assertEqual(200, response.status_code)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('catchment-create'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('catchment-create')
        response = self.client.post(url, data={}, follow=True)
        self.assertRedirects(response, f'{settings.LOGIN_URL}?next={url}')

    def test_post_http_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('catchment-create'))
        self.assertEqual(403, response.status_code)

    def test_post_success_and_http_302_redirect_to_success_url_for_member(self):
        self.client.force_login(self.member)
        data = {'name': 'Updated Test Catchment', 'type': 'custom', 'region': Region.objects.create().pk}
        response = self.client.post(reverse('catchment-create'), data, follow=True)
        self.assertRedirects(response, reverse('catchment-detail',
                                               kwargs={'pk': list(response.context.get('messages'))[0].message}))


class CatchmentCreateByMergeViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_catchment'
    url = reverse('catchment-create-by-merge')

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        lau_1 = LauRegion.objects.create(
            name='Test Region 1',
            borders=GeoPolygon.objects.create(geom=MultiPolygon(Polygon(((0, 0), (0, 2), (2, 2), (2, 0), (0, 0)))))
        )
        cls.region_1 = lau_1.region_ptr
        lau_2 = LauRegion.objects.create(
            name='Test Region 2',
            borders=GeoPolygon.objects.create(geom=MultiPolygon(Polygon(((0, 2), (0, 4), (2, 4), (2, 2), (0, 2)))))
        )
        cls.region_2 = lau_2.region_ptr
        lau_3 = LauRegion.objects.create(
            name='Test Region 3',
            borders=GeoPolygon.objects.create(geom=MultiPolygon(Polygon(((1, 1), (1, 3), (3, 3), (3, 1), (1, 1)))))
        )
        cls.region_3 = lau_3.region_ptr
        cls.parent_catchment = Catchment.objects.create(
            name='Parent Catchment',
            region=Region.objects.create()
        )

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        response = self.client.get(self.url, follow=True)
        self.assertRedirects(response, f'{settings.LOGIN_URL}?next={self.url}')

    def test_get_http_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(self.url)
        self.assertEqual(403, response.status_code)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url)
        self.assertEqual(200, response.status_code)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url)
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        response = self.client.post(self.url, data={}, follow=True)
        self.assertRedirects(response, f'{settings.LOGIN_URL}?next={self.url}')

    def test_post_http_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.post(self.url)
        self.assertEqual(403, response.status_code)

    def test_post_success_and_http_302_redirect_to_success_url_for_member(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Updated Test Catchment',
            'parent': self.parent_catchment.pk,
            'form-INITIAL_FORMS': 2,
            'form-TOTAL_FORMS': 3,
            'form-0-region': self.region_1.pk,
            'form-1-region': self.region_2.pk,
            'form-2-region': self.region_3.pk,
        }
        response = self.client.post(self.url, data, follow=True)
        self.assertRedirects(response, reverse('catchment-detail',
                                               kwargs={'pk': list(response.context.get('messages'))[0].message}))

    def test_create_region_borders(self):
        data = {
            'name': 'New Catchment Created By Merge',
            'parent': self.parent_catchment.pk,
            'form-INITIAL_FORMS': 2,
            'form-TOTAL_FORMS': 3,
            'form-0-region': self.region_1.pk,
            'form-1-region': self.region_2.pk,
            'form-2-region': self.region_3.pk,
        }
        request = RequestFactory().post(self.url, data)
        request.user = self.member
        view = CatchmentCreateByMergeView()
        view.setup(request)
        view.formset = view.get_formset()
        self.assertTrue(view.formset.is_valid())
        geom = MultiPolygon(Polygon(((0, 0), (0, 2), (0, 4), (2, 4), (2, 3), (3, 3), (3, 1), (2, 1), (2, 0), (0, 0))))
        geom.normalize()
        self.assertTrue(view.create_region_borders().geom.equals_exact(geom))

    def test_get_region_name(self):
        data = {
            'name': 'New Catchment Created By Merge',
            'parent': self.parent_catchment.pk,
            'form-INITIAL_FORMS': 2,
            'form-TOTAL_FORMS': 2,
            'form-0-region': self.region_1.pk,
            'form-1-region': self.region_2.pk,
        }
        request = RequestFactory().post(self.url, data)
        request.user = self.member
        view = CatchmentCreateByMergeView()
        view.setup(request)
        form = view.get_form()
        self.assertTrue(form.is_valid())
        view.object = form.save()
        self.assertEqual('New Catchment Created By Merge', view.get_region_name())

    def test_get_region(self):
        data = {
            'name': 'New Catchment Created By Merge',
            'parent': self.parent_catchment.pk,
            'form-INITIAL_FORMS': 2,
            'form-TOTAL_FORMS': 3,
            'form-0-region': self.region_1.pk,
            'form-1-region': self.region_2.pk,
            'form-2-region': self.region_3.pk,
        }
        request = RequestFactory().post(self.url, data)
        request.user = self.member
        view = CatchmentCreateByMergeView()
        view.setup(request)
        view.form = view.get_form()
        self.assertTrue(view.form.is_valid())
        view.object = view.form.save()
        view.formset = view.get_formset()
        self.assertTrue(view.formset.is_valid())
        geom = MultiPolygon(Polygon(((0, 0), (0, 2), (0, 4), (2, 4), (2, 3), (3, 3), (3, 1), (2, 1), (2, 0), (0, 0))))
        geom.normalize()
        expected_region = Region.objects.create(
            name='New Catchment Created By Merge',
            borders=GeoPolygon.objects.create(geom=geom)
        )
        self.assertEqual(expected_region.name, view.get_region().name)
        self.assertTrue(view.get_region().borders.geom.equals_exact(geom))

    def test_catchment_with_correct_region_is_created_on_post_with_valid_data(self):
        self.client.force_login(self.member)
        data = {
            'name': 'New Catchment Created By Merge',
            'parent': self.parent_catchment.pk,
            'form-INITIAL_FORMS': 2,
            'form-TOTAL_FORMS': 3,
            'form-0-region': self.region_1.pk,
            'form-1-region': self.region_2.pk,
            'form-2-region': self.region_3.pk,
        }
        response = self.client.post(self.url, data, follow=True)
        self.assertRedirects(response, reverse('catchment-detail',
                                               kwargs={'pk': list(response.context.get('messages'))[0].message}))
        catchment = Catchment.objects.get(pk=list(response.context.get('messages'))[0].message)
        geom = MultiPolygon(Polygon(((0, 0), (0, 2), (0, 4), (2, 4), (2, 3), (3, 3), (3, 1), (2, 1), (2, 0), (0, 0))))
        geom.normalize()
        expected_region = Region.objects.create(
            name='New Catchment Created By Merge',
            borders=GeoPolygon.objects.create(geom=geom)
        )
        self.assertEqual(expected_region.name, catchment.region.name)
        self.assertTrue(catchment.region.borders.geom.equals_exact(geom))
        self.assertTrue(catchment.type == 'custom')

    def test_at_least_one_entry_in_formset_is_enforced(self):
        self.client.force_login(self.member)
        data = {
            'name': 'New Catchment Created By Merge',
            'parent': self.parent_catchment.pk,
            'form-INITIAL_FORMS': 2,
            'form-TOTAL_FORMS': 2,
            'form-0-region': '',
            'form-1-region': '',
        }
        response = self.client.post(self.url, data)
        self.assertEqual(200, response.status_code)
        self.assertIn('You must select at least one region.', response.context['formset'].non_form_errors())

    def test_empty_forms_are_ignored(self):
        self.client.force_login(self.member)
        data = {
            'name': 'New Catchment Created By Merge',
            'parent': self.parent_catchment.pk,
            'form-INITIAL_FORMS': 2,
            'form-TOTAL_FORMS': 4,
            'form-0-region': self.region_1.pk,
            'form-1-region': self.region_2.pk,
            'form-2-region': '',
            'form-3-region': '',
        }
        response = self.client.post(self.url, data)
        self.assertEqual(302, response.status_code)


class CatchmentDetailViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['change_catchment', 'delete_catchment']

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.catchment = Catchment.objects.create(name='Test Catchment')

    def test_get_http_200_pk_for_anonymous(self):
        response = self.client.get(reverse('catchment-detail', kwargs={'pk': self.catchment.pk}))
        self.assertEqual(200, response.status_code)
        self.assertTemplateUsed(response, 'maps/catchment_detail.html')

    def test_edit_and_delete_button_not_available_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('catchment-detail', kwargs={'pk': self.catchment.pk}))
        self.assertNotContains(response, reverse('catchment-update', kwargs={'pk': self.catchment.pk}))
        self.assertNotContains(response, reverse('catchment-delete-modal', kwargs={'pk': self.catchment.pk}))

    def test_edit_button_available_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('catchment-detail', kwargs={'pk': self.catchment.pk}))
        self.assertContains(response, reverse('catchment-update', kwargs={'pk': self.catchment.pk}))
        self.assertContains(response, reverse('catchment-delete-modal', kwargs={'pk': self.catchment.pk}))


class CatchmentUpdateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'change_catchment'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.region = Region.objects.create()
        cls.catchment = Catchment.objects.create(name='Test Catchment')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('catchment-update', kwargs={'pk': self.catchment.pk})
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, f'{settings.LOGIN_URL}?next={url}')

    def test_get_http_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('catchment-update', kwargs={'pk': self.catchment.pk}))
        self.assertEqual(403, response.status_code)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('catchment-update', kwargs={'pk': self.catchment.pk}))
        self.assertEqual(200, response.status_code)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('catchment-update', kwargs={'pk': self.catchment.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('catchment-update', kwargs={'pk': self.catchment.pk})
        response = self.client.post(url, data={}, follow=True)
        self.assertRedirects(response, f'{settings.LOGIN_URL}?next={url}')

    def test_post_http_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('catchment-update', kwargs={'pk': self.catchment.pk}), data={})
        self.assertEqual(403, response.status_code)

    def test_post_success_and_http_302_redirect_to_success_url_for_member(self):
        self.client.force_login(self.member)
        data = {'name': 'Updated Test Catchment', 'type': 'custom', 'region': self.region.pk}
        response = self.client.post(reverse('catchment-update', kwargs={'pk': self.catchment.pk}), data, follow=True)
        self.assertRedirects(response, reverse('catchment-detail', kwargs={'pk': self.catchment.pk}))


class CatchmentModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'delete_catchment'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.catchment = Catchment.objects.create(name='Test Catchment', region=Region.objects.create())

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('catchment-delete-modal', kwargs={'pk': self.catchment.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{settings.LOGIN_URL}?next={url}')

    def test_get_http_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('catchment-delete-modal', kwargs={'pk': self.catchment.pk}))
        self.assertEqual(403, response.status_code)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('catchment-delete-modal', kwargs={'pk': self.catchment.pk}))
        self.assertEqual(200, response.status_code)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('catchment-delete-modal', kwargs={'pk': self.catchment.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('catchment-delete-modal', kwargs={'pk': self.catchment.pk})
        response = self.client.post(url, data={})
        self.assertRedirects(response, f'{settings.LOGIN_URL}?next={url}')

    def test_post_http_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('catchment-delete-modal', kwargs={'pk': self.catchment.pk}), data={})
        self.assertEqual(403, response.status_code)

    def test_post_success_and_http_302_redirect_to_success_url_for_member(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('catchment-delete-modal', kwargs={'pk': self.catchment.pk}), {})
        self.assertRedirects(response, reverse('catchment-list'))
        with self.assertRaises(Catchment.DoesNotExist):
            Catchment.objects.get(pk=self.catchment.pk)


# ----------- Catchment API---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CatchmentGeometryAPITestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.catchment = Catchment.objects.create(name='Test Catchment')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(
            reverse('data.catchment-geometries') + '?' + urlencode({'catchment': self.catchment.pk}))
        self.assertEqual(200, response.status_code)


class NutsRegionMapViewTestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        region = Region.objects.create(name='Test Region')
        GeoDataset.objects.create(
            name='Test Dataset',
            region=region,
            model_name='NutsRegion'
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('NutsRegion'))
        self.assertEqual(response.status_code, 200)


class NutsAndLauCatchmentPedigreeAPITestCase(ViewSetWithPermissionsTestCase):
    member_permissions = 'add_collection'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        level_0_region = NutsRegion.objects.create(
            nuts_id='XX',
            levl_code=0,
            name_latn='Level 0 Region'
        )
        cls.level_0_catchment = Catchment.objects.create(
            region=level_0_region.region_ptr
        )
        level_1_region = NutsRegion.objects.create(
            nuts_id='XX0',
            levl_code=1,
            name_latn='Level 1 Region',
            parent=level_0_region
        )
        cls.level_1_catchment = Catchment.objects.create(
            region=level_1_region.region_ptr,
            parent_region=level_0_region.region_ptr
        )
        level_2_region_1 = NutsRegion.objects.create(
            nuts_id='XX00',
            levl_code=2,
            name_latn='Level 2 Region 1',
            parent=level_1_region
        )
        cls.level_2_catchment_1 = Catchment.objects.create(
            region=level_2_region_1.region_ptr,
            parent_region=level_1_region.region_ptr
        )
        level_2_region_2 = NutsRegion.objects.create(
            nuts_id='XX01',
            levl_code=2,
            name_latn='Level 2 Region 2',
            parent=level_1_region
        )
        cls.level_2_catchment_1 = Catchment.objects.create(
            region=level_2_region_2.region_ptr,
            parent_region=level_1_region.region_ptr
        )
        level_3_region_1 = NutsRegion.objects.create(
            nuts_id='XX000',
            levl_code=3,
            name_latn='Level 3 Region 1',
            parent=level_2_region_1
        )
        cls.level_3_catchment_1 = Catchment.objects.create(
            region=level_3_region_1.region_ptr,
            parent_region=level_2_region_1.region_ptr
        )
        level_3_region_2 = NutsRegion.objects.create(
            nuts_id='XX011',
            levl_code=3,
            name_latn='Level 3 Region 2',
            parent=level_2_region_2
        )
        cls.level_3_catchment_2 = Catchment.objects.create(
            region=level_3_region_2.region_ptr,
            parent_region=level_2_region_2.region_ptr
        )
        level_4_region_1 = LauRegion.objects.create(
            lau_id='X00000000',
            lau_name='Level 4 Region 1',
            nuts_parent=level_3_region_1
        )
        cls.level_4_catchment_1 = Catchment.objects.create(
            region=level_4_region_1.region_ptr,
            parent_region=level_3_region_1.region_ptr
        )
        level_4_region_2 = LauRegion.objects.create(
            lau_id='X00000001',
            lau_name='Level 4 Region 2',
            nuts_parent=level_3_region_2
        )
        cls.level_4_catchment_2 = Catchment.objects.create(
            region=level_4_region_2.region_ptr,
            parent_region=level_3_region_2.region_ptr
        )

    def test_get_http_200_ok_for_anonymous(self):
        catchment = Catchment.objects.get(region__nutsregion__nuts_id='XX')
        response = self.client.get(
            reverse('data.nuts_lau_catchment_options'),
            {'id': catchment.id, 'direction': 'children'}
        )
        self.assertEqual(response.status_code, 200)

    def test_get_http_400_bad_request_on_missing_query_parameter_id(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('data.nuts_lau_catchment_options'), {'direction': 'children'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data['detail'],
            'Query parameter "id" missing. Must provide valid catchment id.')

    def test_get_http_400_bad_request_on_missing_query_parameter_direction(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('data.nuts_lau_catchment_options'), {'id': self.level_0_catchment.id})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data['detail'],
            'Missing or wrong query parameter "direction". Options: "parents", "children"'
        )

    def test_get_http_400_bad_request_on_wrong_query_parameter_direction(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse('data.nuts_lau_catchment_options'),
            {'id': self.level_0_catchment.id, 'direction': 'south'}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data['detail'],
            'Missing or wrong query parameter "direction". Options: "parents", "children"'
        )

    def test_get_http_404_bad_request_on_non_existing_region_id(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('data.nuts_lau_catchment_options'), {'id': 0, 'direction': 'parents'})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['detail'], 'A NUTS region with the provided id does not exist.')

    def test_get_response_contains_level_4_in_children_if_input_is_level_3(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse('data.nuts_lau_catchment_options'),
            {'id': self.level_3_catchment_1.id, 'direction': 'children'}
        )
        self.assertIn('id_level_4', response.data)


class NutsRegionSummaryAPIViewTestCase(ViewSetWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        NutsRegion.objects.create(
            nuts_id='TE57',
            name_latn='Test NUTS'
        )

    def setUp(self):
        self.region = NutsRegion.objects.get(nuts_id='TE57')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('data.nutsregion-summary'), {'pk': self.region.pk})
        self.assertEqual(response.status_code, 200)

    def test_returns_correct_data(self):
        response = self.client.get(reverse('data.nutsregion-summary'), {'pk': self.region.pk})
        self.assertIn('summaries', response.data)
        self.assertEqual(response.data['summaries'][0]['Name'], self.region.name_latn)


# ----------- Attribute CRUD -------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class AttributeListViewTestCase(ViewWithPermissionsTestCase):

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('attribute-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('attribute-list'))
        self.assertEqual(response.status_code, 200)


class AttributeCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_attribute'

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('attribute-create'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('attribute-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('attribute-create'))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('attribute-create'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('attribute-create'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('attribute-create'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Attribute', 'unit': 'Test Unit'}
        response = self.client.post(reverse('attribute-create'), data=data)
        self.assertEqual(response.status_code, 302)


class AttributeModalCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_attribute'

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('attribute-create-modal'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('attribute-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('attribute-create-modal'))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('attribute-create-modal'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('attribute-create-modal'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('attribute-create-modal'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Attribute', 'unit': 'Test Unit'}
        response = self.client.post(reverse('attribute-create-modal'), data=data)
        self.assertEqual(response.status_code, 302)


class AttributeDetailViewTestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.attribute = Attribute.objects.create(
            name='Test Attribute',
            unit='Test Unit',
            description='This ist a test element'
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('attribute-detail', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('attribute-detail', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 200)


class AttributeModalDetailViewTestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.attribute = Attribute.objects.create(
            name='Test Attribute',
            unit='Test Unit',
            description='This ist a test element'
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('attribute-detail-modal', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('attribute-detail-modal', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 200)


class AttributeUpdateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'change_attribute'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.attribute = Attribute.objects.create(
            name='Test Attribute',
            unit='Test Unit',
            description='This ist a test element'
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('attribute-update', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('attribute-update', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('attribute-update', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('attribute-update', kwargs={'pk': self.attribute.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('attribute-update', kwargs={'pk': self.attribute.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        data = {'name': 'Updated Attribute', 'unit': self.attribute.unit}
        response = self.client.post(reverse('attribute-update', kwargs={'pk': self.attribute.pk}), data=data)
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Updated Attribute', 'unit': self.attribute.unit}
        response = self.client.post(reverse('attribute-update', kwargs={'pk': self.attribute.pk}), data=data)
        self.assertEqual(response.status_code, 302)


class AttributeModalUpdateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'change_attribute'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.attribute = Attribute.objects.create(
            name='Test Attribute',
            unit='Test Unit',
            description='This ist a test element'
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('attribute-update-modal', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('attribute-update-modal', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('attribute-update-modal', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('attribute-update-modal', kwargs={'pk': self.attribute.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('attribute-update-modal', kwargs={'pk': self.attribute.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        data = {'name': 'Updated Attribute', 'unit': self.attribute.unit}
        response = self.client.post(reverse('attribute-update-modal', kwargs={'pk': self.attribute.pk}), data=data)
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Updated Attribute', 'unit': self.attribute.unit}
        response = self.client.post(reverse('attribute-update-modal', kwargs={'pk': self.attribute.pk}), data=data)
        self.assertEqual(response.status_code, 302)


class AttributeModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'delete_attribute'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.attribute = Attribute.objects.create(
            name='Test Attribute',
            unit='Test Unit',
            description='This ist a test element'
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('attribute-delete-modal', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('attribute-delete-modal', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('attribute-delete-modal', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('attribute-delete-modal', kwargs={'pk': self.attribute.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('attribute-delete-modal', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('attribute-delete-modal', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_successful_delete_and_http_302_and_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('attribute-delete-modal', kwargs={'pk': self.attribute.pk}))
        with self.assertRaises(Attribute.DoesNotExist):
            Attribute.objects.get(pk=self.attribute.pk)
        self.assertEqual(response.status_code, 302)


# ----------- Region Attribute Value CRUD ------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class RegionAttributeValueListViewTestCase(ViewWithPermissionsTestCase):

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('regionattributevalue-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('regionattributevalue-list'))
        self.assertEqual(response.status_code, 200)


class RegionAttributeValueCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_regionattributevalue'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.region = Region.objects.create(name='Test Region')
        cls.attribute = Attribute.objects.create(name='Test Attribute', unit='Test Unit')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('regionattributevalue-create'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('regionattributevalue-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('regionattributevalue-create'))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('regionattributevalue-create'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('regionattributevalue-create'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('regionattributevalue-create'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Test Attribute Value',
            'region': self.region.id,
            'date': '2022-01-01',
            'attribute': self.attribute.id,
            'value': 123.321
        }
        response = self.client.post(reverse('regionattributevalue-create'), data=data)
        self.assertEqual(response.status_code, 302)


class RegionAttributeValueModalCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_regionattributevalue'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.region = Region.objects.create(name='Test Region')
        cls.attribute = Attribute.objects.create(name='Test Attribute', unit='Test Unit')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('regionattributevalue-create-modal'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('regionattributevalue-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('regionattributevalue-create-modal'))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('regionattributevalue-create-modal'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('regionattributevalue-create-modal'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('regionattributevalue-create-modal'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Test Attribute Value',
            'region': self.region.id,
            'date': '2022-01-01',
            'attribute': self.attribute.id,
            'value': 123.321
        }
        response = self.client.post(reverse('regionattributevalue-create-modal'), data=data)
        self.assertEqual(response.status_code, 302)


class RegionAttributeValueDetailViewTestCase(ViewWithPermissionsTestCase):
    value = None

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        region = Region.objects.create(name='Test Region')
        attribute = Attribute.objects.create(name='Test Attribute', unit='Test Unit')
        cls.value = RegionAttributeValue.objects.create(
            name='Test Value',
            region=region,
            attribute=attribute,
            value=123.312
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('regionattributevalue-detail', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('regionattributevalue-detail', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 200)


class RegionAttributeValueModalDetailViewTestCase(ViewWithPermissionsTestCase):
    value = None

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        region = Region.objects.create(name='Test Region')
        attribute = Attribute.objects.create(name='Test Attribute', unit='Test Unit')
        cls.value = RegionAttributeValue.objects.create(
            name='Test Value',
            region=region,
            attribute=attribute,
            value=123.312
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('regionattributevalue-detail-modal', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('regionattributevalue-detail-modal', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 200)


class RegionAttributeValueUpdateViewTestCase(ViewWithPermissionsTestCase):
    attribute = None
    region = None
    value = None
    member_permissions = 'change_regionattributevalue'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.region = Region.objects.create(name='Test Region')
        cls.attribute = Attribute.objects.create(name='Test Attribute', unit='Test Unit')
        cls.value = RegionAttributeValue.objects.create(
            name='Test Value',
            region=cls.region,
            attribute=cls.attribute,
            value=123.312
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('regionattributevalue-update', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('regionattributevalue-update', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('regionattributevalue-update', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('regionattributevalue-update', kwargs={'pk': self.value.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('regionattributevalue-update', kwargs={'pk': self.value.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        data = {
            'name': 'Updated Value',
            'region': self.region.id,
            'attribute': self.attribute.id,
            'value': 456.654
        }
        response = self.client.post(reverse('regionattributevalue-update', kwargs={'pk': self.value.pk}), data=data)
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Updated Value',
            'region': self.region.id,
            'date': '2022-01-01',
            'attribute': self.attribute.id,
            'value': 456.654
        }
        response = self.client.post(reverse('regionattributevalue-update', kwargs={'pk': self.value.pk}), data=data)
        self.assertEqual(response.status_code, 302)


class RegionAttributeValueModalUpdateViewTestCase(ViewWithPermissionsTestCase):
    attribute = None
    region = None
    value = None
    member_permissions = 'change_regionattributevalue'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.region = Region.objects.create(name='Test Region')
        cls.attribute = Attribute.objects.create(name='Test Attribute', unit='Test Unit')
        cls.value = RegionAttributeValue.objects.create(
            name='Test Value',
            region=cls.region,
            attribute=cls.attribute,
            value=123.312
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('regionattributevalue-update-modal', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('regionattributevalue-update-modal', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('regionattributevalue-update-modal', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('regionattributevalue-update-modal', kwargs={'pk': self.value.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('regionattributevalue-update-modal', kwargs={'pk': self.value.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        data = {
            'name': 'Updated Value',
            'region': self.region.id,
            'attribute': self.attribute.id,
            'value': 456.654
        }
        response = self.client.post(
            reverse('regionattributevalue-update-modal', kwargs={'pk': self.value.pk}),
            data=data
        )
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Updated Value',
            'region': self.region.id,
            'date': '2022-01-01',
            'attribute': self.attribute.id,
            'value': 456.654
        }
        response = self.client.post(
            reverse('regionattributevalue-update-modal', kwargs={'pk': self.value.pk}),
            data=data
        )
        self.assertEqual(response.status_code, 302)


class RegionAttributeValueModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    value = None
    member_permissions = 'delete_regionattributevalue'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.value = RegionAttributeValue.objects.create(
            name='Test Value',
            region=Region.objects.create(name='Test Region'),
            attribute=Attribute.objects.create(name='Test Attribute', unit='Test Unit'),
            value=123.312
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('regionattributevalue-delete-modal', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('regionattributevalue-delete-modal', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('regionattributevalue-delete-modal', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('regionattributevalue-delete-modal', kwargs={'pk': self.value.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('regionattributevalue-delete-modal', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('regionattributevalue-delete-modal', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_successful_delete_and_http_302_and_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('regionattributevalue-delete-modal', kwargs={'pk': self.value.pk}))
        with self.assertRaises(RegionAttributeValue.DoesNotExist):
            RegionAttributeValue.objects.get(pk=self.value.pk)
        self.assertEqual(response.status_code, 302)


# ----------- Region Utils ---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class RegionOfLauAutocompleteViewTestCase(ViewWithPermissionsTestCase):
    url = reverse('region-of-lau-autocomplete')

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.region_1 = LauRegion.objects.create(name='Test Region 1', lau_id='123').region_ptr
        cls.region_2 = LauRegion.objects.create(name='Test Region 2', lau_id='234').region_ptr
        cls.region_3 = Region.objects.create(name='Test Region Not In Queryset')

    def test_all_lau_regions_with_matching_name_string_in_queryset(self):
        response = self.client.get(self.url, data={'q': 'Test'})
        self.assertEqual(200, response.status_code)
        ids = [region['id'] for region in json.loads(response.content)['results']]
        self.assertListEqual([str(lau.id) for lau in LauRegion.objects.all()], ids)

    def test_all_lau_region_with_matching_lau_id_in_queryset(self):
        response = self.client.get(self.url, data={'q': '12'})
        self.assertEqual(200, response.status_code)
        ids = [region['id'] for region in json.loads(response.content)['results']]
        self.assertListEqual([str(lau.id) for lau in LauRegion.objects.filter(lau_id='123')], ids)

    def test_all_lau_region_with_matching_lau_id_in_queryset_2(self):
        response = self.client.get(self.url, data={'q': '23'})
        self.assertEqual(200, response.status_code)
        ids = [region['id'] for region in json.loads(response.content)['results']]
        self.assertListEqual([str(lau.id) for lau in LauRegion.objects.all()], ids)
