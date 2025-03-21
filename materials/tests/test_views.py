from django.urls import reverse

from distributions.models import TemporalDistribution, Timestep
from utils.tests.testcases import AbstractTestCases, ViewWithPermissionsTestCase
from ..models import (Composition, Material, MaterialCategory, MaterialComponent, MaterialComponentGroup,
                      MaterialProperty, MaterialPropertyValue, Sample, SampleSeries, WeightShare)


class MaterialDashboardViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'change_material'

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materials-dashboard')
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materials-dashboard'))
        self.assertEqual(403, response.status_code)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materials-dashboard'))
        self.assertEqual(200, response.status_code)


# ----------- Material Category CRUD -----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MaterialCategoryCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    model = MaterialCategory

    view_published_list_name = 'materialcategory-list'
    view_private_list_name = 'materialcategory-list-owned'
    view_detail_name = 'materialcategory-detail'
    view_update_name = 'materialcategory-update'
    view_delete_name = 'materialcategory-delete-modal'

    create_object_data = {'name': 'Test Category'}
    update_object_data = {'name': 'Updated Test Category'}


class MaterialCategoryListViewTestCase(ViewWithPermissionsTestCase):

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('materialcategory-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcategory-list'))
        self.assertEqual(response.status_code, 200)


class MaterialCategoryCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_materialcategory'

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materialcategory-create')
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcategory-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcategory-create'))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcategory-create'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materialcategory-create')
        response = self.client.post(url, {})
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('materialcategory-create'))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Category'}
        response = self.client.post(reverse('materialcategory-create'), data, follow=True)
        created_pk = list(response.context.get('messages'))[0].message
        self.assertRedirects(response, reverse('materialcategory-detail', kwargs={'pk': created_pk}))


class MaterialCategoryModalCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_materialcategory'

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materialcategory-create-modal')
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcategory-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcategory-create-modal'))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcategory-create-modal'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materialcategory-create-modal')
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('materialcategory-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_to_success_url_for_member(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Category'}
        response = self.client.post(reverse('materialcategory-create-modal'), data)
        self.assertRedirects(
            response, reverse('materialcategory-detail', kwargs={'pk': MaterialCategory.objects.first().pk})
        )


class MaterialCategoryModalDetailViewTestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.category = MaterialCategory.objects.create(name='Test Category')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('materialcategory-detail-modal', kwargs={'pk': self.category.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcategory-detail-modal', kwargs={'pk': self.category.pk}))
        self.assertEqual(response.status_code, 200)


class MaterialCategoryModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'delete_materialcategory'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.category = MaterialCategory.objects.create(name='Test Category')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materialcategory-delete-modal', kwargs={'pk': self.category.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcategory-delete-modal', kwargs={'pk': self.category.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcategory-delete-modal', kwargs={'pk': self.category.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcategory-delete-modal', kwargs={'pk': self.category.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materialcategory-delete-modal', kwargs={'pk': self.category.pk})
        response = self.client.post(url, {})
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('materialcategory-delete-modal', kwargs={'pk': self.category.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_successful_delete_and_http_302_and_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('materialcategory-delete-modal', kwargs={'pk': self.category.pk}))
        self.assertRedirects(response, reverse('materialcategory-list'))
        with self.assertRaises(MaterialCategory.DoesNotExist):
            MaterialCategory.objects.get(pk=self.category.pk)


# ----------- Material CRUD --------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MaterialListViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_material'

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('material-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('material-list'))
        self.assertEqual(response.status_code, 200)

    def test_create_button_available_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('material-list'))
        self.assertContains(response, reverse('material-create'))

    def test_create_button_not_available_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('material-list'))
        self.assertNotContains(response, reverse('material-create'))


class MaterialCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_material'

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('material-create')
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('material-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('material-create'))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('material-create'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('material-create')
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('material-create'))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Material'}
        response = self.client.post(reverse('material-create'), data, follow=True)
        created_pk = list(response.context.get('messages'))[0].message
        self.assertRedirects(response, reverse('material-detail', kwargs={'pk': created_pk}))


class MaterialModalCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_material'

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('material-create-modal')
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('material-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('material-create'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('material-create-modal')
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('material-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Material'}
        response = self.client.post(reverse('material-create-modal'), data, follow=True)
        pk = response.context['object'].id
        self.assertRedirects(response, reverse('material-detail', kwargs={'pk': pk}))


class MaterialCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    model = Material

    view_published_list_name = 'material-list'
    view_private_list_name = 'material-list-owned'
    view_detail_name = 'material-detail'
    view_update_name = 'material-update'
    view_delete_name = 'material-delete-modal'

    create_object_data = {'name': 'Test Material'}
    update_object_data = {'name': 'Updated Test Material'}

    @classmethod
    def create_published_object(cls):
        published_material = super().create_published_object()
        # Change the name in order to prevent unique key constraint violation
        published_material.name = 'Published Test Material'
        published_material.save()
        return published_material


class SourceModalDetailViewTestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.material = Material.objects.create(name='Test Material')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('material-detail-modal', kwargs={'pk': self.material.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('material-detail-modal', kwargs={'pk': self.material.pk}))
        self.assertEqual(response.status_code, 200)


class MaterialModalUpdateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'change_material'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.material = Material.objects.create(name='Test Material', publication_status='published')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('material-update-modal', kwargs={'pk': self.material.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('material-update-modal', kwargs={'pk': self.material.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('material-update-modal', kwargs={'pk': self.material.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('material-update-modal', kwargs={'pk': self.material.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('material-update-modal', kwargs={'pk': self.material.pk})
        response = self.client.post(url, {})
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        data = {'name': 'Updated Test Material'}
        response = self.client.post(reverse('material-update-modal', kwargs={'pk': self.material.pk}), data)
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Update Test Material'}
        response = self.client.post(reverse('material-update-modal', kwargs={'pk': self.material.pk}), data)
        self.assertRedirects(response, reverse('material-detail', kwargs={'pk': self.material.pk}))


class MaterialModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'delete_material'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.material = Material.objects.create(name='Test Material')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('material-delete-modal', kwargs={'pk': self.material.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('material-delete-modal', kwargs={'pk': self.material.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('material-delete-modal', kwargs={'pk': self.material.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('material-delete-modal', kwargs={'pk': self.material.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('material-delete-modal', kwargs={'pk': self.material.pk})
        response = self.client.post(url, {})
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('material-delete-modal', kwargs={'pk': self.material.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('material-delete-modal', kwargs={'pk': self.material.pk}))
        with self.assertRaises(Material.DoesNotExist):
            Material.objects.get(pk=self.material.pk)
        self.assertRedirects(response, reverse('material-list'))


# ----------- Material Component CRUD ----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class ComponentListViewTestCase(ViewWithPermissionsTestCase):

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('materialcomponent-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcomponent-list'))
        self.assertEqual(response.status_code, 200)


class ComponentCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_materialcomponent'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.component = MaterialComponent.objects.create(name='Test Component')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materialcomponent-create')
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcomponent-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcomponent-create'))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcomponent-create'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materialcomponent-create')
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('materialcomponent-create'))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Component'}
        response = self.client.post(reverse('materialcomponent-create'), data, follow=True)
        created_pk = list(response.context.get('messages'))[0].message
        self.assertRedirects(response, reverse('materialcomponent-detail', kwargs={'pk': created_pk}))


class ComponentModalCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_materialcomponent'

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materialcomponent-create-modal')
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcomponent-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcomponent-create-modal'))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcomponent-create-modal'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materialcomponent-create-modal')
        response = self.client.get(url, {})
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('materialcomponent-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Component'}
        response = self.client.post(reverse('materialcomponent-create-modal'), data, follow=True)
        pk = response.context['object'].id
        self.assertRedirects(response, reverse('materialcomponent-detail', kwargs={'pk': pk}))


class MaterialComponentCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    model = MaterialComponent

    view_published_list_name = 'materialcomponent-list'
    view_private_list_name = 'materialcomponent-list-owned'
    view_detail_name = 'materialcomponent-detail'
    view_update_name = 'materialcomponent-update'
    view_delete_name = 'materialcomponent-delete-modal'

    create_object_data = {'name': 'Test Component'}
    update_object_data = {'name': 'Updated Test Component'}

    @classmethod
    def create_published_object(cls):
        published_component = super().create_published_object()
        # Change the name in order to prevent unique key constraint violation
        published_component.name = 'Published Test Component'
        published_component.save()
        return published_component


class ComponentModalDetailViewTestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.component = MaterialComponent.objects.create(name='Test Component')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('materialcomponent-detail-modal', kwargs={'pk': self.component.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcomponent-detail-modal', kwargs={'pk': self.component.pk}))
        self.assertEqual(response.status_code, 200)


class ComponentModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'delete_materialcomponent'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.component = MaterialComponent.objects.create(name='Test Component')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materialcomponent-delete-modal', kwargs={'pk': self.component.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcomponent-delete-modal', kwargs={'pk': self.component.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcomponent-delete-modal', kwargs={'pk': self.component.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcomponent-delete-modal', kwargs={'pk': self.component.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materialcomponent-delete-modal', kwargs={'pk': self.component.pk})
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('materialcomponent-delete-modal', kwargs={'pk': self.component.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('materialcomponent-delete-modal', kwargs={'pk': self.component.pk}))
        with self.assertRaises(MaterialComponent.DoesNotExist):
            MaterialComponent.objects.get(pk=self.component.pk)
        self.assertRedirects(response, reverse('materialcomponent-list'))


# ----------- Material Component Group CRUD ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class ComponentGroupListViewTestCase(ViewWithPermissionsTestCase):

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('materialcomponentgroup-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcomponentgroup-list'))
        self.assertEqual(response.status_code, 200)


class ComponentGroupCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_materialcomponentgroup'

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materialcomponentgroup-create')
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcomponentgroup-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcomponentgroup-create'))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcomponentgroup-create'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materialcomponentgroup-create')
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('materialcomponentgroup-create'))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Group'}
        response = self.client.post(reverse('materialcomponentgroup-create'), data, follow=True)
        created_pk = list(response.context.get('messages'))[0].message
        self.assertRedirects(response, reverse('materialcomponentgroup-detail', kwargs={'pk': created_pk}))


class ComponentGroupModalCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_materialcomponentgroup'

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materialcomponentgroup-create-modal')
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcomponentgroup-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcomponentgroup-create-modal'))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcomponentgroup-create-modal'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materialcomponentgroup-create-modal')
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('materialcomponentgroup-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Group'}
        response = self.client.post(reverse('materialcomponentgroup-create-modal'), data, follow=True)
        pk = response.context['object'].id
        self.assertRedirects(response, reverse('materialcomponentgroup-detail', kwargs={'pk': pk}))


class MaterialComponentGroupCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    model = MaterialComponentGroup

    view_published_list_name = 'materialcomponentgroup-list'
    view_private_list_name = 'materialcomponentgroup-list-owned'
    view_detail_name = 'materialcomponentgroup-detail'
    view_update_name = 'materialcomponentgroup-update'
    view_delete_name = 'materialcomponentgroup-delete-modal'

    create_object_data = {'name': 'Test Group'}
    update_object_data = {'name': 'Updated Test Group'}

    @classmethod
    def create_published_object(cls):
        published_group = super().create_published_object()
        # Change the name in order to prevent unique key constraint violation
        published_group.name = 'Published Test Group'
        published_group.save()
        return published_group


class ComponentGroupModalDetailViewTestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.group = MaterialComponentGroup.objects.create(name='Test Group')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('materialcomponentgroup-detail-modal', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcomponentgroup-detail-modal', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 200)


class ComponentGroupModalUpdateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'change_materialcomponentgroup'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.group = MaterialComponentGroup.objects.create(name='Test Group', publication_status='published', )

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materialcomponentgroup-update-modal', kwargs={'pk': self.group.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcomponentgroup-update-modal', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcomponentgroup-update-modal', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcomponentgroup-update-modal', kwargs={'pk': self.group.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materialcomponentgroup-update-modal', kwargs={'pk': self.group.pk})
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('materialcomponentgroup-update-modal', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Updated Test Group'}
        response = self.client.post(reverse('materialcomponentgroup-update-modal', kwargs={'pk': self.group.pk}), data)
        self.assertRedirects(response, reverse('materialcomponentgroup-detail', kwargs={'pk': self.group.pk}))


class ComponentGroupModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'delete_materialcomponentgroup'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.group = MaterialComponentGroup.objects.create(name='Test Group')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materialcomponentgroup-delete-modal', kwargs={'pk': self.group.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcomponentgroup-delete-modal', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcomponentgroup-delete-modal', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcomponentgroup-delete-modal', kwargs={'pk': self.group.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materialcomponentgroup-delete-modal', kwargs={'pk': self.group.pk})
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('materialcomponentgroup-delete-modal', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('materialcomponentgroup-delete-modal', kwargs={'pk': self.group.pk}))
        with self.assertRaises(MaterialComponentGroup.DoesNotExist):
            MaterialComponentGroup.objects.get(pk=self.group.pk)
        self.assertRedirects(response, reverse('materialcomponentgroup-list'))


# ----------- Material Property CRUD ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MaterialPropertyListViewTestCase(ViewWithPermissionsTestCase):

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('materialproperty-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialproperty-list'))
        self.assertEqual(response.status_code, 200)


class MaterialPropertyCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_materialproperty'

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materialproperty-create')
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialproperty-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialproperty-create'))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialproperty-create'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materialproperty-create')
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('materialcomponentgroup-create'))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Property', 'unit': 'Test Unit'}
        response = self.client.post(reverse('materialproperty-create'), data, follow=True)
        created_pk = list(response.context.get('messages'))[0].message
        self.assertRedirects(response, reverse('materialproperty-detail', kwargs={'pk': created_pk}))


class MaterialPropertyModalCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_materialproperty'

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materialproperty-create-modal')
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialproperty-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialproperty-create-modal'))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialproperty-create-modal'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materialproperty-create-modal')
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('materialproperty-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Property', 'unit': 'Test Unit'}
        response = self.client.post(reverse('materialproperty-create'), data, follow=True)
        created_pk = list(response.context.get('messages'))[0].message
        self.assertRedirects(response, reverse('materialproperty-detail', kwargs={'pk': created_pk}))


class MaterialPropertyCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    model = MaterialProperty

    view_published_list_name = 'materialproperty-list'
    view_private_list_name = 'materialproperty-list-owned'
    view_detail_name = 'materialproperty-detail'
    view_update_name = 'materialproperty-update'
    view_delete_name = 'materialproperty-delete-modal'

    create_object_data = {'name': 'Test Property', 'unit': 'Test Unit'}
    update_object_data = {'name': 'Updated Test Property', 'unit': 'Test Unit'}


class MaterialPropertyModalDetailViewTestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.property = MaterialProperty.objects.create(name='Test Property', unit='Test Unit')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('materialproperty-detail-modal', kwargs={'pk': self.property.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialproperty-detail-modal', kwargs={'pk': self.property.pk}))
        self.assertEqual(response.status_code, 200)


class MaterialPropertyModalUpdateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'change_materialproperty'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.property = MaterialProperty.objects.create(owner=cls.member, name='Test Property', unit='Test Unit')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materialproperty-update-modal', kwargs={'pk': self.property.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialproperty-update-modal', kwargs={'pk': self.property.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialproperty-update-modal', kwargs={'pk': self.property.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialproperty-update-modal', kwargs={'pk': self.property.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materialproperty-update-modal', kwargs={'pk': self.property.pk})
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('materialproperty-update-modal', kwargs={'pk': self.property.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Updated Test Property', 'unit': 'Test Unit'}
        response = self.client.post(reverse('materialproperty-update-modal', kwargs={'pk': self.property.pk}), data)
        self.assertRedirects(response, reverse('materialproperty-detail', kwargs={'pk': self.property.pk}))


class MaterialPropertyModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'delete_materialproperty'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.property = MaterialProperty.objects.create(name='Test Property', unit='Test Unit')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materialproperty-delete-modal', kwargs={'pk': self.property.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialproperty-delete-modal', kwargs={'pk': self.property.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialproperty-delete-modal', kwargs={'pk': self.property.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialproperty-delete-modal', kwargs={'pk': self.property.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('materialproperty-delete-modal', kwargs={'pk': self.property.pk})
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('materialproperty-delete-modal', kwargs={'pk': self.property.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('materialproperty-delete-modal', kwargs={'pk': self.property.pk}))
        with self.assertRaises(MaterialProperty.DoesNotExist):
            MaterialProperty.objects.get(pk=self.property.pk)
        self.assertRedirects(response, reverse('materialproperty-list'))


# ----------- Material Property Value CRUD -----------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MaterialPropertyValueModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'delete_materialpropertyvalue'
    url_name = 'materialpropertyvalue-delete-modal'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        prop = MaterialProperty.objects.create(
            owner=cls.member,
            name='Test Property',
            unit='Test Unit'
        )
        cls.value = MaterialPropertyValue.objects.create(
            owner=cls.member,
            property=prop,
            average=123.312,
            standard_deviation=0.1337
        )

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse(self.url_name, kwargs={'pk': self.value.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse(self.url_name, kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse(self.url_name, kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse(self.url_name, kwargs={'pk': self.value.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse(self.url_name, kwargs={'pk': self.value.pk})
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse(self.url_name, kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse(self.url_name, kwargs={'pk': self.value.pk}))
        with self.assertRaises(MaterialPropertyValue.DoesNotExist):
            MaterialPropertyValue.objects.get(pk=self.value.pk)
        self.assertRedirects(response, reverse('home'))


# ----------- Sample Series CRUD ---------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class SampleSeriesListViewTestCase(ViewWithPermissionsTestCase):

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('sampleseries-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sampleseries-list'))
        self.assertEqual(response.status_code, 200)


class SampleSeriesCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_sampleseries'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.material = Material.objects.create(name='Test Material')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('sampleseries-create')
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sampleseries-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('sampleseries-create'))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('sampleseries-create'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('sampleseries-create')
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('sampleseries-create'))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Series', 'material': self.material.pk}
        response = self.client.post(reverse('sampleseries-create'), data, follow=True)
        created_pk = list(response.context.get('messages'))[0].message
        self.assertRedirects(response, reverse('sampleseries-detail', kwargs={'pk': created_pk}))


class SampleSeriesModalCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_sampleseries'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.material = Material.objects.create(name='Test Material')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('sampleseries-create-modal')
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sampleseries-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('sampleseries-create-modal'))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('sampleseries-create-modal'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('sampleseries-create-modal')
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('sampleseries-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Series', 'material': self.material.pk}
        response = self.client.post(reverse('sampleseries-create-modal'), data, follow=True)
        pk = response.context['object'].id
        self.assertRedirects(response, reverse('sampleseries-detail', kwargs={'pk': pk}))


class SampleSeriesCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    model = SampleSeries

    view_published_list_name = 'sampleseries-list'
    view_private_list_name = 'sampleseries-list-owned'
    view_detail_name = 'sampleseries-detail'
    view_update_name = 'sampleseries-update'
    view_delete_name = 'sampleseries-delete-modal'

    create_object_data = {'name': 'Test Series'}
    update_object_data = {'name': 'Updated Test Series'}

    @classmethod
    def create_related_objects(cls):
        material = Material.objects.create(name='Test Material')
        return {'material': material}


class SampleSeriesModalDetailViewTestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        material = Material.objects.create(name='Test Material')
        cls.series = SampleSeries.objects.create(name='Test Series', material=material)
        composition = Composition.objects.create(
            group=MaterialComponentGroup.objects.create(name='Test Group'),
            sample=Sample.objects.get(series__name='Test Series'),
            fractions_of=MaterialComponent.objects.default()
        )

        temporal_distribution = TemporalDistribution.objects.create(name='Test Distribution')
        Timestep.objects.create(name='Test Timestep', distribution=temporal_distribution)

        for i in range(2):
            component = MaterialComponent.objects.create(
                name=f'Test Component {i}'
            )
            WeightShare.objects.create(
                component=component,
                composition=composition,
                average=0.2,
                standard_deviation=0.01
            )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('sampleseries-detail-modal', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sampleseries-detail-modal', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('sampleseries-detail-modal', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 200)


class SampleSeriesModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'delete_sampleseries'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        material = Material.objects.create(name='Test Material')
        cls.series = SampleSeries.objects.create(name='Test Series', material=material)

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('sampleseries-delete-modal', kwargs={'pk': self.series.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sampleseries-delete-modal', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('sampleseries-delete-modal', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('sampleseries-delete-modal', kwargs={'pk': self.series.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('sampleseries-delete-modal', kwargs={'pk': self.series.pk})
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('sampleseries-delete-modal', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('sampleseries-delete-modal', kwargs={'pk': self.series.pk}))
        with self.assertRaises(SampleSeries.DoesNotExist):
            SampleSeries.objects.get(pk=self.series.pk)
        self.assertRedirects(response, reverse('sampleseries-list'))


# ----------- Sample Series Utilities ----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class SampleSeriesCreateDuplicateViewTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    create_view = False
    public_list_view = False
    private_list_view = False
    detail_view = False
    delete_view = False

    model = SampleSeries

    view_detail_name = 'sampleseries-detail'
    view_update_name = 'sampleseries-duplicate'

    create_object_data = {'name': 'Test Series'}
    update_object_data = {'name': 'Updated Test Series', 'description': 'New Duplicate'}

    @classmethod
    def create_related_objects(cls):
        return {'material': Material.objects.create(name='Test Material')}


# ----------- Sample CRUD ----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class SampleListViewTestCase(ViewWithPermissionsTestCase):

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('sample-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sample-list'))
        self.assertEqual(response.status_code, 200)


class FeaturedSampleListViewTestCase(ViewWithPermissionsTestCase):

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('sample-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sample-list'))
        self.assertEqual(response.status_code, 200)


class SampleCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_sample'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.material = Material.objects.create(name='Test Material')
        cls.series = SampleSeries.objects.create(name='Test Series', material=cls.material)

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('sample-create')
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_200_ok_for_authenticated_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sample-create'))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('sample-create'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('sample-create')
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_success_and_http_302_redirect_for_authenticated_users(self):
        self.client.force_login(self.outsider)
        data = {
            'name': 'Test Sample',
            'material': self.material.pk,
            'series': self.series.pk,
            'timestep': Timestep.objects.default().pk,
        }
        response = self.client.post(reverse('sample-create'), data, follow=True)
        created_pk = Sample.objects.get(name='Test Sample').pk
        self.assertRedirects(response, reverse('sample-detail', kwargs={'pk': created_pk}))


class SampleCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    model = Sample

    view_published_list_name = 'sample-list'
    view_private_list_name = 'sample-list-owned'
    view_detail_name = 'sample-detail'
    view_update_name = 'sample-update'
    view_delete_name = 'sample-delete-modal'

    create_object_data = {'name': 'Test Sample'}
    update_object_data = {'name': 'Updated Test Sample'}

    @classmethod
    def create_related_objects(cls):
        material = Material.objects.create(name='Test Material')
        prop = MaterialProperty.objects.create(name='Test Property', unit='Test Unit')
        MaterialPropertyValue.objects.create(
            name='Test Value',
            property=prop,
            average=123.3,
            standard_deviation=0.13
        )
        return {'material': material}

    @classmethod
    def create_published_object(cls):
        published_sample = super().create_published_object()
        property_value = MaterialPropertyValue.objects.get(name='Test Value')
        published_sample.properties.add(property_value)
        return published_sample

    @classmethod
    def create_unpublished_object(cls):
        unpublished_sample = super().create_unpublished_object()
        property_value = MaterialPropertyValue.objects.get(name='Test Value')
        unpublished_sample.properties.add(property_value)
        return unpublished_sample

    def test_template_contains_edit_and_delete_buttons_for_owners(self):
        self.client.force_login(self.owner_user)
        url = self.get_detail_url(self.published_object.pk)
        response = self.client.get(url)
        self.assertContains(response, self.get_update_url(self.published_object.pk))
        self.assertContains(response, self.get_delete_url(self.published_object.pk))
        self.assertContains(response, reverse('sample-duplicate', kwargs={'pk': self.published_object.pk}))
        self.assertContains(
            response,
            reverse('sample-add-property', kwargs={'pk': self.published_object.pk})
        )
        self.assertContains(
            response,
            reverse('sample-add-composition', kwargs={'pk': self.published_object.pk})
        )

        property_value = MaterialPropertyValue.objects.get(name='Test Value')
        self.assertContains(
            response,
            reverse('materialpropertyvalue-delete-modal', kwargs={'pk': property_value.pk}))
        self.assertContains(response, 'edit-group-')
        self.assertContains(response, reverse('materials-dashboard'))

    def test_template_does_not_contain_edit_and_delete_button_for_non_owner_users(self):
        self.client.force_login(self.non_owner_user)
        url = self.get_detail_url(self.published_object.pk)
        response = self.client.get(url)
        self.assertNotContains(response, self.get_update_url(self.published_object.pk))
        self.assertNotContains(response, self.get_delete_url(self.published_object.pk))
        self.assertNotContains(response, reverse('sample-duplicate', kwargs={'pk': self.published_object.pk}))
        self.assertNotContains(
            response,
            reverse('sample-add-property', kwargs={'pk': self.published_object.pk})
        )
        self.assertNotContains(
            response,
            reverse('sample-add-composition', kwargs={'pk': self.published_object.pk})
        )

        property_value = MaterialPropertyValue.objects.get(name='Test Value')
        self.assertNotContains(
            response,
            reverse('materialpropertyvalue-delete-modal', kwargs={'pk': property_value.pk}))
        self.assertNotContains(response, 'edit-group-')
        self.assertContains(response, reverse('materials-dashboard'))


class SampleUpdateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'change_sample'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.material = Material.objects.create(name='Test Material')
        cls.series = SampleSeries.objects.create(name='Test Series', material=cls.material)
        cls.sample = Sample.objects.create(name='Test Sample', material=cls.material, series=cls.series)

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('sample-update', kwargs={'pk': self.series.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_200_ok_for_owner(self):
        self.client.force_login(self.sample.owner)
        response = self.client.get(reverse('sample-update', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.sample.owner)
        response = self.client.get(reverse('sample-update', kwargs={'pk': self.sample.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('sample-update', kwargs={'pk': self.series.pk})
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_success_and_http_302_redirect_for_owner(self):
        self.client.force_login(self.sample.owner)
        data = {
            'name': 'Updated Test Sample',
            'material': self.material.pk,
            'series': self.series.pk,
            'timestep': Timestep.objects.default().pk,
        }
        response = self.client.post(reverse('sample-update', kwargs={'pk': self.sample.pk}), data)
        self.assertRedirects(response, reverse('sample-detail', kwargs={'pk': self.sample.pk}))


class SampleModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'delete_sample'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        material = Material.objects.create(name='Test Material')
        cls.series = SampleSeries.objects.create(name='Test Series', material=material)
        cls.sample = Sample.objects.create(name='Test Sample', material=material, series=cls.series)

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('sample-delete-modal', kwargs={'pk': self.sample.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sample-delete-modal', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_owners(self):
        self.client.force_login(self.sample.owner)
        response = self.client.get(reverse('sample-delete-modal', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.sample.owner)
        response = self.client.get(reverse('sample-delete-modal', kwargs={'pk': self.sample.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('sample-delete-modal', kwargs={'pk': self.sample.pk})
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('sample-delete-modal', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_owners(self):
        self.client.force_login(self.sample.owner)
        response = self.client.post(reverse('sample-delete-modal', kwargs={'pk': self.sample.pk}))
        with self.assertRaises(Sample.DoesNotExist):
            Sample.objects.get(pk=self.sample.pk)
        self.assertRedirects(response, reverse('sample-list'))


# ----------- Sample utilities -----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class SampleAddPropertyViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_materialpropertyvalue'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        material = Material.objects.create(name='Test Material')
        series = SampleSeries.objects.create(name='Test Series', material=material)
        cls.sample = Sample.objects.create(name='Test Sample', material=material, series=series)
        MaterialProperty.objects.create(name='Test Property', unit='Test Unit')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('sample-add-property', kwargs={'pk': self.sample.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sample-add-property', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_owners(self):
        self.client.force_login(self.sample.owner)
        response = self.client.get(reverse('sample-add-property', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.sample.owner)
        response = self.client.get(reverse('sample-add-property', kwargs={'pk': self.sample.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('sample-add-property', kwargs={'pk': self.sample.pk})
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('sample-add-property', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_owners(self):
        self.client.force_login(self.sample.owner)
        data = {
            'property': MaterialProperty.objects.get(name='Test Property').pk,
            'average': 123.321,
            'standard_deviation': 0.1337,
        }
        response = self.client.post(reverse('sample-add-property', kwargs={'pk': self.sample.pk}), data)
        self.assertRedirects(response, reverse('sample-detail', kwargs={'pk': self.sample.pk}))

    def test_post_creates_value_and_adds_it_to_sample(self):
        self.client.force_login(self.sample.owner)
        data = {
            'property': MaterialProperty.objects.get(name='Test Property').pk,
            'average': 123.321,
            'standard_deviation': 0.1337,
        }
        self.client.post(reverse('sample-add-property', kwargs={'pk': self.sample.pk}), data)
        value = MaterialPropertyValue.objects.get(average=123.321, standard_deviation=0.1337)
        self.assertIn(value, self.sample.properties.all())


class SampleModalAddPropertyViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_materialpropertyvalue'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        material = Material.objects.create(name='Test Material')
        series = SampleSeries.objects.create(owner=cls.owner, name='Test Series', material=material)
        cls.sample = Sample.objects.create(owner=cls.owner, name='Test Sample', material=material, series=series)
        MaterialProperty.objects.create(name='Test Property', unit='Test Unit')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('sample-add-property-modal', kwargs={'pk': self.sample.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sample-add-property-modal', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_owners(self):
        self.client.force_login(self.sample.owner)
        response = self.client.get(reverse('sample-add-property-modal', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.sample.owner)
        response = self.client.get(reverse('sample-add-property-modal', kwargs={'pk': self.sample.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('sample-add-property-modal', kwargs={'pk': self.sample.pk})
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('sample-add-property-modal', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_owners(self):
        self.client.force_login(self.sample.owner)
        data = {
            'property': MaterialProperty.objects.get(name='Test Property').pk,
            'average': 123.321,
            'standard_deviation': 0.1337,
        }
        response = self.client.post(reverse('sample-add-property-modal', kwargs={'pk': self.sample.pk}), data)
        self.assertRedirects(response, reverse('sample-detail', kwargs={'pk': self.sample.pk}))

    def test_post_creates_value_and_adds_it_to_sample(self):
        self.client.force_login(self.sample.owner)
        data = {
            'property': MaterialProperty.objects.get(name='Test Property').pk,
            'average': 123.321,
            'standard_deviation': 0.1337,
        }
        self.client.post(reverse('sample-add-property-modal', kwargs={'pk': self.sample.pk}), data)
        value = MaterialPropertyValue.objects.get(average=123.321, standard_deviation=0.1337)
        self.assertIn(value, self.sample.properties.all())


class SampleCreateDuplicateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_sample'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.material = Material.objects.create(name='Test Material')
        cls.series = SampleSeries.objects.create(name='Test Series', material=cls.material)
        distribution = TemporalDistribution.objects.create(name='Test Distribution')
        timestep = Timestep.objects.create(name='Test Timestep 1', distribution=distribution)
        Timestep.objects.create(name='Test Timestep 2', distribution=distribution)
        cls.sample = Sample.objects.create(name='Test Sample', material=cls.material, series=cls.series,
                                           timestep=timestep)

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('sample-duplicate', kwargs={'pk': self.sample.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_200_ok_for_owner(self):
        self.client.force_login(self.sample.owner)
        response = self.client.get(reverse('sample-duplicate', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.sample.owner)
        response = self.client.get(reverse('sample-duplicate', kwargs={'pk': self.sample.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('sample-duplicate', kwargs={'pk': self.sample.pk})
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_success_and_http_302_redirect_for_owner(self):
        self.client.force_login(self.sample.owner)
        data = {
            'name': 'Test Sample Duplicate',
            'material': self.material.pk,
            'series': self.series.pk,
            'timestep': Timestep.objects.get(name='Test Timestep 2').pk
        }
        response = self.client.post(reverse('sample-duplicate', kwargs={'pk': self.sample.pk}), data, follow=True)
        duplicate = Sample.objects.get(name='Test Sample Duplicate')
        self.assertRedirects(response, reverse('sample-detail', kwargs={'pk': duplicate.pk}))

    def test_newly_created_sample_has_user_as_owner(self):
        self.client.force_login(self.sample.owner)
        data = {
            'name': 'Test Sample Duplicate',
            'material': self.material.pk,
            'series': self.series.pk,
            'timestep': Timestep.objects.get(name='Test Timestep 2').pk
        }
        self.client.post(reverse('sample-duplicate', kwargs={'pk': self.sample.pk}), data)
        self.assertEqual(Sample.objects.get(name='Test Sample Duplicate').owner, self.sample.owner)


# ----------- Composition CRUD -----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CompositionListViewTestCase(ViewWithPermissionsTestCase):

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('composition-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('composition-list'))
        self.assertEqual(response.status_code, 200)


class CompositionCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_composition'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        material = Material.objects.create(name='Test Material')
        series = SampleSeries.objects.create(name='Test Series', material=material)
        cls.sample = Sample.objects.create(
            name='Test Sample',
            material=material,
            series=series,
            publication_status='published',
        )
        cls.custom_group = MaterialComponentGroup.objects.create(name='Test Group')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('composition-create')
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('composition-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('composition-create'))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('composition-create'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('composition-create')
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('composition-create'))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Test Composition',
            'sample': self.sample.pk,
            'group': self.custom_group.pk,
            'fractions_of': MaterialComponent.objects.default().pk,
        }
        response = self.client.post(reverse('composition-create'), data)
        self.assertRedirects(response, reverse('sample-detail', kwargs={'pk': self.sample.pk}))


class CompositionModalCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_composition'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        material = Material.objects.create(name='Test Material')
        series = SampleSeries.objects.create(name='Test Series', material=material)
        cls.sample = Sample.objects.create(owner=cls.member, name='Test Sample', material=material, series=series)
        cls.custom_group = MaterialComponentGroup.objects.create(name='Test Group')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('composition-create-modal')
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('composition-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('composition-create-modal'))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('composition-create-modal'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('composition-create-modal')
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('composition-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Test Composition',
            'sample': self.sample.pk,
            'group': self.custom_group.pk,
            'fractions_of': MaterialComponent.objects.default().pk,
        }
        response = self.client.post(reverse('composition-create-modal'), data)
        self.assertRedirects(response, reverse('sample-detail', kwargs={'pk': self.sample.pk}))


class CompositionCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    model = Composition

    view_published_list_name = 'composition-list'
    view_private_list_name = 'composition-list-owned'
    view_detail_name = 'composition-detail'
    view_update_name = 'composition-update'
    view_delete_name = 'composition-delete-modal'

    create_object_data = {'name': 'Test Composition'}
    update_object_data = {'name': 'Updated Test Composition'}

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.m2m_objects = cls.create_m2m_objects()

    @classmethod
    def create_related_objects(cls):
        material = Material.objects.create(name='Test Material')
        published_sample = Sample.objects.create(
            owner=cls.owner_user,
            name='Published Test Sample',
            material=material,
            publication_status='published',
        )
        unpublished_sample = Sample.objects.create(
            owner=cls.owner_user,
            name='Private Test Sample',
            material=material,
        )
        group = MaterialComponentGroup.objects.create(name='Test Group')
        return {'published_sample': published_sample, 'unpublished_sample': unpublished_sample, 'group': group}

    @classmethod
    def create_published_object(cls):
        data = cls.create_object_data.copy()
        data['publication_status'] = 'published'
        data.update({
            'sample': cls.related_objects['published_sample'],
            'group': cls.related_objects['group']
        })
        return cls.model.objects.create(owner=cls.owner_user, **data)

    @classmethod
    def create_unpublished_object(cls):
        data = cls.create_object_data.copy()
        data['publication_status'] = 'private'
        data.update({
            'sample': cls.related_objects['unpublished_sample'],
            'group': cls.related_objects['group']
        })
        return cls.model.objects.create(owner=cls.owner_user, **data)

    @classmethod
    def create_m2m_objects(cls):
        component_1 = MaterialComponent.objects.create(name='Test Component 1')
        component_2 = MaterialComponent.objects.create(name='Test Component 2')
        unpublished_weight_share_1 = WeightShare.objects.create(
            composition=cls.unpublished_object,
            component=component_1,
            average=0.33,
            standard_deviation=0.01
        )
        unpublished_weight_share_2 = WeightShare.objects.create(
            composition=cls.unpublished_object,
            component=component_1,
            average=0.67,
            standard_deviation=0.01
        )
        published_weight_share_1 = WeightShare.objects.create(
            composition=cls.published_object,
            component=component_1,
            average=0.33,
            standard_deviation=0.01
        )
        published_weight_share_2 = WeightShare.objects.create(
            composition=cls.published_object,
            component=component_1,
            average=0.67,
            standard_deviation=0.01
        )
        return {
            'components': {
                'component_1': component_1,
                'component_2': component_2
            },
            'weight_shares': {
                'unpublished_weight_share_1': unpublished_weight_share_1,
                'unpublished_weight_share_2': unpublished_weight_share_2,
                'published_weight_share_1': published_weight_share_1,
                'published_weight_share_2': published_weight_share_2
            }
        }

    def related_objects_post_data(self):
        return {
            'name': 'Updated Test Composition',
            'sample': self.related_objects['unpublished_sample'].pk,
            'group': self.related_objects['group'].pk,
            'fractions_of': 1,
            'shares-TOTAL_FORMS': 2,
            'shares-INITIAL_FORMS': 2,
            'shares-0-id': self.m2m_objects['weight_shares']['unpublished_weight_share_1'].pk,
            'shares-0-owner': self.related_objects['unpublished_sample'].owner.pk,
            'shares-0-component': self.m2m_objects['components']['component_1'].pk,
            'shares-0-average': 45.5,
            'shares-0-standard_deviation': 1.5,
            'shares-1-id': self.m2m_objects['weight_shares']['unpublished_weight_share_2'].pk,
            'shares-1-owner': self.related_objects['unpublished_sample'].owner.pk,
            'shares-1-component': self.m2m_objects['components']['component_1'].pk,
            'shares-1-average': 54.5,
            'shares-1-standard_deviation': 1.5,
        }

    def get_update_success_url(self, pk=None):
        return reverse('sample-detail', kwargs={'pk': self.related_objects['unpublished_sample'].pk})

    def test_detail_view_published_as_anonymous(self):
        url = self.get_detail_url(self.published_object.pk)
        response = self.client.get(url, follow=True)
        redirect_url = reverse('sample-detail', kwargs={'pk': self.published_object.sample.pk})
        self.assertRedirects(response, redirect_url)

    def test_detail_view_published_as_authenticated_owner(self):
        self.client.force_login(self.owner_user)
        url = self.get_detail_url(self.published_object.pk)
        response = self.client.get(url, follow=True)
        redirect_url = reverse('sample-detail', kwargs={'pk': self.published_object.sample.pk})
        self.assertRedirects(response, redirect_url)

    def test_detail_view_published_as_authenticated_non_owner(self):
        self.client.force_login(self.non_owner_user)
        url = self.get_detail_url(self.published_object.pk)
        response = self.client.get(url, follow=True)
        redirect_url = reverse('sample-detail', kwargs={'pk': self.published_object.sample.pk})
        self.assertRedirects(response, redirect_url)

    def test_detail_view_unpublished_as_owner(self):
        self.client.force_login(self.owner_user)
        url = self.get_detail_url(self.unpublished_object.pk)
        response = self.client.get(url, follow=True)
        redirect_url = reverse('sample-detail', kwargs={'pk': self.unpublished_object.sample.pk})
        self.assertRedirects(response, redirect_url)

    def test_detail_view_unpublished_as_non_owner(self):
        self.client.force_login(self.non_owner_user)
        url = self.get_detail_url(self.unpublished_object.pk)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, self.permission_denied_message, status_code=403)

    def test_detail_view_unpublished_as_anonymous(self):
        url = self.get_detail_url(self.unpublished_object.pk)
        response = self.client.get(url)
        redirect_url = reverse("composition-detail", kwargs={"pk": self.unpublished_object.pk})
        self.assertRedirects(response, f'{reverse("auth_login")}?next={redirect_url}')

    def test_detail_view_nonexistent_object(self):
        url = self.get_detail_url(pk=9999)  # Assuming this PK does not exist
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_deleted_forms_are_not_included_in_total_sum_validation(self):
        self.client.force_login(self.owner_user)
        url = self.get_update_url(self.unpublished_object.pk)
        new_component = MaterialComponent.objects.create(name='New Component')
        data = {
            'name': 'Updated Test Composition',
            'sample': self.related_objects['unpublished_sample'].pk,
            'group': self.related_objects['group'].pk,
            'fractions_of': 1,
            'shares-INITIAL_FORMS': '2',
            'shares-TOTAL_FORMS': '3',
            'shares-0-id': self.m2m_objects['weight_shares']['unpublished_weight_share_1'].pk,
            'shares-0-owner': self.owner_user.pk,
            'shares-0-component': self.m2m_objects['components']['component_1'].pk,
            'shares-0-average': '45.5',
            'shares-0-standard_deviation': '1.5',
            'shares-1-id': self.m2m_objects['weight_shares']['unpublished_weight_share_2'].pk,
            'shares-1-owner': self.owner_user.pk,
            'shares-1-component': self.m2m_objects['components']['component_2'].pk,
            'shares-1-average': '54.5',
            'shares-1-standard_deviation': '1.5',
            'shares-1-DELETE': True,
            'shares-2-id': '',
            'shares-2-owner': self.owner_user.pk,
            'shares-2-component': new_component.pk,
            'shares-2-average': '54.5',
            'shares-2-standard_deviation': '1.5',
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)

    def test_deleted_forms_delete_correct_weight_share_record(self):
        self.client.force_login(self.owner_user)
        url = self.get_update_url(self.unpublished_object.pk)
        data = {
            'name': 'Updated Test Composition',
            'sample': self.related_objects['unpublished_sample'].pk,
            'group': self.related_objects['group'].pk,
            'fractions_of': 1,
            'shares-INITIAL_FORMS': '1',
            'shares-TOTAL_FORMS': '2',
            'shares-0-id': self.m2m_objects['weight_shares']['unpublished_weight_share_1'].pk,
            'shares-0-owner': self.owner_user.pk,
            'shares-0-component': self.m2m_objects['components']['component_1'].pk,
            'shares-0-average': '45.5',
            'shares-0-standard_deviation': '1.5',
            'shares-0-DELETE': True,
            'shares-1-id': self.m2m_objects['weight_shares']['unpublished_weight_share_2'].pk,
            'shares-1-owner': self.owner_user.pk,
            'shares-1-component': self.m2m_objects['components']['component_2'].pk,
            'shares-1-average': '100.0',
            'shares-1-standard_deviation': '1.5',
            'shares-1-DELETE': False,
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        with self.assertRaises(WeightShare.DoesNotExist):
            WeightShare.objects.get(id=self.m2m_objects['weight_shares']['unpublished_weight_share_1'].pk)


class CompositionModalDetailViewTestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        material = Material.objects.create(name='Test Material')
        series = SampleSeries.objects.create(name='Test Series', material=material)
        sample = Sample.objects.create(name='Test Sample', material=material, series=series)
        group = MaterialComponentGroup.objects.create(name='Test Group')
        cls.composition = Composition.objects.create(name='Test Composition', group=group, sample=sample)

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('composition-detail-modal', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('composition-detail-modal', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 200)


class CompositionModalUpdateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ('change_composition', 'change_weightshare')

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        material = Material.objects.create(name='Test Material')
        group = MaterialComponentGroup.objects.create(name='Test Group')
        SampleSeries.objects.create(owner=cls.member, name='Test Series', material=material)
        cls.sample = Sample.objects.get(series__name='Test Series')
        cls.composition = Composition.objects.create(
            group=group,
            sample=Sample.objects.get(series__name='Test Series'),
            fractions_of=MaterialComponent.objects.default()
        )

        for i in range(2):
            component = MaterialComponent.objects.create(name=f'Test Component {i}')
            WeightShare.objects.create(
                component=component,
                composition=cls.composition,
                average=0.2,
                standard_deviation=0.01
            )

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('composition-update-modal', kwargs={'pk': self.composition.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('composition-update-modal', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('composition-update-modal', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertIn('formset', response.context)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('composition-update-modal', kwargs={'pk': self.composition.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('composition-update-modal', kwargs={'pk': self.composition.pk})
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('composition-update-modal', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        components = [c.pk for c in MaterialComponent.objects.exclude(name='Fresh Matter (FM)')]
        shares = [s.pk for s in WeightShare.objects.exclude(component__name='Fresh Matter (FM)')]
        data = {
            'shares-INITIAL_FORMS': '2',
            'shares-TOTAL_FORMS': '2',
            'shares-0-id': f'{shares[0]}',
            'shares-0-owner': f'{self.member.pk}',
            'shares-0-component': f'{components[0]}',
            'shares-0-average': '45.5',
            'shares-0-standard_deviation': '1.5',
            'shares-1-id': f'{shares[1]}',
            'shares-1-owner': f'{self.member.pk}',
            'shares-1-component': f'{components[1]}',
            'shares-1-average': '54.5',
            'shares-1-standard_deviation': '1.5',
        }
        response = self.client.post(reverse('composition-update-modal', kwargs={'pk': self.composition.pk}), data)
        self.assertRedirects(response, reverse('sample-detail', kwargs={'pk': self.sample.pk}))
        self.assertEqual(len(WeightShare.objects.all()), 3)

    def test_deleted_forms_are_not_included_in_total_sum_validation(self):
        self.client.force_login(self.member)
        components = [c.pk for c in MaterialComponent.objects.exclude(name='Fresh Matter (FM)')]
        shares = [s.pk for s in WeightShare.objects.exclude(component__name='Fresh Matter (FM)')]
        new_component = MaterialComponent.objects.create(name='New Component')
        data = {
            'shares-INITIAL_FORMS': '2',
            'shares-TOTAL_FORMS': '3',
            'shares-0-id': f'{shares[0]}',
            'shares-0-owner': f'{self.member.pk}',
            'shares-0-component': f'{components[0]}',
            'shares-0-average': '45.5',
            'shares-0-standard_deviation': '1.5',
            'shares-1-id': f'{shares[1]}',
            'shares-1-owner': f'{self.member.pk}',
            'shares-1-component': f'{components[1]}',
            'shares-1-average': '54.5',
            'shares-1-standard_deviation': '1.5',
            'shares-1-DELETE': True,
            'shares-2-id': '',
            'shares-2-owner': f'{self.member.pk}',
            'shares-2-component': f'{new_component.pk}',
            'shares-2-average': '54.5',
            'shares-2-standard_deviation': '1.5',
        }
        response = self.client.post(reverse('composition-update-modal', kwargs={'pk': self.composition.pk}), data)
        self.assertEqual(response.status_code, 302)

    def test_deleted_forms_delete_correct_weight_share_record(self):
        self.client.force_login(self.member)
        component = MaterialComponent.objects.get(name='Test Component 1')
        share = WeightShare.objects.create(component=component, composition=self.composition)
        data = {
            'shares-INITIAL_FORMS': '1',
            'shares-TOTAL_FORMS': '2',
            'shares-0-id': f'{share.pk}',
            'shares-0-owner': f'{self.member.pk}',
            'shares-0-component': f'{component.pk}',
            'shares-0-average': '45.5',
            'shares-0-standard_deviation': '1.5',
            'shares-0-DELETE': True,
            'shares-1-id': f'{share.pk}',
            'shares-1-owner': f'{self.member.pk}',
            'shares-1-component': f'{component.pk}',
            'shares-1-average': '100.0',
            'shares-1-standard_deviation': '1.5',
            'shares-1-DELETE': False,
        }
        response = self.client.post(reverse('composition-update-modal', kwargs={'pk': self.composition.pk}), data)
        self.assertEqual(response.status_code, 302)
        with self.assertRaises(WeightShare.DoesNotExist):
            WeightShare.objects.get(pk=share.pk)


class CompositionModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ('delete_composition', 'delete_weightshare')

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        material = Material.objects.create(owner=cls.member, name='Test Material')
        cls.component_group = MaterialComponentGroup.objects.create(owner=cls.member, name='Test Group')
        cls.series = SampleSeries.objects.create(owner=cls.member, name='Test Series', material=material)
        cls.default_component = MaterialComponent.objects.default()
        cls.sample = Sample.objects.get(series=cls.series, timestep=Timestep.objects.default())

    def setUp(self):
        self.composition = Composition.objects.create(owner=self.member, sample=self.sample, group=self.component_group)

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('composition-delete-modal', kwargs={'pk': self.composition.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('composition-delete-modal', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('composition-delete-modal', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('composition-delete-modal', kwargs={'pk': self.composition.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('composition-delete-modal', kwargs={'pk': self.composition.pk})
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        data = {'group': self.component_group.pk}
        response = self.client.post(reverse('composition-delete-modal', kwargs={'pk': self.composition.pk}), data)
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_member(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse('composition-delete-modal', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 302)

    def test_post_deletes_correct_composition(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse('composition-delete-modal', kwargs={'pk': self.composition.pk}))
        with self.assertRaises(Composition.DoesNotExist):
            Composition.objects.get(pk=self.composition.pk)
        self.assertRedirects(response, reverse('sample-detail', kwargs={'pk': self.sample.pk}))


# ----------- Composition utilities ------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AddComponentViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_weightshare'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        material = Material.objects.create(name='Test Material')
        cls.component_group = MaterialComponentGroup.objects.create(name='Test Group')
        cls.series = SampleSeries.objects.create(name='Test Series', material=material)
        cls.default_component = MaterialComponent.objects.default()
        cls.sample = Sample.objects.get(
            series=cls.series,
            timestep=Timestep.objects.default(),
        )
        cls.sample.publication_status = 'published'
        cls.sample.save()

    def setUp(self):
        self.composition = Composition.objects.create(
            sample=self.sample,
            group=self.component_group,
            fractions_of=self.default_component
        )
        self.component = MaterialComponent.objects.create(name='Test Component')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('composition-add-component', kwargs={'pk': self.composition.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('composition-add-component', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('composition-add-component', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('composition-add-component', kwargs={'pk': self.composition.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('composition-add-component', kwargs={'pk': self.composition.pk})
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('composition-add-component', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'component': self.component.pk}
        response = self.client.post(reverse('composition-add-component', kwargs={'pk': self.composition.pk}), data)
        self.assertRedirects(response, reverse('sample-detail', kwargs={'pk': self.sample.pk}))

    def test_post_adds_component(self):
        self.client.force_login(self.member)
        data = {'component': self.component.pk}
        self.client.post(reverse('composition-add-component', kwargs={'pk': self.composition.pk}), data)
        self.composition.shares.get(component=self.component)


class ComponentOrderUpViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'change_composition'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        material = Material.objects.create(name='Test Material')
        cls.component_group = MaterialComponentGroup.objects.create(owner=cls.member, name='Test Group')
        cls.series = SampleSeries.objects.create(owner=cls.member, name='Test Series', material=material)
        MaterialComponent.objects.create(name='Test Component')
        cls.default_component = MaterialComponent.objects.default()
        cls.sample = Sample.objects.get(series=cls.series, timestep=Timestep.objects.default())

    def setUp(self):
        self.composition = Composition.objects.create(
            owner=self.member,
            sample=self.sample,
            group=self.component_group,
            fractions_of=self.default_component
        )

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('composition-order-up', kwargs={'pk': self.composition.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('composition-order-up', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_success_and_http_302_redirect_for_owner(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('composition-order-up', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('sample-detail', kwargs={'pk': self.sample.pk}))
        self.assertTemplateUsed('sample-detail.html')


class ComponentOrderDownViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'change_composition'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        material = Material.objects.create(owner=cls.member, name='Test Material')
        cls.component_group = MaterialComponentGroup.objects.create(owner=cls.member, name='Test Group')
        cls.series = SampleSeries.objects.create(owner=cls.member, name='Test Series', material=material)
        cls.default_component = MaterialComponent.objects.default()
        cls.sample = Sample.objects.get(series=cls.series, timestep=Timestep.objects.default())

    def setUp(self):
        self.composition = Composition.objects.create(
            owner=self.member,
            sample=self.sample,
            group=self.component_group,
            fractions_of=self.default_component
        )
        self.component = MaterialComponent.objects.create(owner=self.member, name='Test Component')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('composition-order-down', kwargs={'pk': self.composition.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('composition-order-down', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_success_and_http_302_redirect_for_owner(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('composition-order-down', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('sample-detail', kwargs={'pk': self.sample.pk}))
        self.assertTemplateUsed('sample-detail.html')


# ----------- Weight Share CRUD ----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class WeightShareModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'delete_weightshare'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        material = Material.objects.create(name='Test Material')
        component_group = MaterialComponentGroup.objects.create(name='Test Group')
        SampleSeries.objects.create(owner=cls.member, name='Test Series', material=material)
        cls.sample = Sample.objects.get(series__name='Test Series')
        cls.component = MaterialComponent.objects.create(name='Test Component')
        cls.composition = Composition.objects.create(sample=cls.sample, group=component_group)

    def setUp(self):
        self.share = WeightShare.objects.create(composition=self.composition, component=self.component)

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('weightshare-delete-modal', kwargs={'pk': self.share.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('weightshare-delete-modal', kwargs={'pk': self.share.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('weightshare-delete-modal', kwargs={'pk': self.share.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('weightshare-delete-modal', kwargs={'pk': self.share.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('weightshare-delete-modal', kwargs={'pk': self.share.pk})
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('weightshare-delete-modal', kwargs={'pk': self.share.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('weightshare-delete-modal', kwargs={'pk': self.share.pk}))
        with self.assertRaises(WeightShare.DoesNotExist):
            WeightShare.objects.get(composition=self.composition, component=self.component)
        self.assertRedirects(response, reverse('sample-detail', kwargs={'pk': self.sample.pk}))


# ----------- Materials/Components/Groups Relations --------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AddCompositionViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ('add_composition', 'add_weightshare')

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        material = Material.objects.create(name='Test Material')
        cls.component_group = MaterialComponentGroup.objects.create(name='Test Group')
        cls.series = SampleSeries.objects.create(
            name='Test Series',
            material=material,
            publication_status='published',
        )

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('sampleseries-add-composition', kwargs={'pk': self.series.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sampleseries-add-composition', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('sampleseries-add-composition', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('sampleseries-add-composition', kwargs={'pk': self.series.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('sampleseries-add-composition', kwargs={'pk': self.series.pk})
        response = self.client.post(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('sampleseries-add-composition', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {
            'group': self.component_group.pk,
            'fractions_of': MaterialComponent.objects.default().pk
        }
        response = self.client.post(reverse('sampleseries-add-composition', kwargs={'pk': self.series.pk}), data)
        self.assertRedirects(response, reverse('sampleseries-detail', kwargs={'pk': self.series.pk}))

    def test_post_adds_group_and_weight_shares_to_sample_series(self):
        self.client.force_login(self.member)
        data = {
            'group': self.component_group.pk,
            'fractions_of': MaterialComponent.objects.default().pk
        }
        self.client.post(reverse('sampleseries-add-composition', kwargs={'pk': self.series.pk}), data)
        for sample in self.series.samples.all():
            Composition.objects.get(sample=sample, group=self.component_group)
