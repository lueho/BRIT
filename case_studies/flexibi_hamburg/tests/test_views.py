from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.test import TestCase, modify_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from ..models import HamburgRoadsideTrees


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class HamburgRoadSideTreeAPITestCase(APITestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')
        HamburgRoadsideTrees.objects.create(
            geom=Point(0, 0, srid=4326)
        )

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')

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
