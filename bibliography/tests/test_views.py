from django.contrib.auth.models import Group, User
from django.test import TestCase, modify_settings
from django.urls import reverse

from users.models import get_default_owner

from ..models import Author, Licence, Source


# ----------- Author CRUD ---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


# CurrentUserMiddleware is used to track object creation and change. It causes errors in the TestCases with
# logins. Can be disabled here because it is not relevant for these tests.
@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class AuthorListViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')

    def test_get_http_200_redirect_for_anonymous(self):
        response = self.client.get(reverse('author-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('author-list'))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class AuthorCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        member.groups.add(editors)

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('author-create'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('author-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('author-create'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('author-create'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('author-create'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {
            'first_names': 'Test',
            'last_names': 'Author'
        }
        response = self.client.post(reverse('author-create'), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class AuthorModalCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        member.groups.add(editors)

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('author-create-modal'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('author-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('author-create-modal'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('author-create-modal'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('author-create-modal'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {
            'first_names': 'Test',
            'last_names': 'Author'
        }
        response = self.client.post(reverse('author-create-modal'), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class AuthorDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.author = Author.objects.create(
            owner=self.owner,
            first_names='Test',
            last_names='Author',
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('author-detail', kwargs={'pk': self.author.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('author-detail', kwargs={'pk': self.author.pk}))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class AuthorModalDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.author = Author.objects.create(
            owner=self.owner,
            first_names='Test',
            last_names='Author',
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('author-detail-modal', kwargs={'pk': self.author.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('author-detail-modal', kwargs={'pk': self.author.pk}))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class AuthorUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        member.groups.add(editors)

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.author = Author.objects.create(
            owner=self.owner,
            first_names='Test',
            last_names='Author',
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('author-update', kwargs={'pk': self.author.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('author-update', kwargs={'pk': self.author.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('author-update', kwargs={'pk': self.author.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('author-update', kwargs={'pk': self.author.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('author-update', kwargs={'pk': self.author.pk}), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'last_names': 'Updated Author'}
        response = self.client.post(reverse('author-update', kwargs={'pk': self.author.pk}), data=data)
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class AuthorModalUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        member.groups.add(editors)

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.author = Author.objects.create(
            owner=self.owner,
            first_names='Test',
            last_names='Author',
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('author-update-modal', kwargs={'pk': self.author.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('author-update-modal', kwargs={'pk': self.author.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('author-update-modal', kwargs={'pk': self.author.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('author-update-modal', kwargs={'pk': self.author.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('author-update-modal', kwargs={'pk': self.author.pk}), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'last_names': 'Updated Author'}
        response = self.client.post(reverse('author-update-modal', kwargs={'pk': self.author.pk}), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class AuthorModalDeleteViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        member.groups.add(editors)

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.author = Author.objects.create(
            owner=self.owner,
            first_names='Test',
            last_names='Author',
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('author-delete-modal', kwargs={'pk': self.author.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('author-delete-modal', kwargs={'pk': self.author.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('author-delete-modal', kwargs={'pk': self.author.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('author-delete-modal', kwargs={'pk': self.author.pk}))
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('author-delete-modal', kwargs={'pk': self.author.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_successful_delete_and_http_302_and_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('author-delete-modal', kwargs={'pk': self.author.pk}))
        with self.assertRaises(Author.DoesNotExist):
            Author.objects.get(pk=self.author.pk)
        self.assertEqual(response.status_code, 302)


# ----------- Licence CRUD ---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


# CurrentUserMiddleware is used to track object creation and change. It causes errors in the TestCases with
# logins. Can be disabled here because it is not relevant for these tests.
@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class LicenceListViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('licence-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('licence-list'))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class LicenceCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        member.groups.add(editors)

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('licence-create'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('licence-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('licence-create'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('licence-create'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('licence-create'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_200_ok_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Licence'}
        response = self.client.post(reverse('licence-create'), data=data)
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class LicenceModalCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        member.groups.add(editors)

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('licence-create-modal'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('licence-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('licence-create-modal'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('licence-create-modal'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('licence-create-modal'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_200_ok_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Licence'}
        response = self.client.post(reverse('licence-create-modal'), data=data)
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class LicenceDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        get_default_owner()
        User.objects.create(username='outsider')

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.licence = Licence.objects.create(
            owner=self.owner,
            name='Test Licence',
            reference_url='https://www.test_licence.org'
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('licence-detail', kwargs={'pk': self.licence.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('licence-detail', kwargs={'pk': self.licence.pk}))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class LicenceModalDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        get_default_owner()
        User.objects.create(username='outsider')

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.licence = Licence.objects.create(
            owner=self.owner,
            name='Test Licence',
            reference_url='https://www.test_licence.org'
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('licence-detail-modal', kwargs={'pk': self.licence.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('licence-detail-modal', kwargs={'pk': self.licence.pk}))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class LicenceUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        member.groups.add(editors)

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.licence = Licence.objects.create(
            owner=self.owner,
            name='Test Licence',
            reference_url='https://www.test_licence.org'
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('licence-update', kwargs={'pk': self.licence.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('licence-update', kwargs={'pk': self.licence.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('licence-update', kwargs={'pk': self.licence.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('licence-update', kwargs={'pk': self.licence.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('licence-update', kwargs={'pk': self.licence.pk}), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Updated Test Licence'}
        response = self.client.post(reverse('licence-update', kwargs={'pk': self.licence.pk}), data=data)
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class LicenceModalUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        member.groups.add(editors)

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.licence = Licence.objects.create(
            owner=self.owner,
            name='Test Licence',
            reference_url='https://www.test_licence.org'
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('licence-update-modal', kwargs={'pk': self.licence.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('licence-update-modal', kwargs={'pk': self.licence.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('licence-update-modal', kwargs={'pk': self.licence.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('licence-update-modal', kwargs={'pk': self.licence.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('licence-update-modal', kwargs={'pk': self.licence.pk}), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Updated Test Licence'}
        response = self.client.post(reverse('licence-update-modal', kwargs={'pk': self.licence.pk}), data=data)
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class LicenceModalDeleteViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        member.groups.add(editors)

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.licence = Licence.objects.create(
            owner=self.owner,
            name='Test Licence',
            reference_url='https://www.test_licence.org'
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('licence-delete-modal', kwargs={'pk': self.licence.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('licence-delete-modal', kwargs={'pk': self.licence.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('licence-delete-modal', kwargs={'pk': self.licence.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('licence-delete-modal', kwargs={'pk': self.licence.pk}))
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('licence-delete-modal', kwargs={'pk': self.licence.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_successful_delete_and_http_302_and_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('licence-delete-modal', kwargs={'pk': self.licence.pk}))
        with self.assertRaises(Licence.DoesNotExist):
            Licence.objects.get(pk=self.licence.pk)
        self.assertEqual(response.status_code, 302)


# ----------- Source CRUD ----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


# CurrentUserMiddleware is used to track object creation and change. It causes errors in the TestCases with
# logins. Can be disabled here because it is not relevant for these tests.
@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SourceListViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('source-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('source-list'))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SourceCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        member.groups.add(editors)

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('source-create'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('source-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('source-create'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('source-create'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('source-create'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_200_ok_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {'type': 'article'}
        response = self.client.post(reverse('source-create'), data=data)
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SourceModalCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        member.groups.add(editors)

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('source-create-modal'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('source-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('source-create-modal'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('source-create-modal'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('source-create-modal'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_200_ok_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {'type': 'article'}
        response = self.client.post(reverse('source-create-modal'), data=data)
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SourceDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        member.groups.add(editors)

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.source = Source.objects.create(
            owner=self.owner
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('source-detail', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('source-detail', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SourceModalDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        get_default_owner()
        User.objects.create(username='outsider')

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.source = Source.objects.create(
            owner=self.owner
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('source-detail-modal', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('source-detail-modal', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SourceUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        member.groups.add(editors)

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.source = Source.objects.create(
            owner=self.owner
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('source-update', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('source-update', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('source-update', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('source-update', kwargs={'pk': self.source.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        data = {
            'type': 'article'
        }
        response = self.client.post(reverse('source-update', kwargs={'pk': self.source.pk}), data=data)
        self.assertEqual(response.status_code, 403)

    def test_post_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        data = {
            'type': 'article'
        }
        response = self.client.post(reverse('source-update', kwargs={'pk': self.source.pk}), data=data)
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SourceModalUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        member.groups.add(editors)

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.source = Source.objects.create(
            owner=self.owner
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('source-update-modal', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('source-update-modal', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('source-update-modal', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('source-update-modal', kwargs={'pk': self.source.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        data = {
            'type': 'article'
        }
        response = self.client.post(reverse('source-update-modal', kwargs={'pk': self.source.pk}), data=data)
        self.assertEqual(response.status_code, 403)

    def test_post_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        data = {
            'type': 'article'
        }
        response = self.client.post(reverse('source-update-modal', kwargs={'pk': self.source.pk}), data=data)
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SourceModalDeleteViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        member.groups.add(editors)

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.source = Source.objects.create(
            owner=self.owner
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('source-delete-modal', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('source-delete-modal', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('source-delete-modal', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('source-delete-modal', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('source-delete-modal', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_successful_delete_and_http_302_and_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('source-delete-modal', kwargs={'pk': self.source.pk}))
        with self.assertRaises(Source.DoesNotExist):
            Source.objects.get(pk=self.source.pk)
        self.assertEqual(response.status_code, 302)

@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class CheckSourceUrlViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        member.groups.add(editors)
        Source.objects.create(
            owner=owner,
            title='Test Source from the Web',
            abbreviation='WORKING',
            url='https://httpbin.org/status/200'
        )

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.source = Source.objects.get(abbreviation='WORKING')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        request_url = reverse('source-check-url', kwargs={'pk': self.source.pk})
        response = self.client.get(request_url, follow=True)
        self.assertRedirects(response, f"{reverse('auth_login')}?next={request_url}", status_code=302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('source-check-url', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('source-check-url', kwargs={'pk': self.source.pk}))
        self.assertEqual(200, response.status_code)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SourceListCheckUrlsViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        member.groups.add(editors)
        Source.objects.create(
            owner=owner,
            title='Test Source from the Web',
            abbreviation='WORKING',
            url='https://httpbin.org/status/200'
        )
        Source.objects.create(
            owner=owner,
            title='Test Source from the Web',
            abbreviation='NOTWORKING',
            url='https://httpbin.org/status/404'
        )
        Source.objects.create(
            owner=owner,
            title='Test Source from the Web',
            abbreviation='NOTWORKING',
            url='https://httpbin.org/status/404'
        )

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        request_url = f"{reverse('source-list-check-urls')}?url_valid=False"
        response = self.client.get(request_url, follow=True)
        self.assertRedirects(response, f"{reverse('auth_login')}?next={request_url}", status_code=302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        request_url = f"{reverse('source-list-check-urls')}?url_valid=False"
        response = self.client.get(request_url)
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        request_url = f"{reverse('source-list-check-urls')}?url_valid=False&page=1"
        response = self.client.get(request_url)
        self.assertEqual(200, response.status_code)
