import json
from unittest.mock import patch
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory, TestCase

from ..views import BaseFileExportView


class DummyTask:
    @staticmethod
    def delay(file_format, filter_params, export_context):
        class DummyTaskResult:
            task_id = "dummy-task-id"

        return DummyTaskResult()


class DummyExportView(BaseFileExportView):
    task_function = DummyTask


class BaseFileExportViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="testuser", password="testpass")



    def test_missing_task_function(self):
        """
        Check that a view subclass without a defined task_function raises NotImplementedError.
        """

        class NoTaskExportView(BaseFileExportView):
            pass

        request = self.factory.get("/dummy-url?format=csv")
        request.user = self.user
        view = NoTaskExportView.as_view()
        with self.assertRaises(NotImplementedError):
            view(request)

    def test_get_filter_params_is_noop(self):
        """
        By default, get_filter_params returns params unchanged.
        """
        params = {"foo": ["bar"]}
        request = self.factory.get("/dummy-url")
        request.user = self.user
        view_instance = DummyExportView()
        result = view_instance.get_filter_params(request, params.copy())
        self.assertEqual(result, params)





    def test_get_method_calls_task_function(self):
        params = {"foo": ["bar"]}
        query_string = "&".join([f"{key}={value[0]}" for key, value in params.items()])
        request = self.factory.get(f"/dummy-url?{query_string}")
        request.user = self.user
        with patch.object(DummyTask, "delay", wraps=DummyTask.delay) as mock_delay:
            response = DummyExportView.as_view()(request)
            mock_delay.assert_called_once()
            called_args, _ = mock_delay.call_args
            self.assertEqual(called_args[0], "csv")
            self.assertEqual(called_args[1], params)
            self.assertEqual(len(called_args), 3)
            self.assertIsInstance(called_args[2], dict)
            self.assertEqual(response.status_code, 200)
            response_data = json.loads(response.content)
            self.assertIn("task_id", response_data)
            self.assertEqual(response_data["task_id"], "dummy-task-id")

