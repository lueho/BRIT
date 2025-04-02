from django.urls import reverse

from maps.models import Catchment, Region
from utils.tests.testcases import AbstractTestCases, ViewWithPermissionsTestCase
from ..models import Scenario


# ----------- Scenario CRUD --------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class ScenarioCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_scenario'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.region = Region.objects.create(name='Test Region')
        cls.catchment = Catchment.objects.create(name='Test Catchment', region=cls.region, parent_region=cls.region)

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('scenario-create')
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('scenario-create'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('scenario-create'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('scenario-create')
        response = self.client.post(url, {})
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('scenario-create'))
        self.assertEqual(response.status_code, 200)

    def test_post_success_and_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Test Scenario',
            'region': self.region.pk,
            'catchment': self.catchment.pk
        }
        response = self.client.post(reverse('scenario-create'), data, follow=True)
        created_pk = list(response.context.get('messages'))[0].message
        self.assertRedirects(response, reverse('scenario-detail', kwargs={'pk': created_pk}))


class ScenarioCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    dashboard_view = False

    model = Scenario

    view_create_name = 'scenario-create'
    view_published_list_name = 'scenario-list'
    view_private_list_name = 'scenario-list-owned'
    view_detail_name = 'scenario-detail'
    view_update_name = 'scenario-update'
    view_delete_name = 'scenario-delete-modal'

    create_object_data = {'name': 'Test Scenario'}
    update_object_data = {'name': 'Updated Test Scenario'}

    @classmethod
    def create_related_objects(cls):
        region = Region.objects.create(name='Test Region')
        return {
            'region': region,
            'catchment': Catchment.objects.create(name='Test Catchment', region=region, parent_region=region)
        }


class ScenarioResultCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    dashboard_view = False
    create_view = False
    public_list_view = False
    private_list_view = False
    delete_view = False

    update_view = False

    model = Scenario
    view_detail_name = 'scenario-result'

    create_object_data = {'name': 'Test Scenario'}

    @classmethod
    def create_related_objects(cls):
        region = Region.objects.create(name='Test Region')
        return {
            'region': region,
            'catchment': Catchment.objects.create(name='Test Catchment', region=region, parent_region=region)
        }
