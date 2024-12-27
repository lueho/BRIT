from django.urls import reverse

from utils.tests.testcases import AbstractTestCases, ViewWithPermissionsTestCase
from ..models import Property, PropertyUnit


class UnitListViewTestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        PropertyUnit.objects.create(name='Test Unit 1')
        PropertyUnit.objects.create(name='Test Unit 2')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('propertyunit-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('propertyunit-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('propertyunit-list'))
        self.assertEqual(response.status_code, 200)


class UnitCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['add_propertyunit']
    url = reverse('propertyunit-create')

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
        unit = PropertyUnit.objects.get(name='Test Unit')
        self.assertRedirects(response, reverse('propertyunit-detail', kwargs={'pk': unit.pk}))


class UnitCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    model = PropertyUnit
    view_detail_name = 'propertyunit-detail'
    view_update_name = 'propertyunit-update'
    view_delete_name = 'propertyunit-delete-modal'

    create_object_data = {'name': 'Test Unit'}

    @classmethod
    def create_published_object(cls):
        # Change the name of the published object to avoid unique constraint violation
        unit = super().create_published_object()
        unit.name = 'Test Unit 2'
        unit.save()
        return unit


class UnitUpdateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['change_propertyunit']

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.unit = PropertyUnit.objects.create(name='Test Unit', publication_status='published', )

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('propertyunit-update', kwargs={'pk': self.unit.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('propertyunit-update', kwargs={'pk': self.unit.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('propertyunit-update', kwargs={'pk': self.unit.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('propertyunit-update', kwargs={'pk': self.unit.pk})
        response = self.client.post(url, data={'name': 'Test Unit'})
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('propertyunit-update', kwargs={'pk': self.unit.pk}),
                                    data={'name': 'Test Unit'})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_to_detail_view_for_member(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('propertyunit-update', kwargs={'pk': self.unit.pk}),
                                    data={'name': 'Test Unit'})
        self.assertRedirects(response, reverse('propertyunit-detail', kwargs={'pk': self.unit.pk}))


class UnitModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['delete_propertyunit']

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.unit = PropertyUnit.objects.create(name='Test Unit')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('propertyunit-delete-modal', kwargs={'pk': self.unit.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('propertyunit-delete-modal', kwargs={'pk': self.unit.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('propertyunit-delete-modal', kwargs={'pk': self.unit.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('propertyunit-delete-modal', kwargs={'pk': self.unit.pk})
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('propertyunit-delete-modal', kwargs={'pk': self.unit.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_to_list_view_for_member(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('propertyunit-delete-modal', kwargs={'pk': self.unit.pk}))
        self.assertRedirects(response, reverse('propertyunit-list'))


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
        unit = PropertyUnit.objects.create(name='Test Unit')
        response = self.client.post(self.url, data={'name': 'Test Property', 'allowed_units': [unit.pk]})
        prop = Property.objects.get(name='Test Property')
        self.assertRedirects(response, reverse('property-detail', kwargs={'pk': prop.pk}))
        self.assertEqual(Property.objects.count(), 1)
        self.assertEqual(Property.objects.first().name, 'Test Property')


class PropertyCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    model = Property
    view_detail_name = 'property-detail'
    view_update_name = 'property-update'
    view_delete_name = 'property-delete-modal'

    create_object_data = {'name': 'Test Property'}

    @classmethod
    def create_related_objects(cls):
        return {'unit': PropertyUnit.objects.create(name='Test Unit')}


class PropertyUpdateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['change_property']

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.unit = PropertyUnit.objects.create(name='Test Unit')
        cls.prop = Property.objects.create(name='Test Property', publication_status='published', )
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
        allowed_unit_1 = PropertyUnit.objects.create(name='Allowed Unit 1')
        allowed_unit_2 = PropertyUnit.objects.create(name='Allowed Unit 2')
        PropertyUnit.objects.create(name='Not Allowed Unit')
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
        for unit in PropertyUnit.objects.all():
            option = f'<option value="{unit.id}"'
            if unit in self.prop.allowed_units.all():
                self.assertIn(option, options)
            else:
                self.assertNotIn(option, options)
