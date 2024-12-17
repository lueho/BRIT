from django.urls import reverse

from maps.models import Catchment, Region
from utils.tests.testcases import AbstractTestCases, ViewWithPermissionsTestCase
from ..models import Scenario


# ----------- Scenario CRUD --------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class ScenarioListViewTestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        region = Region.objects.create(name='Test Region')
        catchment = Catchment.objects.create(name='Test Catchment', region=region, parent_region=region)
        Scenario.objects.create(name='Test Scenario', region=region, catchment=catchment)

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('scenario-list'))
        self.assertEqual(200, response.status_code)


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
    model = Scenario
    view_detail_name = 'scenario-detail'
    view_update_name = 'scenario-update'
    view_delete_name = 'scenario-delete-modal'

    create_object_data = {'name': 'Test Scenario'}

    @classmethod
    def create_related_objects(cls):
        region = Region.objects.create(name='Test Region')
        return {
            'region': region,
            'catchment': Catchment.objects.create(name='Test Catchment', region=region, parent_region=region)
        }


class ScenarioUpdateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'change_scenario'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        region = Region.objects.create(name='Test Region')
        catchment = Catchment.objects.create(name='Test Catchment', region=region, parent_region=region)
        cls.scenario = Scenario.objects.create(
            name='Test Scenario', region=region, catchment=catchment, publication_status='published'
        )

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('scenario-update', kwargs={'pk': self.scenario.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('scenario-update', kwargs={'pk': self.scenario.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('scenario-update', kwargs={'pk': self.scenario.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('scenario-update', kwargs={'pk': self.scenario.pk})
        response = self.client.post(url, {})
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('scenario-update', kwargs={'pk': self.scenario.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_to_success_url_for_member(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Updated Test Scenario',
            'region': self.scenario.region.pk,
            'catchment': self.scenario.catchment.pk
        }
        response = self.client.post(reverse('scenario-update', kwargs={'pk': self.scenario.pk}), data)
        self.assertRedirects(response, reverse('scenario-detail', kwargs={'pk': self.scenario.pk}))


class ScenarioModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'delete_scenario'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.scenario = Scenario.objects.create(name='Test Scenario')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('scenario-delete-modal', kwargs={'pk': self.scenario.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('scenario-delete-modal', kwargs={'pk': self.scenario.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('scenario-delete-modal', kwargs={'pk': self.scenario.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('scenario-delete-modal', kwargs={'pk': self.scenario.pk})
        response = self.client.post(url, {})
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('scenario-delete-modal', kwargs={'pk': self.scenario.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_successful_delete_and_http_302_and_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('scenario-delete-modal', kwargs={'pk': self.scenario.pk}))
        self.assertRedirects(response, reverse('scenario-list'))
        with self.assertRaises(Scenario.DoesNotExist):
            Scenario.objects.get(pk=self.scenario.pk)


class ScenarioResultCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    model = Scenario
    view_detail_name = 'scenario-result'
    view_update_name = 'scenario-update'
    view_delete_name = 'scenario-delete-modal'

    create_object_data = {'name': 'Test Scenario'}

    @classmethod
    def create_related_objects(cls):
        region = Region.objects.create(name='Test Region')
        return {
            'region': region,
            'catchment': Catchment.objects.create(name='Test Catchment', region=region, parent_region=region)
        }
