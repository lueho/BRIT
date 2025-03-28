import json
from unittest.mock import patch
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory, TestCase

from ..views import FilteredListFileExportView


class DummyTask:
    @staticmethod
    def delay(file_format, filter_params):
        class DummyTaskResult:
            task_id = "dummy-task-id"

        return DummyTaskResult()


class DummyExportView(FilteredListFileExportView):
    task_function = DummyTask


class FilteredListFileExportViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='testuser', password='testpass')

    def test_login_required(self):
        """
        Verify that an unauthenticated user is redirected (HTTP 302) to the login page.
        """
        url = '/dummy-url?format=csv'
        request = self.factory.get(url)
        request.user = AnonymousUser()
        response = DummyExportView.as_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"{settings.LOGIN_URL}?next={quote(url)}", response['Location'])

    def test_missing_task_function(self):
        """
        Check that a view subclass without a defined task_function raises NotImplementedError.
        """

        class NoTaskExportView(FilteredListFileExportView):
            pass

        request = self.factory.get('/dummy-url?format=csv')
        request.user = self.user
        view = NoTaskExportView.as_view()
        with self.assertRaises(NotImplementedError):
            view(request)

    def test_get_filter_params_public(self):
        """
        Ensure that for public lists, 'page' is removed, list_type is popped,
        and publication_status is set to ['published'].
        """
        params = {
            'page': ['1'],
            'list_type': ['public'],
            'some_filter': ['value']
        }
        request = self.factory.get('/dummy-url')
        request.user = self.user
        view_instance = DummyExportView()
        result = view_instance.get_filter_params(request, params.copy())
        self.assertNotIn('page', result)
        self.assertEqual(result.get('publication_status'), ['published'])
        self.assertEqual(result.get('some_filter'), ['value'])
        self.assertNotIn('list_type', result)

    def test_get_filter_params_private(self):
        """
        Ensure that for private lists, the 'owner' filter is set to the current user's pk.
        """
        params = {
            'page': ['1'],
            'list_type': ['private'],
            'some_filter': ['value']
        }
        request = self.factory.get('/dummy-url')
        request.user = self.user
        view_instance = DummyExportView()
        result = view_instance.get_filter_params(request, params.copy())
        self.assertNotIn('page', result)
        self.assertEqual(result.get('owner'), [self.user.pk])
        self.assertNotIn('publication_status', result)
        self.assertEqual(result.get('some_filter'), ['value'])
        self.assertNotIn('list_type', result)

    def test_get_method_calls_task_function(self):
        """
        Test that a GET request correctly extracts parameters, processes filters,
        calls the task_function.delay, and returns a JSON response with a task_id.
        """
        # Build a URL with query parameters.
        params = {
            'format': ['csv'],
            'page': ['1'],
            'list_type': ['private'],
            'some_filter': ['value']
        }
        # Create a query string manually.
        query_string = '&'.join([f'{key}={value[0]}' for key, value in params.items()])
        request = self.factory.get(f'/dummy-url?{query_string}')
        request.user = self.user

        # Patch DummyTask.delay to inspect its call parameters.
        with patch.object(DummyTask, 'delay', wraps=DummyTask.delay) as mock_delay:
            response = DummyExportView.as_view()(request)
            # For private lists, get_filter_params should add owner and remove list_type/page.
            expected_filter_params = {
                'some_filter': ['value'],
                'owner': [self.user.pk]
            }
            # Check that the task was called with the expected file format and filter params.
            mock_delay.assert_called_once_with('csv', expected_filter_params)
            self.assertEqual(response.status_code, 200)
            response_data = json.loads(response.content)
            self.assertIn('task_id', response_data)
            self.assertEqual(response_data['task_id'], 'dummy-task-id')
