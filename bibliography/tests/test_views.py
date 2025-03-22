from unittest.mock import patch

from django.db.models.signals import post_save
from django.urls import reverse
from factory.django import mute_signals

from utils.tests.testcases import AbstractTestCases, ViewWithPermissionsTestCase
from ..models import Author, Licence, Source, SourceAuthor


# ----------- Author CRUD ---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AuthorListViewTestCase(ViewWithPermissionsTestCase):

    def test_get_http_200_redirect_for_anonymous(self):
        response = self.client.get(reverse('author-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('author-list'))
        self.assertEqual(response.status_code, 200)


class AuthorCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['add_author']

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


class AuthorModalCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['add_author']

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


class AuthorCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    model = Author

    view_create_name = 'author-create'
    view_published_list_name = 'author-list'
    view_private_list_name = 'author-list-owned'
    view_detail_name = 'author-detail'
    view_update_name = 'author-update'
    view_delete_name = 'author-delete-modal'

    create_object_data = {'last_names': 'Test Author'}
    update_object_data = {'last_names': 'Updated Author'}


class AuthorModalDetailViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['view_author']

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.author = Author.objects.create(
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


class AuthorModalUpdateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['change_author']

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.author = Author.objects.create(
            first_names='Test',
            last_names='Author',
            publication_status='published'
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
        response = self.client.post(reverse('author-update-modal', kwargs={'pk': self.author.pk}), data=data,
                                    follow=True)
        self.assertRedirects(
            response,
            f"{reverse('author-detail', kwargs={'pk': self.author.pk})}",
            status_code=302,
            target_status_code=200
        )


class AuthorModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['delete_author']

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.author = Author.objects.create(
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


# ----------- Author Utils ---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AuthorAutoCompleteViewTestCase(ViewWithPermissionsTestCase):

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('author-autocomplete'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('author-autocomplete'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('author-autocomplete'))
        self.assertEqual(response.status_code, 200)

    def test_get_returns_only_authors_with_given_string_in_name(self):
        test_author = Author.objects.create(first_names='Test', last_names='Author')
        Author.objects.create(first_names='Another', last_names='Author')
        response = self.client.get(reverse('author-autocomplete'), {'q': 'Test'})
        results = [{
            'id': str(test_author.pk),
            'text': 'Author, Test',
            'selected_text': 'Author, Test'
        }]
        self.assertEqual(1, len(response.json()['results']))
        self.assertDictEqual(results[0], response.json()['results'][0])


# ----------- Licence CRUD ---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class LicenceListViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['view_licence']

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('licence-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('licence-list'))
        self.assertEqual(response.status_code, 200)


class LicenceCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['add_licence']

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


class LicenceModalCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['add_licence']

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
            f"{reverse('licence-detail', kwargs={'pk': Licence.objects.get(name='Test Licence').pk})}",
            status_code=302,
            target_status_code=200
        )


class LicenceCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    model = Licence

    view_create_name = 'licence-create'
    view_published_list_name = 'licence-list'
    view_private_list_name = 'licence-list-owned'
    view_detail_name = 'licence-detail'
    view_update_name = 'licence-update'
    view_delete_name = 'licence-delete-modal'

    create_object_data = {'name': 'Test Licence'}
    update_object_data = {'name': 'Updated Test Licence'}


class LicenceModalDetailViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['view_licence']

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.licence = Licence.objects.create(
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


class LicenceModalUpdateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['change_licence']

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.licence = Licence.objects.create(
            name='Test Licence',
            reference_url='https://www.reference-url.org',
            publication_status='published',
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
        response = self.client.post(reverse('licence-update-modal', kwargs={'pk': self.licence.pk}), data=data,
                                    follow=True)
        self.assertRedirects(
            response,
            f"{reverse('licence-detail', kwargs={'pk': self.licence.pk})}",
            status_code=302,
            target_status_code=200
        )


class LicenceModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['delete_licence']

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.licence = Licence.objects.create(
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


class SourceListViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['view_source']

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('source-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('source-list'))
        self.assertEqual(response.status_code, 200)


class SourceCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['add_source']

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
        author_1 = Author.objects.create(first_names='One', last_names='Author')
        author_2 = Author.objects.create(first_names='Two', last_names='Author')
        data = {
            'abbreviation': 'TS1',
            'type': 'article',
            'title': 'Test Source',
            'sourceauthors-TOTAL_FORMS': 2,
            'sourceauthors-INITIAL_FORMS': 0,
            'sourceauthors-0-id': '',
            'sourceauthors-0-source': '',
            'sourceauthors-0-author': author_1.pk,
            'sourceauthors-1-id': '',
            'sourceauthors-1-source': '',
            'sourceauthors-1-author': author_2.pk
        }
        with mute_signals(post_save):
            response = self.client.post(reverse('source-create'), data=data, follow=True)

        new_source = Source.objects.get(abbreviation='TS1')
        self.assertEqual(2, new_source.authors.all().count())
        self.assertRedirects(
            response,
            f"{reverse('source-detail', kwargs={'pk': new_source.pk})}",
            status_code=302,
            target_status_code=200
        )


class SourceModalCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['add_source']

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
        author_1 = Author.objects.create(first_names='One', last_names='Author')
        author_2 = Author.objects.create(first_names='Two', last_names='Author')
        data = {
            'abbreviation': 'TS1',
            'authors': [author_1.pk, author_2.pk],
            'type': 'article',
            'title': 'Test Source',
            'sourceauthors-TOTAL_FORMS': 2,
            'sourceauthors-INITIAL_FORMS': 0,
            'sourceauthors-0-id': '',
            'sourceauthors-0-source': '',
            'sourceauthors-0-author': author_1.pk,
            'sourceauthors-1-id': '',
            'sourceauthors-1-source': '',
            'sourceauthors-1-author': author_2.pk
        }
        with mute_signals(post_save):
            response = self.client.post(reverse('source-create'), data=data, follow=True)

        new_source = Source.objects.get(abbreviation='TS1')
        self.assertEqual(2, new_source.authors.all().count())
        self.assertRedirects(
            response,
            f"{reverse('source-detail', kwargs={'pk': new_source.pk})}",
            status_code=302,
            target_status_code=200
        )


class SourceCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    model = Source

    view_create_name = 'source-create'
    view_published_list_name = 'source-list'
    view_private_list_name = 'source-list-owned'
    view_detail_name = 'source-detail'
    view_update_name = 'source-update'
    view_delete_name = 'source-delete-modal'

    create_object_data = {
        'abbreviation': 'TS1',
        'type': 'article',
        'title': 'Test Source',
        'url': 'https://www.test-url.org'
    }
    update_object_data = {
        'abbreviation': 'TS1',
        'type': 'article',
        'title': 'Updated Test Source',
        'url': 'https://www.updated-url.org'
    }

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        author_1_data = {'last_names': 'Test Author', 'first_names': 'One'}
        author_2_data = {'last_names': 'Test Author', 'first_names': 'Two'}
        author_1 = Author.objects.create(**author_1_data)
        author_2 = Author.objects.create(**author_2_data)
        cls.source_author_1 = SourceAuthor.objects.create(
            source=cls.published_object,
            author=author_1,
            position=1
        )
        cls.source_author_2 = SourceAuthor.objects.create(
            source=cls.published_object,
            author=author_2,
            position=2
        )
        cls.source_author_3 = SourceAuthor.objects.create(
            source=cls.unpublished_object,
            author=author_1,
            position=1
        )
        cls.source_author_4 = SourceAuthor.objects.create(
            source=cls.unpublished_object,
            author=author_2,
            position=2)

    def related_objects_post_data(self):
        return {
            'sourceauthors-TOTAL_FORMS': 2,
            'sourceauthors-INITIAL_FORMS': 0,
            'sourceauthors-0-id': '',
            'sourceauthors-0-source': '',
            'sourceauthors-0-author': self.source_author_1.author.pk,
            'sourceauthors-1-id': '',
            'sourceauthors-1-source': '',
            'sourceauthors-1-author': self.source_author_2.author.pk
        }

    def test_detail_view_unpublished_contains_check_url_button_for_owner(self):
        self.client.force_login(self.owner_user)
        response = self.client.get(self.get_detail_url(self.unpublished_object.pk))
        self.assertContains(response, 'check url')

    def test_detail_view_published_contains_check_url_button_for_owner(self):
        self.client.force_login(self.owner_user)
        response = self.client.get(self.get_detail_url(self.published_object.pk))
        self.assertContains(response, 'check url')

    def test_detail_view_published_doesnt_contain_check_url_button_for_anonymous(self):
        response = self.client.get(self.get_detail_url(self.published_object.pk))
        self.assertNotContains(response, 'check url')

    def test_detail_view_published_doesnt_contain_check_url_button_for_non_owner(self):
        self.client.force_login(self.non_owner_user)
        response = self.client.get(self.get_detail_url(self.published_object.pk))
        self.assertNotContains(response, 'check url')


class SourceModalDetailViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['view_source']

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        with mute_signals(post_save):
            cls.source = Source.objects.create(
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


class SourceModalUpdateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['change_source']

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        with mute_signals(post_save):
            cls.source = Source.objects.create(
                abbreviation='TS1',
                type='article',
                title='Test Source',
                publication_status='published',
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
        with mute_signals(post_save):
            response = self.client.post(reverse('source-update-modal', kwargs={'pk': self.source.pk}), data=data)
        self.assertRedirects(
            response,
            f"{reverse('source-detail', kwargs={'pk': self.source.pk})}",
            status_code=302,
            target_status_code=200
        )


class SourceModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['delete_source']

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        with mute_signals(post_save):
            cls.source = Source.objects.create(
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


@patch('bibliography.views.check_source_url.delay')
class SourceCheckUrlViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['change_source']

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        with mute_signals(post_save):
            cls.source = Source.objects.create(
                title='Test Source from the Web',
                abbreviation='WORKING',
                url='https://httpbin.org/status/200'
            )

    def test_get_http_302_redirect_to_login_for_anonymous(self, mock_check_task):
        mock_check_task.return_value = type('task', (object,), {'task_id': 'fake_task_id'})
        request_url = reverse('source-check-url', kwargs={'pk': self.source.pk})
        response = self.client.get(request_url, follow=True)
        self.assertRedirects(
            response,
            f"{reverse('auth_login')}?next={reverse('source-check-url', kwargs={'pk': self.source.pk})}",
            status_code=302,
            target_status_code=200
        )

    def test_get_http_403_forbidden_for_outsiders(self, mock_check_task):
        mock_check_task.return_value = type('task', (object,), {'task_id': 'fake_task_id'})
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('source-check-url', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self, mock_check_task):
        mock_check_task.return_value = type('task', (object,), {'task_id': 'fake_task_id'})
        self.client.force_login(self.member)
        response = self.client.get(reverse('source-check-url', kwargs={'pk': self.source.pk}))
        self.assertEqual(200, response.status_code)
        self.assertTrue(mock_check_task.called_with(self.source.pk))


@patch('bibliography.views.check_source_urls.delay')
class SourceListCheckUrlsViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['change_source']

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        with mute_signals(post_save):
            Source.objects.create(
                title='Test Source from the Web',
                abbreviation='WORKING',
                url='https://httpbin.org/status/200'
            )
            Source.objects.create(
                title='Test Source from the Web',
                abbreviation='NOTWORKING',
                url='https://httpbin.org/status/404'
            )
            Source.objects.create(
                title='Test Source from the Web',
                abbreviation='NOTWORKING',
                url='https://httpbin.org/status/404'
            )

    def test_get_http_302_redirect_to_login_for_anonymous(self, mock_check_task):
        mock_check_task.return_value = type('task', (object,), {'task_id': 'fake_task_id'})
        request_url = f"{reverse('source-list-check-urls')}?url_valid=False"
        response = self.client.get(request_url, follow=True)
        self.assertRedirects(response, f"{reverse('auth_login')}?next={request_url}", status_code=302)

    def test_get_http_403_forbidden_for_outsiders(self, mock_check_task):
        mock_check_task.return_value = type('task', (object,), {'task_id': 'fake_task_id'})
        self.client.force_login(self.outsider)
        request_url = f"{reverse('source-list-check-urls')}?url_valid=False"
        response = self.client.get(request_url)
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self, mock_check_task):
        mock_check_task.return_value = type('task', (object,), {'task_id': 'fake_task_id'})
        self.client.force_login(self.member)
        request_url = f"{reverse('source-list-check-urls')}?url_valid=False&page=1"
        response = self.client.get(request_url)
        self.assertEqual(200, response.status_code)
        self.assertTrue(mock_check_task.called_with(url_valid=False))
