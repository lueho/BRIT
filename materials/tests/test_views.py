from django.contrib.auth.models import Group, User, Permission
from django.test import TestCase, modify_settings
from django.urls import reverse

from ..models import Material, MaterialComponentShare, MaterialComponent, CompositionSet, \
    MaterialComponentGroupSettings, MaterialComponentGroup


# CurrentUserMiddleware is used to track object creation and change. It causes errors in the TestCases with
# logins. Can be disabled here because it is not relevant for these tests.
@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialListViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider', password='very-secure!')

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
        User.objects.create(username='outsider', password='very-secure!')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('material-create'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('material-create'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('material-create'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_302_redirect_for_logged_in_users_with_minimal_data(self):
        self.client.force_login(self.outsider)
        data = {
            'name': 'Test Material'
        }
        response = self.client.post(reverse('material-create'), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialModalCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider', password='very-secure!')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('material-create-modal'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('material-create-modal'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('material-create-modal'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_302_redirect_for_logged_in_users_with_minimal_data(self):
        self.client.force_login(self.outsider)
        data = {
            'name': 'Test Material'
        }
        response = self.client.post(reverse('material-create-modal'), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner', password='very-secure!')
        User.objects.create(username='outsider', password='very-secure!')

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
        User.objects.create(username='owner', password='very-secure!')
        User.objects.create(username='outsider', password='very-secure!')

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
        User.objects.create(username='owner', password='very-secure!')
        User.objects.create(username='outsider', password='very-secure!')
        member = User.objects.create(username='member', password='very-secure!')
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
        data = {
            'name': 'Updated Test Material'
        }
        response = self.client.post(reverse('material-update', kwargs={'pk': self.material.pk}), data=data)
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Updated Test Material'
        }
        response = self.client.post(reverse('material-update', kwargs={'pk': self.material.pk}), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialModalUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner', password='very-secure!')
        User.objects.create(username='outsider', password='very-secure!')
        member = User.objects.create(username='member', password='very-secure!')
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
        data = {
            'name': 'Updated Test Material'
        }
        response = self.client.post(reverse('material-update-modal', kwargs={'pk': self.material.pk}), data=data)
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Update Test Material'
        }
        response = self.client.post(reverse('material-update-modal', kwargs={'pk': self.material.pk}), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class MaterialModalDeleteViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner', password='very-secure!')
        User.objects.create(username='outsider', password='very-secure!')
        member = User.objects.create(username='member', password='very-secure!')
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


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class CompositionSetModalUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = User.objects.create(username='owner', password='very-secure!')
        User.objects.create(username='outsider', password='very-secure!')
        member = User.objects.create(username='member', password='very-secure!')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='change_compositionset'))
        members.permissions.add(Permission.objects.get(codename='change_materialcomponentshare'))
        member.groups.add(members)

        material = Material.objects.create(
            owner=owner,
            name='Test Material'
        )

        group = MaterialComponentGroup.objects.create(
            owner=owner,
            name='Test Group'
        )

        group_settings = MaterialComponentGroupSettings.objects.create(
            owner=owner,
            group=group,
            material_settings=material.standard_settings,
            fractions_of=MaterialComponent.objects.default()
        )

        composition_set = CompositionSet.objects.get(
            owner=owner,
            group_settings=group_settings
        )

        for i in range(2):
            component = MaterialComponent.objects.create(
                owner=owner,
                name=f'Test Component {i}'
            )
            MaterialComponentShare.objects.create(
                owner=owner,
                component=component,
                composition_set=composition_set,
                average=0.2,
                standard_deviation=0.01
            )

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.composition_set = CompositionSet.objects.get(
            group_settings__group__name='Test Group'
        )
        self.material = Material.objects.get(
            owner=self.owner,
            name='Test Material'
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('compositionset-update-modal', kwargs={'pk': self.composition_set.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('compositionset-update-modal', kwargs={'pk': self.composition_set.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('compositionset-update-modal', kwargs={'pk': self.composition_set.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertIn('formset', response.context)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(
            reverse('compositionset-update-modal', kwargs={'pk': self.composition_set.pk}),
            data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(
            reverse('compositionset-update-modal', kwargs={'pk': self.composition_set.pk}),
            data={}
        )
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        components = [c.id for c in MaterialComponent.objects.exclude(name='Fresh Matter (FM)')]
        shares = [s.id for s in MaterialComponentShare.objects.exclude(
            component__name='Fresh Matter (FM)'
        )]
        data = {
            'materialcomponentshare_set-INITIAL_FORMS': '2',
            'materialcomponentshare_set-TOTAL_FORMS': '2',
            'materialcomponentshare_set-0-id': f'{shares[0]}',
            'materialcomponentshare_set-0-component': f'{components[0]}',
            'materialcomponentshare_set-0-average': '45.5',
            'materialcomponentshare_set-0-standard_deviation': '1.5',
            'materialcomponentshare_set-1-id': f'{shares[1]}',
            'materialcomponentshare_set-1-component': f'{components[1]}',
            'materialcomponentshare_set-1-average': '54.5',
            'materialcomponentshare_set-1-standard_deviation': '1.5',
        }
        response = self.client.post(
            reverse('compositionset-update-modal', kwargs={'pk': self.composition_set.pk}),
            data=data
        )
        self.assertEqual(response.status_code, 302)

    def test_post_http_302_redirect_for_members_with_correct_data(self):
        self.client.force_login(self.member)
        components = [c.id for c in MaterialComponent.objects.exclude(name='Fresh Matter (FM)')]
        shares = [s.id for s in MaterialComponentShare.objects.exclude(
            component__name='Fresh Matter (FM)'
        )]
        data = {
            'materialcomponentshare_set-INITIAL_FORMS': '2',
            'materialcomponentshare_set-TOTAL_FORMS': '2',
            'materialcomponentshare_set-0-id': f'{shares[0]}',
            'materialcomponentshare_set-0-component': f'{components[0]}',
            'materialcomponentshare_set-0-average': '45.5',
            'materialcomponentshare_set-0-standard_deviation': '1.5',
            'materialcomponentshare_set-1-id': f'{shares[1]}',
            'materialcomponentshare_set-1-component': f'{components[1]}',
            'materialcomponentshare_set-1-average': '54.5',
            'materialcomponentshare_set-1-standard_deviation': '1.5',
        }
        response = self.client.post(
            reverse('compositionset-update-modal', kwargs={'pk': self.composition_set.pk}),
            data=data
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(MaterialComponentShare.objects.all()), 3)
