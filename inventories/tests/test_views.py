from django.test import TestCase, modify_settings
from django.urls import reverse

from maps.models import Catchment, Region
from users.models import User
from ..models import Scenario


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class ScenarioResultDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = User.objects.create(username='owner', password='very-secure!')
        region = Region.objects.create(
            owner=owner,
            name='Test Region'
        )
        catchment = Catchment.objects.create(
            owner=owner,
            name='Test Catchment'
        )
        Scenario.objects.create(
            owner=owner,
            name='Test Scenario',
            region=region,
            catchment=catchment
        )

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.scenario = Scenario.objects.get(name='Test Scenario')

    def test_get_http_200_ok_for_scenario_owner(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('scenario-result', kwargs={'pk': self.scenario.pk}))
        self.assertEqual(response.status_code, 200)
