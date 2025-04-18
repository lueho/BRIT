from django.urls import reverse

from utils.tests.testcases import AbstractTestCases, ViewWithPermissionsTestCase
from ..models import Property, Unit


class UnitCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    model = Unit

    view_dashboard_name = 'properties-dashboard'
    view_create_name = 'unit-create'
    view_published_list_name = 'unit-list'
    view_private_list_name = 'unit-list-owned'
    view_detail_name = 'unit-detail'
    view_update_name = 'unit-update'
    view_delete_name = 'unit-delete-modal'

    create_object_data = {'name': 'Test Unit'}
    update_object_data = {'name': 'Updated Test Unit'}

    @classmethod
    def create_published_object(cls):
        # Change the name of the published object to avoid unique constraint violation
        unit = super().create_published_object()
        unit.name = 'Test Unit 2'
        unit.save()
        return unit


class PropertyCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['add_property']
    url = reverse('property-create')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={self.url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        response = self.client.post(self.url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={self.url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_to_detail_for_member(self):
        self.client.force_login(self.member)
        unit = Unit.objects.create(name='Test Unit')
        response = self.client.post(self.url, data={'name': 'Test Property', 'allowed_units': [unit.pk]})
        prop = Property.objects.get(name='Test Property')
        self.assertRedirects(response, reverse('property-detail', kwargs={'pk': prop.pk}))
        self.assertEqual(Property.objects.count(), 1)
        self.assertEqual(Property.objects.first().name, 'Test Property')


class PropertyCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    model = Property

    view_dashboard_name = 'properties-dashboard'
    view_create_name = 'property-create'
    view_published_list_name = 'property-list'
    view_private_list_name = 'property-list-owned'
    view_detail_name = 'property-detail'
    view_update_name = 'property-update'
    view_delete_name = 'property-delete-modal'

    create_object_data = {'name': 'Test Property'}
    update_object_data = {'name': 'Updated Test Property'}

    @classmethod
    def create_related_objects(cls):
        return {'unit': Unit.objects.create(name='Test Unit')}

    def related_objects_post_data(self):
        data = super().related_objects_post_data()
        data['allowed_units'] = [self.related_objects['unit'].pk]
        return data


class PropertyUnitOptionsViewTestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        allowed_unit_1 = Unit.objects.create(name='Allowed Unit 1')
        allowed_unit_2 = Unit.objects.create(name='Allowed Unit 2')
        Unit.objects.create(name='Not Allowed Unit')
        cls.prop = Property.objects.create(name='Test Property')
        cls.prop.allowed_units.set([allowed_unit_1, allowed_unit_2])

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('property-unit-options', kwargs={'pk': self.prop.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('property-unit-options', kwargs={'pk': self.prop.pk}))
        self.assertEqual(response.status_code, 200)

    def test_response_options_contains_only_allowed_options(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse('property-unit-options', kwargs={'pk': self.prop.pk}))
        self.assertEqual(response.status_code, 200)
        options = response.json()['options']
        for unit in Unit.objects.all():
            option = f'<option value="{unit.id}"'
            if unit in self.prop.allowed_units.all():
                self.assertIn(option, options)
            else:
                self.assertNotIn(option, options)
