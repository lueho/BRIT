from django.contrib.auth.models import Group, User
from django.urls import reverse

from utils.tests.testcases import UserLoginTestCase
from users.models import get_default_owner

from ..models import Author, Licence, Source


# ----------- Author CRUD ---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AuthorListViewTestCase(UserLoginTestCase):

    outsider = None

    @classmethod
    def setUpTestData(cls):
        cls.outsider = User.objects.create(username='outsider')

    def test_get_http_200_redirect_for_anonymous(self):
        response = self.client.get(reverse('author-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('author-list'))
        self.assertEqual(response.status_code, 200)


class AuthorCreateViewTestCase(UserLoginTestCase):

    outsider = None
    member = None

    @classmethod
    def setUpTestData(cls):
        cls.outsider = User.objects.create(username='outsider')
        cls.member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        cls.member.groups.add(editors)

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        response = self.client.get(reverse('author-create'))
        self.assertRedirects(
            response,
            f"{reverse('auth_login')}?next={reverse('author-create')}",
            status_code=302,
            target_status_code=200
        )

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('author-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('author-create'))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('author-create'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('author-create'), data={})
        self.assertRedirects(
            response,
            f"{reverse('auth_login')}?next={reverse('author-create')}",
            status_code=302,
            target_status_code=200
        )

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('author-create'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {
            'first_names': 'Test',
            'last_names': 'Author'
        }
        response = self.client.post(reverse('author-create'), data=data, follow=True)
        self.assertRedirects(
            response,
            f"{reverse('author-detail', kwargs={'pk': Author.objects.first().pk})}",
            status_code=302,
            target_status_code=200
        )


class AuthorModalCreateViewTestCase(UserLoginTestCase):

    outsider = None
    member = None

    @classmethod
    def setUpTestData(cls):
        cls.outsider = User.objects.create(username='outsider')
        cls.member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        cls.member.groups.add(editors)

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

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('author-create-modal'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('author-create-modal'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('author-create-modal'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {
            'first_names': 'Test',
            'last_names': 'Author'
        }
        response = self.client.post(reverse('author-create'), data=data, follow=True)
        self.assertRedirects(
            response,
            f"{reverse('author-detail', kwargs={'pk': Author.objects.first().pk})}",
            status_code=302,
            target_status_code=200
        )


class AuthorDetailViewTestCase(UserLoginTestCase):

    outsider = None
    author = None

    @classmethod
    def setUpTestData(cls):
        cls.outsider = User.objects.create(username='outsider')
        cls.author = Author.objects.create(
            owner=get_default_owner(),
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


class AuthorModalDetailViewTestCase(UserLoginTestCase):

    outsider = None
    author = None

    @classmethod
    def setUpTestData(cls):
        cls.outsider = User.objects.create(username='outsider')
        cls.author = Author.objects.create(
            owner=get_default_owner(),
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


class AuthorUpdateViewTestCase(UserLoginTestCase):

    outsider = None
    member = None
    author = None

    @classmethod
    def setUpTestData(cls):
        cls.outsider = User.objects.create(username='outsider')
        cls.member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        cls.member.groups.add(editors)
        cls.author = Author.objects.create(
            owner=get_default_owner(),
            first_names='Test',
            last_names='Author',
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('author-update', kwargs={'pk': self.author.pk}))
        self.assertRedirects(
            response,
            f"{reverse('auth_login')}?next={reverse('author-update', kwargs={'pk': self.author.pk})}",
            status_code=302,
            target_status_code=200
        )

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('author-update', kwargs={'pk': self.author.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('author-update', kwargs={'pk': self.author.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('author-update', kwargs={'pk': self.author.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('author-update', kwargs={'pk': self.author.pk}), data={})
        self.assertRedirects(
            response,
            f"{reverse('auth_login')}?next={reverse('author-update', kwargs={'pk': self.author.pk})}",
            status_code=302,
            target_status_code=200
        )

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('author-update', kwargs={'pk': self.author.pk}), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'last_names': 'Updated Author'}
        response = self.client.post(reverse('author-update', kwargs={'pk': self.author.pk}), data=data, follow=True)
        self.assertRedirects(
            response,
            f"{reverse('author-detail', kwargs={'pk': self.author.pk})}",
            status_code=302,
            target_status_code=200
        )


class AuthorModalUpdateViewTestCase(UserLoginTestCase):

    outsider = None
    member = None
    author = None

    @classmethod
    def setUpTestData(cls):
        cls.outsider = User.objects.create(username='outsider')
        cls.member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        cls.member.groups.add(editors)
        cls.author = Author.objects.create(
            owner=get_default_owner(),
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

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('author-update-modal', kwargs={'pk': self.author.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('author-update-modal', kwargs={'pk': self.author.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('author-update-modal', kwargs={'pk': self.author.pk}), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'last_names': 'Updated Author'}
        response = self.client.post(reverse('author-update', kwargs={'pk': self.author.pk}), data=data, follow=True)
        self.assertRedirects(
            response,
            f"{reverse('author-detail', kwargs={'pk': self.author.pk})}",
            status_code=302,
            target_status_code=200
        )


class AuthorModalDeleteViewTestCase(UserLoginTestCase):

    outsider = None
    member = None
    author = None

    @classmethod
    def setUpTestData(cls):
        cls.outsider = User.objects.create(username='outsider')
        cls.member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        cls.member.groups.add(editors)
        cls.author = Author.objects.create(
            owner=get_default_owner(),
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

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('author-delete-modal', kwargs={'pk': self.author.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

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
        self.assertRedirects(
            response,
            f"{reverse('author-list')}",
            status_code=302,
            target_status_code=200
        )


# ----------- Licence CRUD ---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class LicenceListViewTestCase(UserLoginTestCase):

    outsider = None

    @classmethod
    def setUpTestData(cls):
        cls.outsider = User.objects.create(username='outsider')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('licence-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('licence-list'))
        self.assertEqual(response.status_code, 200)


class LicenceCreateViewTestCase(UserLoginTestCase):
    outsider = None
    member = None

    @classmethod
    def setUpTestData(cls):
        cls.outsider = User.objects.create(username='outsider')
        cls.member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        cls.member.groups.add(editors)

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('licence-create'))
        self.assertRedirects(
            response,
            f"{reverse('auth_login')}?next={reverse('licence-create')}",
            status_code=302,
            target_status_code=200
        )

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('licence-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('licence-create'))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('licence-create'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('licence-create'), data={})
        self.assertRedirects(
            response,
            f"{reverse('auth_login')}?next={reverse('licence-create')}",
            status_code=302,
            target_status_code=200
        )

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('licence-create'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Licence'}
        response = self.client.post(reverse('licence-create'), data=data)
        self.assertRedirects(
            response,
            f"{reverse('licence-detail', kwargs={'pk': Licence.objects.first().pk})}",
            status_code=302,
            target_status_code=200
        )


class LicenceModalCreateViewTestCase(UserLoginTestCase):

    outsider = None
    member = None

    @classmethod
    def setUpTestData(cls):
        cls.outsider = User.objects.create(username='outsider')
        cls.member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        cls.member.groups.add(editors)

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

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('licence-create-modal'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('licence-create-modal'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('licence-create-modal'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Licence'}
        response = self.client.post(reverse('licence-create-modal'), data=data, follow=True)
        self.assertRedirects(
            response,
            f"{reverse('licence-detail', kwargs={'pk': Licence.objects.first().pk})}",
            status_code=302,
            target_status_code=200
        )


class LicenceDetailViewTestCase(UserLoginTestCase):

    outsider = None
    licence = None

    @classmethod
    def setUpTestData(cls):
        cls.outsider = User.objects.create(username='outsider')
        cls.licence = Licence.objects.create(
            owner=get_default_owner(),
            name='Test Licence',
            reference_url='https://www.reference-url.org',
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('licence-detail', kwargs={'pk': self.licence.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('licence-detail', kwargs={'pk': self.licence.pk}))
        self.assertEqual(response.status_code, 200)


class LicenceModalDetailViewTestCase(UserLoginTestCase):

    outsider = None
    licence = None

    @classmethod
    def setUpTestData(cls):
        cls.outsider = User.objects.create(username='outsider')
        cls.licence = Licence.objects.create(
            owner=get_default_owner(),
            name='Test Licence',
            reference_url='https://www.reference-url.org',
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('licence-detail-modal', kwargs={'pk': self.licence.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('licence-detail-modal', kwargs={'pk': self.licence.pk}))
        self.assertEqual(response.status_code, 200)


class LicenceUpdateViewTestCase(UserLoginTestCase):

    outsider = None
    member = None
    licence = None

    @classmethod
    def setUpTestData(cls):
        cls.outsider = User.objects.create(username='outsider')
        cls.member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        cls.member.groups.add(editors)
        cls.licence = Licence.objects.create(
            owner=get_default_owner(),
            name='Test Licence',
            reference_url='https://www.reference-url.org',
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('licence-update', kwargs={'pk': self.licence.pk}), follow=True)
        self.assertRedirects(
            response,
            f"{reverse('auth_login')}?next={reverse('licence-update', kwargs={'pk': self.licence.pk})}",
            status_code=302,
            target_status_code=200
        )

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('licence-update', kwargs={'pk': self.licence.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('licence-update', kwargs={'pk': self.licence.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('licence-update', kwargs={'pk': self.licence.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('licence-update', kwargs={'pk': self.licence.pk}), data={}, follow=True)
        self.assertRedirects(
            response,
            f"{reverse('auth_login')}?next={reverse('licence-update', kwargs={'pk': self.licence.pk})}",
            status_code=302,
            target_status_code=200
        )

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('licence-update', kwargs={'pk': self.licence.pk}), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Updated Test Licence'}
        response = self.client.post(reverse('licence-update', kwargs={'pk': self.licence.pk}), data=data, follow=True)
        self.assertRedirects(
            response,
            f"{reverse('licence-detail', kwargs={'pk': self.licence.pk})}",
            status_code=302,
            target_status_code=200
        )


class LicenceModalUpdateViewTestCase(UserLoginTestCase):

    outsider = None
    member = None
    licence = None

    @classmethod
    def setUpTestData(cls):
        cls.outsider = User.objects.create(username='outsider')
        cls.member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        cls.member.groups.add(editors)
        cls.licence = Licence.objects.create(
            owner=get_default_owner(),
            name='Test Licence',
            reference_url='https://www.reference-url.org',
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

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('licence-update-modal', kwargs={'pk': self.licence.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('licence-update-modal', kwargs={'pk': self.licence.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('licence-update-modal', kwargs={'pk': self.licence.pk}), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Updated Test Licence'}
        response = self.client.post(reverse('licence-update-modal', kwargs={'pk': self.licence.pk}), data=data, follow=True)
        self.assertRedirects(
            response,
            f"{reverse('licence-detail', kwargs={'pk': self.licence.pk})}",
            status_code=302,
            target_status_code=200
        )


class LicenceModalDeleteViewTestCase(UserLoginTestCase):

    outsider = None
    member = None
    licence = None

    @classmethod
    def setUpTestData(cls):
        cls.outsider = User.objects.create(username='outsider')
        cls.member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        cls.member.groups.add(editors)
        cls.licence = Licence.objects.create(
            owner=get_default_owner(),
            name='Test Licence',
            reference_url='https://www.reference-url.org',
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

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('licence-delete-modal', kwargs={'pk': self.licence.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

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
        self.assertRedirects(
            response,
            f"{reverse('licence-list')}",
            status_code=302,
            target_status_code=200
        )


# ----------- Source CRUD ----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class SourceListViewTestCase(UserLoginTestCase):

    outsider = None

    @classmethod
    def setUpTestData(cls):
        cls.outsider = User.objects.create(username='outsider')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('source-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('source-list'))
        self.assertEqual(response.status_code, 200)


class SourceCreateViewTestCase(UserLoginTestCase):

    outsider = None
    member = None

    @classmethod
    def setUpTestData(cls):
        cls.outsider = User.objects.create(username='outsider')
        cls.member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        cls.member.groups.add(editors)

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('source-create'), follow=True)
        self.assertRedirects(
            response,
            f"{reverse('auth_login')}?next={reverse('source-create')}",
            status_code=302,
            target_status_code=200
        )

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('source-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('source-create'))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('source-create'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('source-create'), data={}, follow=True)
        self.assertRedirects(
            response,
            f"{reverse('auth_login')}?next={reverse('source-create')}",
            status_code=302,
            target_status_code=200
        )

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('source-create'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {'abbreviation': 'TS1', 'type': 'article', 'title': 'Test Source'}
        response = self.client.post(reverse('source-create'), data=data, follow=True)
        self.assertRedirects(
            response,
            f"{reverse('source-detail', kwargs={'pk': Source.objects.first().pk})}",
            status_code=302,
            target_status_code=200
        )


class SourceModalCreateViewTestCase(UserLoginTestCase):

    outsider = None
    member = None

    @classmethod
    def setUpTestData(cls):
        cls.outsider = User.objects.create(username='outsider')
        cls.member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        cls.member.groups.add(editors)

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

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('source-create-modal'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('source-create-modal'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('source-create-modal'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {'abbreviation': 'TS1', 'type': 'article', 'title': 'Test Source'}
        response = self.client.post(reverse('source-create-modal'), data=data)
        self.assertRedirects(
            response,
            f"{reverse('source-detail', kwargs={'pk': Source.objects.first().pk})}",
            status_code=302,
            target_status_code=200
        )


class SourceDetailViewTestCase(UserLoginTestCase):

    outsider = None
    source = None

    @classmethod
    def setUpTestData(cls):
        cls.outsider = User.objects.create(username='outsider')
        cls.source = Source.objects.create(
            owner=get_default_owner(),
            abbreviation='TS1',
            type='article',
            title='Test Source'
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('source-detail', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('source-detail', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 200)


class SourceModalDetailViewTestCase(UserLoginTestCase):

    outsider = None
    source = None

    @classmethod
    def setUpTestData(cls):
        cls.outsider = User.objects.create(username='outsider')
        cls.source = Source.objects.create(
            owner=get_default_owner(),
            abbreviation='TS1',
            type='article',
            title='Test Source'
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('source-detail-modal', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('source-detail-modal', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 200)


class SourceUpdateViewTestCase(UserLoginTestCase):

    member = None
    outsider = None
    source = None

    @classmethod
    def setUpTestData(cls):
        cls.outsider = User.objects.create(username='outsider')
        cls.member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        cls.member.groups.add(editors)
        cls.source = Source.objects.create(
            owner=get_default_owner(),
            abbreviation='TS1',
            type='article',
            title='Test Source'
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('source-update', kwargs={'pk': self.source.pk}), follow=True)
        self.assertRedirects(
            response,
            f"{reverse('auth_login')}?next={reverse('source-update', kwargs={'pk': self.source.pk})}",
            status_code=302,
            target_status_code=200
        )

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('source-update', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('source-update', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('source-update', kwargs={'pk': self.source.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('source-update', kwargs={'pk': self.source.pk}), data={}, follow=True)
        self.assertRedirects(
            response,
            f"{reverse('auth_login')}?next={reverse('source-update', kwargs={'pk': self.source.pk})}",
            status_code=302,
            target_status_code=200
        )

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        data = {
            'type': 'article'
        }
        response = self.client.post(reverse('source-update', kwargs={'pk': self.source.pk}), data=data)
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {
            'abbreviation': self.source.abbreviation,
            'type': self.source.type,
            'title': 'Updated Test Source'
        }
        response = self.client.post(reverse('source-update', kwargs={'pk': self.source.pk}), data=data)
        self.assertRedirects(
            response,
            f"{reverse('source-detail', kwargs={'pk': self.source.pk})}",
            status_code=302,
            target_status_code=200
        )


class SourceModalUpdateViewTestCase(UserLoginTestCase):

    member = None
    outsider = None
    source = None

    @classmethod
    def setUpTestData(cls):
        cls.outsider = User.objects.create(username='outsider')
        cls.member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        cls.member.groups.add(editors)
        cls.source = Source.objects.create(
            owner=get_default_owner(),
            abbreviation='TS1',
            type='article',
            title='Test Source'
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

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('source-update-modal', kwargs={'pk': self.source.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('source-update-modal', kwargs={'pk': self.source.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('source-update-modal', kwargs={'pk': self.source.pk}), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {
            'abbreviation': self.source.abbreviation,
            'type': self.source.type,
            'title': 'Updated Test Source'
        }
        response = self.client.post(reverse('source-update-modal', kwargs={'pk': self.source.pk}), data=data)
        self.assertRedirects(
            response,
            f"{reverse('source-detail', kwargs={'pk': self.source.pk})}",
            status_code=302,
            target_status_code=200
        )


class SourceModalDeleteViewTestCase(UserLoginTestCase):

    outsider = None
    member = None
    source = None

    @classmethod
    def setUpTestData(cls):
        cls.outsider = User.objects.create(username='outsider')
        cls.member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        cls.member.groups.add(editors)
        cls.source = Source.objects.create(
            owner=get_default_owner(),
            abbreviation='TS1',
            type='article',
            title='Test Source'
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

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('source-delete-modal', kwargs={'pk': self.source.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

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
        self.assertRedirects(
            response,
            f"{reverse('source-list')}",
            status_code=302,
            target_status_code=200
        )


class CheckSourceUrlViewTestCase(UserLoginTestCase):

    outsider = None
    member = None
    source = None

    @classmethod
    def setUpTestData(cls):
        cls.outsider = User.objects.create(username='outsider')
        cls.member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        cls.member.groups.add(editors)
        cls.source = Source.objects.create(
            owner=get_default_owner(),
            title='Test Source from the Web',
            abbreviation='WORKING',
            url='https://httpbin.org/status/200'
        )

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        request_url = reverse('source-check-url', kwargs={'pk': self.source.pk})
        response = self.client.get(request_url, follow=True)
        self.assertRedirects(
            response,
            f"{reverse('auth_login')}?next={reverse('source-check-url', kwargs={'pk': self.source.pk})}",
            status_code=302,
            target_status_code=200
        )

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('source-check-url', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('source-check-url', kwargs={'pk': self.source.pk}))
        self.assertEqual(200, response.status_code)


class SourceListCheckUrlsViewTestCase(UserLoginTestCase):

    outsider = None
    member = None

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        cls.outsider = User.objects.create(username='outsider')
        cls.member = User.objects.create(username='member')
        editors = Group.objects.get(name='editors')
        cls.member.groups.add(editors)
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
