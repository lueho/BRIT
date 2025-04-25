from unittest.mock import patch

from django.db.models.signals import post_save
from django.urls import reverse
from factory.django import mute_signals

from utils.tests.testcases import AbstractTestCases, ViewWithPermissionsTestCase
from ..models import Author, Licence, Source, SourceAuthor


# ----------- Author CRUD ---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AuthorCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    modal_detail_view = True
    modal_update_view = True
    modal_create_view = True

    model = Author

    view_dashboard_name = 'bibliography-dashboard'
    view_create_name = 'author-create'
    view_modal_create_name = 'author-create-modal'
    view_published_list_name = 'author-list'
    view_private_list_name = 'author-list-owned'
    view_detail_name = 'author-detail'
    view_modal_detail_name = 'author-detail-modal'
    view_update_name = 'author-update'
    view_modal_update_name = 'author-update-modal'
    view_delete_name = 'author-delete-modal'

    create_object_data = {'last_names': 'Test Author'}
    update_object_data = {'last_names': 'Updated Author'}


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


class LicenceCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    modal_detail_view = True
    modal_update_view = True
    modal_create_view = True

    model = Licence

    view_dashboard_name = 'bibliography-dashboard'
    view_create_name = 'licence-create'
    view_modal_create_name = 'licence-create-modal'
    view_published_list_name = 'licence-list'
    view_private_list_name = 'licence-list-owned'
    view_detail_name = 'licence-detail'
    view_modal_detail_name = 'licence-detail-modal'
    view_update_name = 'licence-update'
    view_modal_update_name = 'licence-update-modal'
    view_delete_name = 'licence-delete-modal'

    create_object_data = {'name': 'Test Licence'}
    update_object_data = {'name': 'Updated Test Licence'}


# ----------- Source CRUD ----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class SourceCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    modal_detail_view = True
    modal_create_view = True

    model = Source

    view_dashboard_name = 'bibliography-dashboard'
    view_create_name = 'source-create'
    view_modal_create_name = 'source-create-modal'
    view_published_list_name = 'source-list'
    view_private_list_name = 'source-list-owned'
    view_detail_name = 'source-detail'
    view_modal_detail_name = 'source-detail-modal'
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
