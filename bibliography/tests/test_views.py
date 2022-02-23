from django.contrib.auth.models import Group, User
from django.test import TestCase, modify_settings
from django.urls import reverse

from ..models import Source


# CurrentUserMiddleware is used to track object creation and change. It causes errors in the TestCases with
# logins. Can be disabled here because it is not relevant for these tests.
@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SourceListViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider', password='very-secure!')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('source-list'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('source-list'))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SourceCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider', password='very-secure!')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('source-create'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('source-create'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('source-create'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_200_ok_for_logged_in_users_with_minimal_data(self):
        self.client.force_login(self.outsider)
        data = {
            'type': 'article'
        }
        response = self.client.post(reverse('source-create'), data=data)
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SourceModalCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider', password='very-secure!')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('source-create-modal'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('source-create-modal'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('source-create-modal'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_200_ok_for_logged_in_users_with_minimal_data(self):
        self.client.force_login(self.outsider)
        data = {
            'type': 'article'
        }
        response = self.client.post(reverse('source-create-modal'), data=data)
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SourceDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner', password='very-secure!')
        User.objects.create(username='outsider', password='very-secure!')

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.source = Source.objects.create(
            owner=self.owner
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('source-detail', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('source-detail', kwargs={'pk': self.source.pk}))
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
        self.source = Source.objects.create(
            owner=self.owner
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('source-detail-modal', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('source-detail-modal', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SourceUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner', password='very-secure!')
        User.objects.create(username='outsider', password='very-secure!')
        member = User.objects.create(username='member', password='very-secure!')
        librarians = Group.objects.get(name='librarians')
        member.groups.add(librarians)

    def setUp(self):
        self.owner = User.objects.get(username='owner')
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
        User.objects.create(username='owner', password='very-secure!')
        User.objects.create(username='outsider', password='very-secure!')
        member = User.objects.create(username='member', password='very-secure!')
        librarians = Group.objects.get(name='librarians')
        member.groups.add(librarians)

    def setUp(self):
        self.owner = User.objects.get(username='owner')
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
        User.objects.create(username='owner', password='very-secure!')
        User.objects.create(username='outsider', password='very-secure!')
        member = User.objects.create(username='member', password='very-secure!')
        librarians = Group.objects.get(name='librarians')
        member.groups.add(librarians)

    def setUp(self):
        self.owner = User.objects.get(username='owner')
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
