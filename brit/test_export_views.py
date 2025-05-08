import json
from urllib.parse import quote
from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory, TestCase
from brit.export_views import BritFilteredListFileExportView

class DummyTask:
    @staticmethod
    def delay(file_format, filter_params, export_context):
        class DummyTaskResult:
            task_id = "dummy-task-id"
        return DummyTaskResult()

class DummyExportView(BritFilteredListFileExportView):
    task_function = DummyTask

class BritFilteredListFileExportViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="testuser", password="testpass")

    def test_login_required(self):
        url = "/dummy-url?format=csv"
        request = self.factory.get(url)
        request.user = AnonymousUser()
        response = DummyExportView.as_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"{settings.LOGIN_URL}?next={quote(url)}", response["Location"])

    def test_get_filter_params_public(self):
        params = {"page": ["1"], "list_type": ["public"], "some_filter": ["value"]}
        request = self.factory.get("/dummy-url")
        request.user = self.user
        view_instance = DummyExportView()
        result = view_instance.get_filter_params(request, params.copy())
        self.assertNotIn("page", result)
        self.assertEqual(result.get("publication_status"), ["published"])
        self.assertEqual(result.get("some_filter"), ["value"])
        self.assertNotIn("list_type", result)

    def test_get_filter_params_private(self):
        params = {"page": ["1"], "list_type": ["private"], "some_filter": ["value"]}
        request = self.factory.get("/dummy-url")
        request.user = self.user
        view_instance = DummyExportView()
        result = view_instance.get_filter_params(request, params.copy())
        self.assertNotIn("page", result)
        self.assertEqual(result.get("owner"), [self.user.pk])
        self.assertNotIn("publication_status", result)
        self.assertEqual(result.get("some_filter"), ["value"])
        self.assertNotIn("list_type", result)

    def test_get_export_context(self):
        params = {"list_type": ["private"]}
        request = self.factory.get("/dummy-url")
        request.user = self.user
        view_instance = DummyExportView()
        context = view_instance.get_export_context(request, params.copy())
        self.assertEqual(context["user_id"], self.user.pk)
        self.assertEqual(context["list_type"], "private")

    def test_get_method_calls_task_function(self):
        params = {"page": ["1"], "list_type": ["private"], "some_filter": ["value"]}
        query_string = "&".join([f"{key}={value[0]}" for key, value in params.items()])
        request = self.factory.get(f"/dummy-url?{query_string}")
        request.user = self.user
        response = DummyExportView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertIn("task_id", response_data)
        self.assertEqual(response_data["task_id"], "dummy-task-id")
