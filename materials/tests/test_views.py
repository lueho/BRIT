from django.contrib.auth.models import Group, User, Permission
from django.test import TestCase, modify_settings
from django.urls import reverse

from distributions.models import Timestep, TemporalDistribution
from ..models import Material, MaterialCategory, WeightShare, MaterialComponent, \
    Composition, MaterialComponentGroup, Sample, get_default_owner, SampleSeries, MaterialProperty, \
    MaterialPropertyValue


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialDashboardViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('material-dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('material-dashboard'))
        self.assertEqual(response.status_code, 403)


# ----------- Material Category CRUD -----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialCategoryListViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('materialcategory-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcategory-list'))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialCategoryCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_materialcategory'))
        member.groups.add(members)

    def setUp(self):
        self.member = User.objects.get(username='member')
        self.outsider = User.objects.get(username='outsider')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('materialcategory-create'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcategory-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcategory-create'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('materialcategory-create'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('materialcategory-create'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Category'}
        response = self.client.post(reverse('materialcategory-create'), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialCategoryModalCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_materialcategory'))
        member.groups.add(members)

    def setUp(self):
        self.member = User.objects.get(username='member')
        self.outsider = User.objects.get(username='outsider')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('materialcategory-create-modal'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcategory-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcategory-create-modal'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('materialcategory-create-modal'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('materialcategory-create-modal'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Category'}
        response = self.client.post(reverse('materialcategory-create-modal'), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialCategoryDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.category = MaterialCategory.objects.create(
            owner=self.owner
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('materialcategory-detail', kwargs={'pk': self.category.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcategory-detail', kwargs={'pk': self.category.pk}))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialCategoryModalDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.category = MaterialCategory.objects.create(
            owner=self.owner
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('materialcategory-detail-modal', kwargs={'pk': self.category.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcategory-detail-modal', kwargs={'pk': self.category.pk}))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialCategoryUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='change_materialcategory'))
        member.groups.add(members)

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.category = MaterialCategory.objects.create(
            owner=self.owner,
            name='Test Category'
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('materialcategory-update', kwargs={'pk': self.category.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcategory-update', kwargs={'pk': self.category.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcategory-update', kwargs={'pk': self.category.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('materialcategory-update', kwargs={'pk': self.category.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        data = {'name': 'Updated Test Category'}
        response = self.client.post(reverse('materialcategory-update', kwargs={'pk': self.category.pk}), data=data)
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Updated Test Category'}
        response = self.client.post(reverse('materialcategory-update', kwargs={'pk': self.category.pk}), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialCategoryModalUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='change_materialcategory'))
        member.groups.add(members)

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.category = MaterialCategory.objects.create(
            owner=self.owner,
            name='Test Category'
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('materialcategory-update-modal', kwargs={'pk': self.category.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcategory-update-modal', kwargs={'pk': self.category.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcategory-update-modal', kwargs={'pk': self.category.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('materialcategory-update-modal', kwargs={'pk': self.category.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        data = {'name': 'Updated Test Material'}
        response = self.client.post(
            reverse('materialcategory-update-modal', kwargs={'pk': self.category.pk}),
            data=data
        )
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Update Test Category'}
        response = self.client.post(
            reverse('materialcategory-update-modal', kwargs={'pk': self.category.pk}),
            data=data
        )
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialCategoryModalDeleteViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='delete_materialcategory'))
        member.groups.add(members)

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.category = MaterialCategory.objects.create(
            owner=self.owner
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('materialcategory-delete-modal', kwargs={'pk': self.category.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcategory-delete-modal', kwargs={'pk': self.category.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcategory-delete-modal', kwargs={'pk': self.category.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('materialcategory-delete-modal', kwargs={'pk': self.category.pk}))
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('materialcategory-delete-modal', kwargs={'pk': self.category.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_successful_delete_and_http_302_and_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('materialcategory-delete-modal', kwargs={'pk': self.category.pk}))
        with self.assertRaises(MaterialCategory.DoesNotExist):
            MaterialCategory.objects.get(pk=self.category.pk)
        self.assertEqual(response.status_code, 302)


# ----------- Material CRUD --------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


# CurrentUserMiddleware is used to track object creation and change. It causes errors in the TestCases with
# logins. Can be disabled here because it is not relevant for these tests.
@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialListViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('material-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('material-list'))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_material'))
        member.groups.add(members)

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('material-create'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('material-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('material-create-modal'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('material-create'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('material-create'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Material'}
        response = self.client.post(reverse('material-create'), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialModalCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_material'))
        member.groups.add(members)

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('material-create-modal'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('material-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('material-create-modal'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('material-create-modal'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('material-create-modal'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Material'}
        response = self.client.post(reverse('material-create-modal'), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.material = Material.objects.create(
            owner=self.owner
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('material-detail', kwargs={'pk': self.material.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('material-detail', kwargs={'pk': self.material.pk}))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SourceModalDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.material = Material.objects.create(
            owner=self.owner
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('material-detail-modal', kwargs={'pk': self.material.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('material-detail-modal', kwargs={'pk': self.material.pk}))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='change_material'))
        member.groups.add(members)

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.material = Material.objects.create(
            owner=self.owner,
            name='Test Material'
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('material-update', kwargs={'pk': self.material.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('material-update', kwargs={'pk': self.material.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('material-update', kwargs={'pk': self.material.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('material-update', kwargs={'pk': self.material.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        data = {'name': 'Updated Test Material'}
        response = self.client.post(reverse('material-update', kwargs={'pk': self.material.pk}), data=data)
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Updated Test Material'}
        response = self.client.post(reverse('material-update', kwargs={'pk': self.material.pk}), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialModalUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='change_material'))
        member.groups.add(members)

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.material = Material.objects.create(
            owner=self.owner,
            name='Test Material'
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('material-update-modal', kwargs={'pk': self.material.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('material-update-modal', kwargs={'pk': self.material.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('material-update-modal', kwargs={'pk': self.material.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('material-update-modal', kwargs={'pk': self.material.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        data = {'name': 'Updated Test Material'}
        response = self.client.post(reverse('material-update-modal', kwargs={'pk': self.material.pk}), data=data)
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Update Test Material'}
        response = self.client.post(reverse('material-update-modal', kwargs={'pk': self.material.pk}), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialModalDeleteViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='delete_material'))
        member.groups.add(members)

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.material = Material.objects.create(
            owner=self.owner
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('material-delete-modal', kwargs={'pk': self.material.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('material-delete-modal', kwargs={'pk': self.material.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('material-delete-modal', kwargs={'pk': self.material.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('material-delete-modal', kwargs={'pk': self.material.pk}))
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('material-delete-modal', kwargs={'pk': self.material.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_successful_delete_and_http_302_and_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('material-delete-modal', kwargs={'pk': self.material.pk}))
        with self.assertRaises(Material.DoesNotExist):
            Material.objects.get(pk=self.material.pk)
        self.assertEqual(response.status_code, 302)


# ----------- Material Component CRUD ----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class ComponentListViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('materialcomponent-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcomponent-list'))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class ComponentCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_materialcomponent'))
        member.groups.add(members)

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('materialcomponent-create'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcomponent-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcomponent-create'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('materialcomponent-create'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('materialcomponent-create'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Component'}
        response = self.client.post(reverse('materialcomponent-create'), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class ComponentModalCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_materialcomponent'))
        member.groups.add(members)

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('materialcomponent-create-modal'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcomponent-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcomponent-create-modal'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('materialcomponent-create-modal'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('materialcomponent-create-modal'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Component'}
        response = self.client.post(reverse('materialcomponent-create-modal'), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class ComponentDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        MaterialComponent.objects.create(owner=owner, name='Test Component')

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.component = MaterialComponent.objects.get(name='Test Component')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('materialcomponent-detail', kwargs={'pk': self.component.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcomponent-detail', kwargs={'pk': self.component.pk}))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class ComponentModalDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        MaterialComponent.objects.create(owner=owner, name='Test Component')

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.component = MaterialComponent.objects.get(name='Test Component')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('materialcomponent-detail-modal', kwargs={'pk': self.component.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcomponent-detail-modal', kwargs={'pk': self.component.pk}))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class ComponentUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='change_materialcomponent'))
        member.groups.add(members)

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.component = MaterialComponent.objects.create(
            owner=self.owner,
            name='Test Component'
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('materialcomponent-update', kwargs={'pk': self.component.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcomponent-update', kwargs={'pk': self.component.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcomponent-update', kwargs={'pk': self.component.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('materialcomponent-update', kwargs={'pk': self.component.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        data = {'name': 'Updated Test Component'}
        response = self.client.post(reverse('materialcomponent-update', kwargs={'pk': self.component.pk}), data=data)
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Updated Test Component'}
        response = self.client.post(reverse('materialcomponent-update', kwargs={'pk': self.component.pk}), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class ComponentModalUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='change_materialcomponent'))
        member.groups.add(members)

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.component = MaterialComponent.objects.create(
            owner=self.owner,
            name='Test Component'
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('materialcomponent-update-modal', kwargs={'pk': self.component.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcomponent-update-modal', kwargs={'pk': self.component.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcomponent-update-modal', kwargs={'pk': self.component.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(
            reverse('materialcomponent-update-modal', kwargs={'pk': self.component.pk}),
            data={}
        )
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        data = {'name': 'Updated Test Component'}
        response = self.client.post(
            reverse('materialcomponent-update-modal', kwargs={'pk': self.component.pk}),
            data=data
        )
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Updated Test Component'}
        response = self.client.post(
            reverse('materialcomponent-update-modal', kwargs={'pk': self.component.pk}),
            data=data
        )
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class ComponentModalDeleteViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='delete_materialcomponent'))
        member.groups.add(members)

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.component = MaterialComponent.objects.create(
            owner=self.owner,
            name='Test Component'
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('materialcomponent-delete-modal', kwargs={'pk': self.component.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcomponent-delete-modal', kwargs={'pk': self.component.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcomponent-delete-modal', kwargs={'pk': self.component.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('materialcomponent-delete-modal', kwargs={'pk': self.component.pk}))
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('materialcomponent-delete-modal', kwargs={'pk': self.component.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_successful_delete_and_http_302_and_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('materialcomponent-delete-modal', kwargs={'pk': self.component.pk}))
        with self.assertRaises(MaterialComponent.DoesNotExist):
            MaterialComponent.objects.get(pk=self.component.pk)
        self.assertEqual(response.status_code, 302)


# ----------- Material Component Group CRUD ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class ComponentGroupListViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('materialcomponentgroup-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcomponentgroup-list'))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class ComponentGroupCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_materialcomponentgroup'))
        member.groups.add(members)

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('materialcomponentgroup-create'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcomponentgroup-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcomponentgroup-create'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('materialcomponentgroup-create'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('materialcomponentgroup-create'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Group'}
        response = self.client.post(reverse('materialcomponentgroup-create'), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class ComponentgroupModalCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_materialcomponentgroup'))
        member.groups.add(members)

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('materialcomponentgroup-create-modal'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcomponentgroup-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcomponentgroup-create-modal'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('materialcomponentgroup-create-modal'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('materialcomponentgroup-create-modal'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Group'}
        response = self.client.post(reverse('materialcomponentgroup-create-modal'), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class ComponentGroupDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        MaterialComponentGroup.objects.create(owner=owner, name='Test Group')

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.group = MaterialComponentGroup.objects.get(name='Test Group')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('materialcomponentgroup-detail', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcomponentgroup-detail', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class ComponentGroupModalDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        MaterialComponentGroup.objects.create(owner=owner, name='Test Group')

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.group = MaterialComponentGroup.objects.get(name='Test Group')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('materialcomponentgroup-detail-modal', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcomponentgroup-detail-modal', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class ComponentGroupUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='change_materialcomponentgroup'))
        member.groups.add(members)

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.group = MaterialComponentGroup.objects.create(owner=self.owner, name='Test Group')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('materialcomponentgroup-update', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcomponentgroup-update', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcomponentgroup-update', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('materialcomponentgroup-update', kwargs={'pk': self.group.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        data = {'name': 'Updated Test Group'}
        response = self.client.post(reverse('materialcomponentgroup-update', kwargs={'pk': self.group.pk}), data=data)
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Updated Test Group'}
        response = self.client.post(reverse('materialcomponentgroup-update', kwargs={'pk': self.group.pk}), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class ComponentGroupModalUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='change_materialcomponentgroup'))
        member.groups.add(members)

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.group = MaterialComponentGroup.objects.create(
            owner=self.owner,
            name='Test Group'
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('materialcomponentgroup-update-modal', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcomponentgroup-update-modal', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcomponentgroup-update-modal', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(
            reverse('materialcomponentgroup-update-modal', kwargs={'pk': self.group.pk}),
            data={}
        )
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        data = {'name': 'Updated Test Group'}
        response = self.client.post(
            reverse('materialcomponentgroup-update-modal', kwargs={'pk': self.group.pk}),
            data=data
        )
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Updated Test Group'}
        response = self.client.post(
            reverse('materialcomponentgroup-update-modal', kwargs={'pk': self.group.pk}),
            data=data
        )
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class ComponentGroupModalDeleteViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='delete_materialcomponentgroup'))
        member.groups.add(members)

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.group = MaterialComponentGroup.objects.create(owner=self.owner, name='Test Group')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('materialcomponentgroup-delete-modal', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialcomponentgroup-delete-modal', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialcomponentgroup-delete-modal', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('materialcomponentgroup-delete-modal', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('materialcomponentgroup-delete-modal', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_successful_delete_and_http_302_and_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('materialcomponentgroup-delete-modal', kwargs={'pk': self.group.pk}))
        with self.assertRaises(MaterialComponentGroup.DoesNotExist):
            MaterialComponentGroup.objects.get(pk=self.group.pk)
        self.assertEqual(response.status_code, 302)


# ----------- Material Property CRUD ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialPropertyListViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('materialproperty-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialproperty-list'))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialPropertyCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_materialproperty'))
        member.groups.add(members)

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('materialproperty-create'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialproperty-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialproperty-create'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('materialproperty-create'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('materialcomponentgroup-create'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Property', 'unit': 'Test Unit'}
        response = self.client.post(reverse('materialproperty-create'), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialPropertyModalCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_materialproperty'))
        member.groups.add(members)

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('materialproperty-create-modal'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialproperty-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialproperty-create-modal'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('materialproperty-create-modal'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('materialproperty-create-modal'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Property', 'unit': 'Test Unit'}
        response = self.client.post(reverse('materialproperty-create-modal'), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialPropertyDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        MaterialProperty.objects.create(owner=owner, name='Test Property', unit='Test Unit')

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.property = MaterialProperty.objects.get(name='Test Property')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('materialproperty-detail', kwargs={'pk': self.property.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialproperty-detail', kwargs={'pk': self.property.pk}))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialPropertyModalDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        MaterialProperty.objects.create(owner=owner, name='Test Property', unit='Test Unit')

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.property = MaterialProperty.objects.get(name='Test Property')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('materialproperty-detail-modal', kwargs={'pk': self.property.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialproperty-detail-modal', kwargs={'pk': self.property.pk}))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialPropertyUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='change_materialproperty'))
        member.groups.add(members)

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.property = MaterialProperty.objects.create(owner=self.owner, name='Test Property', unit='Test Unit')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('materialproperty-update', kwargs={'pk': self.property.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialproperty-update', kwargs={'pk': self.property.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialproperty-update', kwargs={'pk': self.property.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('materialproperty-update', kwargs={'pk': self.property.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        data = {'name': 'Updated Test Property'}
        response = self.client.post(reverse('materialproperty-update', kwargs={'pk': self.property.pk}), data=data)
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Updated Test Property', 'unit': 'Test Unit'}
        response = self.client.post(reverse('materialproperty-update', kwargs={'pk': self.property.pk}), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialPropertyModalUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='change_materialproperty'))
        member.groups.add(members)

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.property = MaterialProperty.objects.create(owner=self.owner, name='Test Property', unit='Test Unit')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('materialproperty-update-modal', kwargs={'pk': self.property.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialproperty-update-modal', kwargs={'pk': self.property.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialproperty-update-modal', kwargs={'pk': self.property.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(
            reverse('materialproperty-update-modal', kwargs={'pk': self.property.pk}),
            data={}
        )
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        data = {'name': 'Updated Test Property'}
        response = self.client.post(
            reverse('materialproperty-update-modal', kwargs={'pk': self.property.pk}),
            data=data
        )
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Updated Test Property', 'unit': 'Test Unit'}
        response = self.client.post(
            reverse('materialproperty-update-modal', kwargs={'pk': self.property.pk}),
            data=data
        )
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialPropertyModalDeleteViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='delete_materialproperty'))
        member.groups.add(members)

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.property = MaterialProperty.objects.create(owner=self.owner, name='Test Property', unit='Test Unit')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('materialproperty-delete-modal', kwargs={'pk': self.property.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialproperty-delete-modal', kwargs={'pk': self.property.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialproperty-delete-modal', kwargs={'pk': self.property.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('materialproperty-delete-modal', kwargs={'pk': self.property.pk}))
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('materialproperty-delete-modal', kwargs={'pk': self.property.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_successful_delete_and_http_302_and_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('materialproperty-delete-modal', kwargs={'pk': self.property.pk}))
        with self.assertRaises(MaterialProperty.DoesNotExist):
            MaterialProperty.objects.get(pk=self.property.pk)
        self.assertEqual(response.status_code, 302)


# ----------- Material Property Value CRUD -----------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialPropertyValueModalDeleteViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='delete_materialpropertyvalue'))
        member.groups.add(members)
        MaterialProperty.objects.create(owner=owner, name='Test Property', unit='Test Unit')

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.property = MaterialProperty.objects.get(name='Test Property')
        self.value = MaterialPropertyValue.objects.create(
            owner=self.owner,
            property=self.property,
            average=123.312,
            standard_deviation=0.1337
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('materialpropertyvalue-delete-modal', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('materialpropertyvalue-delete-modal', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('materialpropertyvalue-delete-modal', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('materialpropertyvalue-delete-modal', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('materialpropertyvalue-delete-modal', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_successful_delete_and_http_302_and_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('materialpropertyvalue-delete-modal', kwargs={'pk': self.value.pk}))
        with self.assertRaises(MaterialPropertyValue.DoesNotExist):
            MaterialPropertyValue.objects.get(pk=self.value.pk)
        self.assertEqual(response.status_code, 302)


# ----------- Sample Series CRUD ---------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SampleSeriesListViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('sampleseries-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sampleseries-list'))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SampleSeriesCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_sampleseries'))
        member.groups.add(members)

        Material.objects.create(owner=owner, name='Test Material')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.material = Material.objects.get(name='Test Material')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('sampleseries-create'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sampleseries-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('sampleseries-create'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('sampleseries-create'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('sampleseries-create'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Test Series',
            'material': self.material.id,
        }
        response = self.client.post(reverse('sampleseries-create'), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SampleModalCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_sample'))
        member.groups.add(members)

        Material.objects.create(owner=owner, name='Test Material')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.material = Material.objects.get(name='Test Material')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('sampleseries-create-modal'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sampleseries-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('sampleseries-create-modal'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('sampleseries-create-modal'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('sampleseries-create-modal'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Test Series',
            'material': self.material.id,
        }
        response = self.client.post(reverse('sampleseries-create-modal'), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SampleSeriesDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='view_sampleseries'))
        members.permissions.add(Permission.objects.get(codename='view_sampleseries'))
        member.groups.add(members)

        material = Material.objects.create(
            owner=owner,
            name='Test Material'
        )

        group = MaterialComponentGroup.objects.create(
            owner=owner,
            name='Test Group'
        )

        SampleSeries.objects.create(
            owner=owner,
            material=material,
            name='Test Series'
        )

        composition = Composition.objects.create(
            owner=owner,
            group=group,
            sample=Sample.objects.get(series__name='Test Series'),
            fractions_of=MaterialComponent.objects.default()
        )

        temporal_distribution = TemporalDistribution.objects.create(
            owner=owner,
            name='Test Distribution'
        )

        Timestep.objects.create(
            owner=owner,
            name='Test Timestep',
            distribution=temporal_distribution
        )

        for i in range(2):
            component = MaterialComponent.objects.create(
                owner=owner,
                name=f'Test Component {i}'
            )
            WeightShare.objects.create(
                owner=owner,
                component=component,
                composition=composition,
                average=0.2,
                standard_deviation=0.01
            )

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.composition = Composition.objects.get(
            group__name='Test Group'
        )
        self.material = Material.objects.get(
            owner=self.owner,
            name='Test Material'
        )
        self.series = SampleSeries.objects.get(name='Test Series')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('sampleseries-detail', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sampleseries-detail', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('sampleseries-detail', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SampleSeriesModalDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='view_sampleseries'))
        members.permissions.add(Permission.objects.get(codename='view_sampleseries'))
        member.groups.add(members)

        material = Material.objects.create(
            owner=owner,
            name='Test Material'
        )

        group = MaterialComponentGroup.objects.create(
            owner=owner,
            name='Test Group'
        )

        SampleSeries.objects.create(
            owner=owner,
            material=material,
            name='Test Series'
        )

        composition = Composition.objects.create(
            owner=owner,
            group=group,
            sample=Sample.objects.get(series__name='Test Series'),
            fractions_of=MaterialComponent.objects.default()
        )

        temporal_distribution = TemporalDistribution.objects.create(
            owner=owner,
            name='Test Distribution'
        )

        Timestep.objects.create(
            owner=owner,
            name='Test Timestep',
            distribution=temporal_distribution
        )

        for i in range(2):
            component = MaterialComponent.objects.create(
                owner=owner,
                name=f'Test Component {i}'
            )
            WeightShare.objects.create(
                owner=owner,
                component=component,
                composition=composition,
                average=0.2,
                standard_deviation=0.01
            )

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.composition = Composition.objects.get(
            group__name='Test Group'
        )
        self.material = Material.objects.get(
            owner=self.owner,
            name='Test Material'
        )
        self.series = SampleSeries.objects.get(name='Test Series')

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


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SampleSeriesUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='change_sampleseries'))
        member.groups.add(members)

        material = Material.objects.create(owner=owner, name='Test Material')
        SampleSeries.objects.create(owner=owner, name='Test Series', material=material)

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.material = Material.objects.get(name='Test Material')
        self.series = SampleSeries.objects.get(name='Test Series')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('sampleseries-update', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sampleseries-update', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('sampleseries-update', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('sampleseries-update', kwargs={'pk': self.series.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('sampleseries-update', kwargs={'pk': self.series.pk}), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Updated Test Series',
            'material': self.material.id,
        }
        response = self.client.post(reverse('sampleseries-update', kwargs={'pk': self.series.pk}), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SampleSeriesModalUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='change_sampleseries'))
        member.groups.add(members)

        material = Material.objects.create(owner=owner, name='Test Material')
        SampleSeries.objects.create(owner=owner, name='Test Series', material=material)

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.series = SampleSeries.objects.get(name='Test Series')
        self.material = Material.objects.get(name='Test Material')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('sampleseries-update-modal', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sampleseries-update-modal', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('sampleseries-update-modal', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(
            reverse('sampleseries-update-modal', kwargs={'pk': self.series.pk}),
            data={}
        )
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('sampleseries-update-modal', kwargs={'pk': self.series.pk}), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Updated Test Series',
            'material': self.material.id,
        }
        response = self.client.post(
            reverse('sampleseries-update-modal', kwargs={'pk': self.series.pk}),
            data=data
        )
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SampleSeriesModalDeleteViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='delete_sampleseries'))
        member.groups.add(members)

        Material.objects.create(owner=owner, name='Test Material')

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.material = Material.objects.get(name='Test Material')
        self.series = SampleSeries.objects.create(owner=self.owner, name='Test Series', material=self.material)

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('sampleseries-delete-modal', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sampleseries-delete-modal', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('sampleseries-delete-modal', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('sampleseries-delete-modal', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('sampleseries-delete-modal', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_successful_delete_and_http_302_and_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('sampleseries-delete-modal', kwargs={'pk': self.series.pk}))
        with self.assertRaises(SampleSeries.DoesNotExist):
            SampleSeries.objects.get(pk=self.series.pk)
        self.assertEqual(response.status_code, 302)


# ----------- Sample Series Utilities ----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SampleSeriesCreateDuplicateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_sampleseries'))
        member.groups.add(members)

        material = Material.objects.create(owner=owner, name='Test Material')
        series = SampleSeries.objects.create(owner=owner, name='Test Series', material=material)

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.material = Material.objects.get(name='Test Material')
        self.series = SampleSeries.objects.get(name='Test Series')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('sampleseries-duplicate', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sampleseries-duplicate', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('sampleseries-duplicate', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('sampleseries-duplicate', kwargs={'pk': self.series.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('sampleseries-duplicate', kwargs={'pk': self.series.pk}), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Test Series Duplicate',
            'material': self.material.id,
        }
        response = self.client.post(reverse('sampleseries-duplicate', kwargs={'pk': self.series.pk}), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SampleSeriesModalCreateDuplicateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_sampleseries'))
        member.groups.add(members)

        material = Material.objects.create(owner=owner, name='Test Material')
        series = SampleSeries.objects.create(owner=owner, name='Test Series', material=material)

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.material = Material.objects.get(name='Test Material')
        self.series = SampleSeries.objects.get(name='Test Series')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('sampleseries-duplicate-modal', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sampleseries-duplicate-modal', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('sampleseries-duplicate-modal', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('sampleseries-duplicate-modal', kwargs={'pk': self.series.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('sampleseries-duplicate-modal', kwargs={'pk': self.series.pk}), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Test Series Duplicate',
            'material': self.material.id,
        }
        response = self.client.post(reverse('sampleseries-duplicate-modal', kwargs={'pk': self.series.pk}), data=data)
        self.assertEqual(response.status_code, 302)


# ----------- Sample CRUD ----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SampleListViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('sample-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sample-list'))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class FeaturedSampleListViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('sample-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sample-list'))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SampleCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_sample'))
        member.groups.add(members)

        material = Material.objects.create(owner=owner, name='Test Material')
        SampleSeries.objects.create(owner=owner, name='Test Series', material=material)

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.series = SampleSeries.objects.get(name='Test Series')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('sample-create'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sample-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('sample-create'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('sample-create'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('sample-create'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Test Sample',
            'series': self.series.id,
            'timestep': Timestep.objects.default().id,
        }
        response = self.client.post(reverse('sample-create'), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SampleModalCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_sample'))
        member.groups.add(members)

        material = Material.objects.create(owner=owner, name='Test Material')
        SampleSeries.objects.create(owner=owner, name='Test Series', material=material)

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.series = SampleSeries.objects.get(name='Test Series')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('sample-create-modal'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sample-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('sample-create-modal'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('sample-create-modal'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('sample-create-modal'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Test Sample',
            'series': self.series.id,
            'timestep': Timestep.objects.default().id,
        }
        response = self.client.post(reverse('sample-create-modal'), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SampleDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        material = Material.objects.create(owner=owner, name='Test Material')
        series = SampleSeries.objects.create(owner=owner, name='Test Series', material=material)
        Sample.objects.create(owner=owner, name='Test Sample', series=series)

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.sample = Sample.objects.get(name='Test Sample')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('sample-detail', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sample-detail', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SampleModalDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        material = Material.objects.create(owner=owner, name='Test Material')
        series = SampleSeries.objects.create(owner=owner, name='Test Series', material=material)
        Sample.objects.create(owner=owner, name='Test Sample', series=series)

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.sample = Sample.objects.get(name='Test Sample')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('sample-detail-modal', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sample-detail-modal', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SampleUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='change_sample'))
        member.groups.add(members)

        material = Material.objects.create(owner=owner, name='Test Material')
        SampleSeries.objects.create(owner=owner, name='Test Series', material=material)

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.series = SampleSeries.objects.get(name='Test Series')
        self.sample = Sample.objects.create(owner=self.owner, name='Test Sample', series=self.series)

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('sample-update', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sample-update', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('sample-update', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('sample-update', kwargs={'pk': self.sample.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('sample-update', kwargs={'pk': self.sample.pk}), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Test Sample',
            'series': self.series.id,
            'timestep': Timestep.objects.default().id,
        }
        response = self.client.post(reverse('sample-update', kwargs={'pk': self.sample.pk}), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SampleModalUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='change_sample'))
        member.groups.add(members)

        material = Material.objects.create(owner=owner, name='Test Material')
        SampleSeries.objects.create(owner=owner, name='Test Series', material=material)

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.series = SampleSeries.objects.get(name='Test Series')
        self.sample = Sample.objects.create(owner=self.owner, name='Test Sample', series=self.series)

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('sample-update-modal', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sample-update-modal', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('sample-update-modal', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(
            reverse('sample-update-modal', kwargs={'pk': self.sample.pk}),
            data={}
        )
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('sample-update-modal', kwargs={'pk': self.sample.pk}), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Test Sample',
            'series': self.series.id,
            'timestep': Timestep.objects.default().id,
        }
        response = self.client.post(
            reverse('sample-update-modal', kwargs={'pk': self.sample.pk}),
            data=data
        )
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SampleModalDeleteViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='delete_sample'))
        member.groups.add(members)
        material = Material.objects.create(owner=owner, name='Test Material')
        SampleSeries.objects.create(owner=owner, name='Test Series', material=material)

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.series = SampleSeries.objects.get(name='Test Series')
        self.sample = Sample.objects.create(owner=self.owner, name='Test Sample', series=self.series)

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('sample-delete-modal', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sample-delete-modal', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('sample-delete-modal', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('sample-delete-modal', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('sample-delete-modal', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_successful_delete_and_http_302_and_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('sample-delete-modal', kwargs={'pk': self.sample.pk}))
        with self.assertRaises(Sample.DoesNotExist):
            Sample.objects.get(pk=self.sample.pk)
        self.assertEqual(response.status_code, 302)


# ----------- Sample utilities -----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SampleAddPropertyViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_materialpropertyvalue'))
        member.groups.add(members)
        material = Material.objects.create(owner=owner, name='Test Material')
        series = SampleSeries.objects.create(owner=owner, name='Test Series', material=material)
        Sample.objects.create(owner=owner, name='Test Sample', series=series)
        MaterialProperty.objects.create(owner=owner, name='Test Property', unit='Test Unit')

    def setUp(self):
        self.member = User.objects.get(username='member')
        self.outsider = User.objects.get(username='outsider')
        self.sample = Sample.objects.get(name='Test Sample')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('sample-add-property', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sample-add-property', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('sample-add-property', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('sample-add-property', kwargs={'pk': self.sample.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('sample-add-property', kwargs={'pk': self.sample.pk}), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {
            'property': MaterialProperty.objects.get(name='Test Property').id,
            'average': 123.321,
            'standard_deviation': 0.1337,
        }
        response = self.client.post(reverse('sample-add-property', kwargs={'pk': self.sample.pk}), data=data)
        self.assertEqual(response.status_code, 302)

    def test_post_creates_value_and_adds_it_to_sample(self):
        self.client.force_login(self.member)
        data = {
            'property': MaterialProperty.objects.get(name='Test Property').id,
            'average': 123.321,
            'standard_deviation': 0.1337,
        }
        response = self.client.post(reverse('sample-add-property', kwargs={'pk': self.sample.pk}), data=data)
        self.assertEqual(response.status_code, 302)
        value = MaterialPropertyValue.objects.get(average=123.321, standard_deviation=0.1337)
        self.assertIn(value, self.sample.properties.all())


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SampleModalAddPropertyViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_materialpropertyvalue'))
        member.groups.add(members)
        material = Material.objects.create(owner=owner, name='Test Material')
        series = SampleSeries.objects.create(owner=owner, name='Test Series', material=material)
        Sample.objects.create(owner=owner, name='Test Sample', series=series)
        MaterialProperty.objects.create(owner=owner, name='Test Property', unit='Test Unit')

    def setUp(self):
        self.member = User.objects.get(username='member')
        self.outsider = User.objects.get(username='outsider')
        self.sample = Sample.objects.get(name='Test Sample')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('sample-add-property-modal', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sample-add-property-modal', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('sample-add-property-modal', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('sample-add-property-modal', kwargs={'pk': self.sample.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('sample-add-property-modal', kwargs={'pk': self.sample.pk}), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {
            'property': MaterialProperty.objects.get(name='Test Property').id,
            'average': 123.321,
            'standard_deviation': 0.1337,
        }
        response = self.client.post(reverse('sample-add-property-modal', kwargs={'pk': self.sample.pk}), data=data)
        self.assertEqual(response.status_code, 302)

    def test_post_creates_value_and_adds_it_to_sample(self):
        self.client.force_login(self.member)
        data = {
            'property': MaterialProperty.objects.get(name='Test Property').id,
            'average': 123.321,
            'standard_deviation': 0.1337,
        }
        response = self.client.post(reverse('sample-add-property-modal', kwargs={'pk': self.sample.pk}), data=data)
        self.assertEqual(response.status_code, 302)
        value = MaterialPropertyValue.objects.get(average=123.321, standard_deviation=0.1337)
        self.assertIn(value, self.sample.properties.all())


# ----------- Composition CRUD -----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class CompositionListViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('composition-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('composition-list'))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class CompositionCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_composition'))
        member.groups.add(members)

        material = Material.objects.create(owner=owner, name='Test Material')
        series = SampleSeries.objects.create(owner=owner, name='Test Series', material=material)
        Sample.objects.create(owner=owner, name='Test Sample', series=series)
        MaterialComponentGroup.objects.create(owner=owner, name='Test Group')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.series = SampleSeries.objects.get(name='Test Series')
        self.sample = Sample.objects.get(name='Test Sample')
        self.custom_group = MaterialComponentGroup.objects.get(name='Test Group')
        self.default_component = MaterialComponent.objects.default()

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('composition-create'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('composition-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('composition-create'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('composition-create'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('composition-create'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Test Composition',
            'sample': self.sample.id,
            'group': self.custom_group.id,
            'fractions_of': self.default_component.id,
        }
        response = self.client.post(reverse('composition-create'), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class CompositionModalCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_composition'))
        member.groups.add(members)

        material = Material.objects.create(owner=owner, name='Test Material')
        series = SampleSeries.objects.create(owner=owner, name='Test Series', material=material)
        Sample.objects.create(owner=owner, name='Test Sample', series=series)
        MaterialComponentGroup.objects.create(owner=owner, name='Test Group')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.series = SampleSeries.objects.get(name='Test Series')
        self.sample = Sample.objects.get(name='Test Sample')
        self.custom_group = MaterialComponentGroup.objects.get(name='Test Group')
        self.default_component = MaterialComponent.objects.default()

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('composition-create-modal'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('composition-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('composition-create-modal'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('composition-create-modal'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('composition-create-modal'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Test Composition',
            'sample': self.sample.id,
            'group': self.custom_group.id,
            'fractions_of': self.default_component.id,
        }
        response = self.client.post(reverse('composition-create-modal'), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class CompositionDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        material = Material.objects.create(owner=owner, name='Test Material')
        series = SampleSeries.objects.create(owner=owner, name='Test Series', material=material)
        sample = Sample.objects.create(owner=owner, name='Test Sample', series=series)
        group = MaterialComponentGroup.objects.create(owner=owner, name='Test Group')
        Composition.objects.create(owner=owner, name='Test Composition', group=group, sample=sample)

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.composition = Composition.objects.get(name='Test Composition')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('composition-detail', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('composition-detail', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class CompositionModalDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        material = Material.objects.create(owner=owner, name='Test Material')
        series = SampleSeries.objects.create(owner=owner, name='Test Series', material=material)
        sample = Sample.objects.create(owner=owner, name='Test Sample', series=series)
        group = MaterialComponentGroup.objects.create(owner=owner, name='Test Group')
        Composition.objects.create(owner=owner, name='Test Composition', group=group, sample=sample)

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.composition = Composition.objects.get(name='Test Composition')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('composition-detail-modal', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('composition-detail-modal', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class CompositionUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='change_composition'))
        members.permissions.add(Permission.objects.get(codename='change_weightshare'))
        member.groups.add(members)

        material = Material.objects.create(
            owner=owner,
            name='Test Material'
        )

        group = MaterialComponentGroup.objects.create(
            owner=owner,
            name='Test Group'
        )

        SampleSeries.objects.create(
            owner=owner,
            material=material,
            name='Test Series'
        )

        composition = Composition.objects.create(
            owner=owner,
            group=group,
            sample=Sample.objects.get(series__name='Test Series'),
            fractions_of=MaterialComponent.objects.default()
        )

        for i in range(2):
            component = MaterialComponent.objects.create(
                owner=owner,
                name=f'Test Component {i}'
            )
            WeightShare.objects.create(
                owner=owner,
                component=component,
                composition=composition,
                average=0.2,
                standard_deviation=0.01
            )

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.composition = Composition.objects.get(
            group__name='Test Group'
        )
        self.material = Material.objects.get(
            owner=self.owner,
            name='Test Material'
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('composition-update', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('composition-update', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('composition-update', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertIn('formset', response.context)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(
            reverse('composition-update', kwargs={'pk': self.composition.pk}),
            data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(
            reverse('composition-update', kwargs={'pk': self.composition.pk}),
            data={}
        )
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        components = [c.id for c in MaterialComponent.objects.exclude(name='Fresh Matter (FM)')]
        shares = [s.id for s in WeightShare.objects.exclude(
            component__name='Fresh Matter (FM)'
        )]
        data = {
            'shares-INITIAL_FORMS': '2',
            'shares-TOTAL_FORMS': '2',
            'shares-0-id': f'{shares[0]}',
            'shares-0-component': f'{components[0]}',
            'shares-0-average': '45.5',
            'shares-0-standard_deviation': '1.5',
            'shares-1-id': f'{shares[1]}',
            'shares-1-component': f'{components[1]}',
            'shares-1-average': '54.5',
            'shares-1-standard_deviation': '1.5',
        }
        response = self.client.post(
            reverse('composition-update', kwargs={'pk': self.composition.pk}),
            data=data
        )
        self.assertEqual(response.status_code, 302)

    def test_post_http_302_redirect_for_members_with_correct_data(self):
        self.client.force_login(self.member)
        components = [c.id for c in MaterialComponent.objects.exclude(name='Fresh Matter (FM)')]
        shares = [s.id for s in WeightShare.objects.exclude(
            component__name='Fresh Matter (FM)'
        )]
        data = {
            'shares-INITIAL_FORMS': '2',
            'shares-TOTAL_FORMS': '2',
            'shares-0-id': f'{shares[0]}',
            'shares-0-component': f'{components[0]}',
            'shares-0-average': '45.5',
            'shares-0-standard_deviation': '1.5',
            'shares-1-id': f'{shares[1]}',
            'shares-1-component': f'{components[1]}',
            'shares-1-average': '54.5',
            'shares-1-standard_deviation': '1.5',
        }
        response = self.client.post(
            reverse('composition-update', kwargs={'pk': self.composition.pk}),
            data=data
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(WeightShare.objects.all()), 3)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class CompositionModalUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='change_composition'))
        members.permissions.add(Permission.objects.get(codename='change_weightshare'))
        member.groups.add(members)

        material = Material.objects.create(
            owner=owner,
            name='Test Material'
        )

        group = MaterialComponentGroup.objects.create(
            owner=owner,
            name='Test Group'
        )

        SampleSeries.objects.create(
            owner=owner,
            material=material,
            name='Test Series'
        )

        composition = Composition.objects.create(
            owner=owner,
            group=group,
            sample=Sample.objects.get(series__name='Test Series'),
            fractions_of=MaterialComponent.objects.default()
        )

        for i in range(2):
            component = MaterialComponent.objects.create(
                owner=owner,
                name=f'Test Component {i}'
            )
            WeightShare.objects.create(
                owner=owner,
                component=component,
                composition=composition,
                average=0.2,
                standard_deviation=0.01
            )

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.composition = Composition.objects.get(
            group__name='Test Group'
        )
        self.material = Material.objects.get(
            owner=self.owner,
            name='Test Material'
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('composition-update-modal', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 302)

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

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(
            reverse('composition-update-modal', kwargs={'pk': self.composition.pk}),
            data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(
            reverse('composition-update-modal', kwargs={'pk': self.composition.pk}),
            data={}
        )
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        components = [c.id for c in MaterialComponent.objects.exclude(name='Fresh Matter (FM)')]
        shares = [s.id for s in WeightShare.objects.exclude(
            component__name='Fresh Matter (FM)'
        )]
        data = {
            'shares-INITIAL_FORMS': '2',
            'shares-TOTAL_FORMS': '2',
            'shares-0-id': f'{shares[0]}',
            'shares-0-component': f'{components[0]}',
            'shares-0-average': '45.5',
            'shares-0-standard_deviation': '1.5',
            'shares-1-id': f'{shares[1]}',
            'shares-1-component': f'{components[1]}',
            'shares-1-average': '54.5',
            'shares-1-standard_deviation': '1.5',
        }
        response = self.client.post(
            reverse('composition-update-modal', kwargs={'pk': self.composition.pk}),
            data=data
        )
        self.assertEqual(response.status_code, 302)

    def test_post_http_302_redirect_for_members_with_correct_data(self):
        self.client.force_login(self.member)
        components = [c.id for c in MaterialComponent.objects.exclude(name='Fresh Matter (FM)')]
        shares = [s.id for s in WeightShare.objects.exclude(
            component__name='Fresh Matter (FM)'
        )]
        data = {
            'shares-INITIAL_FORMS': '2',
            'shares-TOTAL_FORMS': '2',
            'shares-0-id': f'{shares[0]}',
            'shares-0-component': f'{components[0]}',
            'shares-0-average': '45.5',
            'shares-0-standard_deviation': '1.5',
            'shares-1-id': f'{shares[1]}',
            'shares-1-component': f'{components[1]}',
            'shares-1-average': '54.5',
            'shares-1-standard_deviation': '1.5',
        }
        response = self.client.post(
            reverse('composition-update-modal', kwargs={'pk': self.composition.pk}),
            data=data
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(WeightShare.objects.all()), 3)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class CompositionModalDeleteViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='delete_composition'))
        members.permissions.add(Permission.objects.get(codename='delete_weightshare'))
        member.groups.add(members)

        material = Material.objects.create(
            owner=owner,
            name='Test Material'
        )
        MaterialComponentGroup.objects.create(
            owner=owner,
            name='Test Group'
        )
        SampleSeries.objects.create(
            owner=owner,
            material=material,
            name='Test Series'
        )

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.series = SampleSeries.objects.get(name='Test Series')
        self.component_group = MaterialComponentGroup.objects.get(name='Test Group')
        self.default_component = MaterialComponent.objects.default()
        self.sample = Sample.objects.get(series=self.series, timestep=Timestep.objects.default())
        self.composition = Composition.objects.create(
            owner=self.owner,
            sample=self.sample,
            group=self.component_group
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('composition-delete-modal', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('composition-delete-modal', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('composition-delete-modal', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(
            reverse('composition-delete-modal', kwargs={'pk': self.composition.pk}
                    ),
            data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        data = {
            'group': self.component_group.id,
        }
        response = self.client.post(
            reverse('composition-delete-modal', kwargs={'pk': self.composition.pk}),
            data=data
        )
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_member(self):
        self.client.force_login(self.member)
        data = {
            'group': self.component_group.id,
        }
        response = self.client.post(
            reverse('composition-delete-modal', kwargs={'pk': self.composition.pk}),
            data=data)
        self.assertEqual(response.status_code, 302)

    def test_post_deletes_correct_composition(self):
        self.client.force_login(self.member)
        data = {
            'group': self.component_group.id,
        }
        response = self.client.post(
            reverse('composition-delete-modal', kwargs={'pk': self.composition.pk}),
            data=data)
        self.assertEqual(response.status_code, 302)
        with self.assertRaises(Composition.DoesNotExist):
            Composition.objects.get(id=self.composition.id)


# ----------- Composition utilities ------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class AddComponentViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_weightshare'))
        member.groups.add(members)

        material = Material.objects.create(
            owner=owner,
            name='Test Material'
        )
        MaterialComponentGroup.objects.create(
            owner=owner,
            name='Test Group'
        )
        SampleSeries.objects.create(
            owner=owner,
            material=material,
            name='Test Series'
        )

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.series = SampleSeries.objects.get(name='Test Series')
        self.component_group = MaterialComponentGroup.objects.get(name='Test Group')
        self.default_component = MaterialComponent.objects.default()
        self.sample = Sample.objects.get(series=self.series, timestep=Timestep.objects.default())
        self.composition = Composition.objects.create(
            owner=self.owner,
            sample=self.sample,
            group=self.component_group,
            fractions_of=self.default_component
        )
        self.component = MaterialComponent.objects.create(
            owner=self.owner,
            name='Test Component'
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('composition-add-component', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('composition-add-component', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('composition-add-component', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('composition-add-component', kwargs={'pk': self.composition.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        data = {'component': self.component.id}
        response = self.client.post(
            reverse('composition-add-component', kwargs={'pk': self.composition.pk}),
            data=data
        )
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'component': self.component.id}
        response = self.client.post(
            reverse('composition-add-component', kwargs={'pk': self.composition.pk}),
            data=data)
        self.assertEqual(response.status_code, 302)

    def test_post_adds_component(self):
        self.client.force_login(self.member)
        data = {'component': self.component.id}
        self.client.post(reverse('composition-add-component', kwargs={'pk': self.composition.pk}), data=data)
        self.composition.shares.get(component=self.component)


# ----------- Weight Share CRUD ----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class WeightShareModalDeleteViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='delete_weightshare'))
        member.groups.add(members)
        material = Material.objects.create(
            owner=owner,
            name='Test Material'
        )
        component_group = MaterialComponentGroup.objects.create(
            owner=owner,
            name='Test Group'
        )
        SampleSeries.objects.create(
            owner=owner,
            material=material,
            name='Test Series'
        )
        MaterialComponent.objects.create(owner=owner, name='Test Component')
        Composition.objects.create(
            owner=owner,
            sample=Sample.objects.get(series__name='Test Series'),
            group=component_group
        )

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.sample = Sample.objects.get(series__name='Test Series', timestep=Timestep.objects.default())
        self.composition = Composition.objects.get(sample=self.sample, group__name='Test Group')
        self.component = MaterialComponent.objects.get(name='Test Component')
        self.share = WeightShare.objects.create(
            owner=self.owner,
            composition=self.composition,
            component=self.component
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('weightshare-delete-modal', kwargs={'pk': self.share.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('weightshare-delete-modal', kwargs={'pk': self.share.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('weightshare-delete-modal', kwargs={'pk': self.share.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('weightshare-delete-modal', kwargs={'pk': self.share.pk}))
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('weightshare-delete-modal', kwargs={'pk': self.share.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('weightshare-delete-modal', kwargs={'pk': self.share.pk}))
        self.assertEqual(response.status_code, 302)

    def test_post_deletes_correct_share(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('weightshare-delete-modal', kwargs={'pk': self.share.pk}))
        self.assertEqual(response.status_code, 302)
        with self.assertRaises(WeightShare.DoesNotExist):
            WeightShare.objects.get(composition=self.composition, component=self.component)


# ----------- Materials/Components/Groups Relations --------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class AddComponentGroupViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_composition'))
        members.permissions.add(Permission.objects.get(codename='add_weightshare'))
        member.groups.add(members)
        material = Material.objects.create(
            owner=owner,
            name='Test Material'
        )
        MaterialComponentGroup.objects.create(
            owner=owner,
            name='Test Group'
        )
        SampleSeries.objects.create(
            owner=owner,
            material=material,
            name='Test Series'
        )

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.series = SampleSeries.objects.get(name='Test Series')
        self.component_group = MaterialComponentGroup.objects.get(name='Test Group')
        self.default_component = MaterialComponent.objects.default()

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('sampleseries-add-componentgroup', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sampleseries-add-componentgroup', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('sampleseries-add-componentgroup', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('sampleseries-add-componentgroup', kwargs={'pk': self.series.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        data = {
            'group': self.component_group.id,
            'fractions_of': self.default_component.id
        }
        response = self.client.post(
            reverse('sampleseries-add-componentgroup', kwargs={'pk': self.series.pk}),
            data=data
        )
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_member(self):
        self.client.force_login(self.member)
        data = {
            'group': self.component_group.id,
            'fractions_of': self.default_component.id
        }
        response = self.client.post(
            reverse('sampleseries-add-componentgroup', kwargs={'pk': self.series.pk}),
            data=data)
        self.assertEqual(response.status_code, 302)

    def test_post_adds_group_and_weight_shares_to_sample_series(self):
        self.client.force_login(self.member)
        data = {
            'group': self.component_group.id,
            'fractions_of': self.default_component.id
        }
        response = self.client.post(
            reverse('sampleseries-add-componentgroup', kwargs={'pk': self.series.pk}),
            data=data)
        self.assertEqual(response.status_code, 302)
        for sample in self.series.samples.all():
            Composition.objects.get(sample=sample, group=self.component_group)
