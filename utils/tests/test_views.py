from django.test import (TestCase, RequestFactory)
from django.urls import reverse
from django_filters import FilterSet, CharFilter

from .testcases import ViewWithPermissionsTestCase
from ..models import Property, Unit
from ..views import BRITFilterView


class MockFilterSet(FilterSet):
    name = CharFilter(field_name='name', lookup_expr='icontains', initial='Initial property')

    class Meta:
        model = Property
        fields = ['name']


class BRITFilterViewTestCase(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.view = BRITFilterView()
        self.view.filterset_class = MockFilterSet

    def test_initial_filter_values_extraction(self):
        expected_initial_values = {'name': 'Initial property'}
        self.assertEqual(self.view.get_default_filters(), expected_initial_values)

    def test_get_with_empty_query_parameters(self):
        request = self.factory.get('/')
        self.view.request = request
        self.view.kwargs = {}
        response = self.view.get(request)

        self.assertEqual(response.status_code, 302)
        redirect_url = response.url
        self.assertEqual('/?name=Initial+property', redirect_url)

    def test_get_with_query_parameters(self):
        request = self.factory.get('/?name=Other+property')
        self.view.request = request
        self.view.kwargs = {}
        response = self.view.get(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data['filter'].data, {'name': ['Other property']})


class UtilsDashboardViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'view_property'
    url = reverse('utils-dashboard')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={self.url}')

    def test_get_http_403_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)


class UnitListViewTestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        Unit.objects.create(name='Test Unit 1')
        Unit.objects.create(name='Test Unit 2')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('unit-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('unit-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('unit-list'))
        self.assertEqual(response.status_code, 200)


class UnitCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['add_unit']
    url = reverse('unit-create')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={self.url}')

    def test_get_http_403_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        response = self.client.post(self.url, data={'name': 'Test Unit'})
        self.assertRedirects(response, f'{reverse("auth_login")}?next={self.url}')

    def test_post_http_403_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(self.url, data={'name': 'Test Unit'})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_to_detail_view_for_member(self):
        self.client.force_login(self.member)
        response = self.client.post(self.url, data={'name': 'Test Unit'})
        unit = Unit.objects.get(name='Test Unit')
        self.assertRedirects(response, reverse('unit-detail', kwargs={'pk': unit.pk}))


class UnitDetailViewTestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.unit = Unit.objects.create(name='Test Unit')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('unit-detail', kwargs={'pk': self.unit.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('unit-detail', kwargs={'pk': self.unit.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('unit-detail', kwargs={'pk': self.unit.pk}))
        self.assertEqual(response.status_code, 200)


class UnitUpdateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['change_unit']

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.unit = Unit.objects.create(name='Test Unit')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('unit-update', kwargs={'pk': self.unit.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('unit-update', kwargs={'pk': self.unit.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('unit-update', kwargs={'pk': self.unit.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('unit-update', kwargs={'pk': self.unit.pk})
        response = self.client.post(url, data={'name': 'Test Unit'})
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('unit-update', kwargs={'pk': self.unit.pk}), data={'name': 'Test Unit'})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_to_detail_view_for_member(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('unit-update', kwargs={'pk': self.unit.pk}), data={'name': 'Test Unit'})
        self.assertRedirects(response, reverse('unit-detail', kwargs={'pk': self.unit.pk}))


class UnitModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['delete_unit']

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.unit = Unit.objects.create(name='Test Unit')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('unit-delete-modal', kwargs={'pk': self.unit.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('unit-delete-modal', kwargs={'pk': self.unit.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('unit-delete-modal', kwargs={'pk': self.unit.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('unit-delete-modal', kwargs={'pk': self.unit.pk})
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('unit-delete-modal', kwargs={'pk': self.unit.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_to_list_view_for_member(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('unit-delete-modal', kwargs={'pk': self.unit.pk}))
        self.assertRedirects(response, reverse('unit-list'))


class PropertyListViewTestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        Property.objects.create(name='Test Property 1')
        Property.objects.create(name='Test Property 2')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('property-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('property-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('property-list'))
        self.assertEqual(response.status_code, 200)


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


class PropertyDetailViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['view_property']

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.prop = Property.objects.create(name='Test Property')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('property-detail', kwargs={'pk': self.prop.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('property-detail', kwargs={'pk': self.prop.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('property-detail', kwargs={'pk': self.prop.pk}))
        self.assertEqual(response.status_code, 200)


class PropertyUpdateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['change_property']

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.unit = Unit.objects.create(name='Test Unit')
        cls.prop = Property.objects.create(name='Test Property')
        cls.prop.allowed_units.add(cls.unit)

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        response = self.client.get(reverse('property-update', kwargs={'pk': self.prop.pk}))
        self.assertRedirects(response,
                             f'{reverse("auth_login")}?next={reverse("property-update", kwargs={"pk": self.prop.pk})}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('property-update', kwargs={'pk': self.prop.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('property-update', kwargs={'pk': self.prop.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        response = self.client.post(reverse('property-update', kwargs={'pk': self.prop.pk}))
        self.assertRedirects(response,
                             f'{reverse("auth_login")}?next={reverse("property-update", kwargs={"pk": self.prop.pk})}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('property-update', kwargs={'pk': self.prop.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_to_detail_for_member(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('property-update', kwargs={'pk': self.prop.pk}), data={
            'name': 'Updated Property',
            'allowed_units': [self.unit.pk],
        })
        self.assertRedirects(response, reverse('property-detail', kwargs={'pk': self.prop.pk}))
        self.assertEqual(Property.objects.count(), 1)
        self.assertEqual(Property.objects.first().name, 'Updated Property')


class PropertyModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['delete_property']

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.prop = Property.objects.create(name='Test Property')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        response = self.client.get(reverse('property-delete-modal', kwargs={'pk': self.prop.pk}))
        self.assertRedirects(response,
                             f'{reverse("auth_login")}?next={reverse("property-delete-modal", kwargs={"pk": self.prop.pk})}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('property-delete-modal', kwargs={'pk': self.prop.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('property-delete-modal', kwargs={'pk': self.prop.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        response = self.client.post(reverse('property-delete-modal', kwargs={'pk': self.prop.pk}))
        self.assertRedirects(response,
                             f'{reverse("auth_login")}?next={reverse("property-delete-modal", kwargs={"pk": self.prop.pk})}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('property-delete-modal', kwargs={'pk': self.prop.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_to_list_for_member(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('property-delete-modal', kwargs={'pk': self.prop.pk}))
        self.assertRedirects(response, reverse('property-list'))
        self.assertEqual(Property.objects.count(), 0)


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
