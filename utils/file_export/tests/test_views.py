import json
from unittest.mock import MagicMock, patch
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase

from ..views import (
    SESSION_KEY,
    ExportModalView,
    FilteredListFileExportProgressView,
    FilteredListFileExportView,
    GenericUserCreatedObjectExportView,
    SingleObjectFileExportView,
    _store_task_id,
)


class DummyTask:
    @staticmethod
    def delay(file_format, filter_params, export_context):
        class DummyTaskResult:
            task_id = "dummy-task-id"

        return DummyTaskResult()


class DummyExportView(FilteredListFileExportView):
    task_function = DummyTask


class FilteredListFileExportViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="testuser")

    def _make_request(self, url="/dummy-url", user=None):
        """Create a GET request with a real session attached."""
        request = self.factory.get(url)
        request.user = user or self.user
        request.session = SessionStore()
        return request

    def test_login_required(self):
        """Verify that an unauthenticated user is redirected (HTTP 302) to the login page."""
        url = "/dummy-url?format=csv"
        request = self.factory.get(url)
        request.user = AnonymousUser()
        response = DummyExportView.as_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"{settings.LOGIN_URL}?next={quote(url)}", response["Location"])

    def test_missing_task_function(self):
        """Check that a view subclass without a defined task_function raises NotImplementedError."""

        class NoTaskExportView(FilteredListFileExportView):
            pass

        request = self._make_request("/dummy-url?format=csv")
        view = NoTaskExportView.as_view()
        with self.assertRaises(NotImplementedError):
            view(request)

    def test_get_filter_params_public(self):
        """Ensure that for public lists, 'page' is removed and publication_status is set."""
        params = {"page": ["1"], "list_type": ["public"], "some_filter": ["value"]}
        request = self._make_request()
        view_instance = DummyExportView()
        result = view_instance.get_filter_params(request, params.copy())
        self.assertNotIn("page", result)
        self.assertEqual(result.get("publication_status"), ["published"])
        self.assertEqual(result.get("some_filter"), ["value"])
        self.assertNotIn("list_type", result)

    def test_get_filter_params_private(self):
        """Ensure that for private lists, the 'owner' filter is set to the current user's pk."""
        params = {"page": ["1"], "list_type": ["private"], "some_filter": ["value"]}
        request = self._make_request()
        view_instance = DummyExportView()
        result = view_instance.get_filter_params(request, params.copy())
        self.assertNotIn("page", result)
        self.assertEqual(result.get("owner"), [self.user.pk])
        self.assertNotIn("publication_status", result)
        self.assertEqual(result.get("some_filter"), ["value"])
        self.assertNotIn("list_type", result)

    def test_get_filter_params_defaults_to_published_when_no_list_type(self):
        """Verify default scoping when list_type is not provided."""
        params = {"some_filter": ["value"]}
        request = self._make_request()
        view_instance = DummyExportView()
        result = view_instance.get_filter_params(request, params.copy())
        self.assertEqual(result.get("publication_status"), ["published"])

    def test_get_defaults_format_to_csv(self):
        """Verify that omitting the format param defaults to csv."""
        request = self._make_request("/dummy-url?list_type=public")
        with patch.object(DummyTask, "delay", wraps=DummyTask.delay) as mock_delay:
            DummyExportView.as_view()(request)
            called_args, _ = mock_delay.call_args
            self.assertEqual(called_args[0], "csv")

    def test_get_passes_xlsx_format(self):
        """Verify that format=xlsx is forwarded to the task."""
        request = self._make_request("/dummy-url?format=xlsx&list_type=public")
        with patch.object(DummyTask, "delay", wraps=DummyTask.delay) as mock_delay:
            DummyExportView.as_view()(request)
            called_args, _ = mock_delay.call_args
            self.assertEqual(called_args[0], "xlsx")

    def test_get_method_calls_task_function(self):
        params = {"page": ["1"], "list_type": ["private"], "some_filter": ["value"]}
        query_string = "&".join([f"{key}={value[0]}" for key, value in params.items()])
        request = self._make_request(f"/dummy-url?{query_string}")
        with patch.object(DummyTask, "delay", wraps=DummyTask.delay) as mock_delay:
            response = DummyExportView.as_view()(request)
            expected_filter_params = {"some_filter": ["value"], "owner": [self.user.pk]}
            mock_delay.assert_called_once()
            called_args, _ = mock_delay.call_args
            self.assertEqual(called_args[0], "csv")
            self.assertEqual(called_args[1], expected_filter_params)
            self.assertEqual(len(called_args), 3)
            self.assertIsInstance(called_args[2], dict)
            self.assertIn("user_id", called_args[2])
            self.assertIn("list_type", called_args[2])
            self.assertEqual(response.status_code, 200)
            response_data = json.loads(response.content)
            self.assertIn("task_id", response_data)
            self.assertEqual(response_data["task_id"], "dummy-task-id")

    def test_get_stores_task_id_in_session(self):
        """Verify the dispatched task ID is persisted in the session."""
        request = self._make_request("/dummy-url?list_type=public")
        DummyExportView.as_view()(request)
        self.assertIn("dummy-task-id", request.session.get(SESSION_KEY, []))


class StoreTaskIdTests(TestCase):
    """Tests for the _store_task_id helper."""

    def test_appends_task_id_to_session(self):
        request = MagicMock()
        session = SessionStore()
        request.session = session
        _store_task_id(request, "task-1")
        _store_task_id(request, "task-2")
        self.assertEqual(session[SESSION_KEY], ["task-1", "task-2"])

    def test_noop_when_session_is_none(self):
        request = MagicMock(spec=[])
        request.session = None
        _store_task_id(request, "task-1")  # should not raise


class SingleObjectFileExportViewTests(TestCase):
    """Tests for SingleObjectFileExportView."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="testuser")

    def test_missing_task_function_raises_not_implemented(self):
        class NoTaskView(SingleObjectFileExportView):
            model = User

            def get_queryset(self):
                return User.objects.all()

        request = self.factory.get("/dummy/")
        request.user = self.user
        request.session = SessionStore()
        with self.assertRaises(NotImplementedError):
            NoTaskView.as_view()(request, pk=self.user.pk)

    def test_dispatches_task_and_returns_task_id(self):
        mock_task = MagicMock()
        mock_task.delay.return_value = MagicMock(task_id="single-obj-task-id")

        class TaskView(SingleObjectFileExportView):
            model = User
            task_function = mock_task

            def get_queryset(self):
                return User.objects.all()

        request = self.factory.get("/dummy/")
        request.user = self.user
        request.session = SessionStore()
        response = TaskView.as_view()(request, pk=self.user.pk)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["task_id"], "single-obj-task-id")
        mock_task.delay.assert_called_once_with(self.user.pk)

    def test_login_required(self):
        mock_task = MagicMock()

        class TaskView(SingleObjectFileExportView):
            model = User
            task_function = mock_task

        request = self.factory.get("/dummy/")
        request.user = AnonymousUser()
        response = TaskView.as_view()(request, pk=1)
        self.assertEqual(response.status_code, 302)


class GenericUserCreatedObjectExportViewTests(TestCase):
    """Tests for GenericUserCreatedObjectExportView."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="testuser")

    def test_missing_model_label_raises_not_implemented(self):
        class NoLabelView(GenericUserCreatedObjectExportView):
            pass

        request = self.factory.get("/dummy/?format=csv&list_type=public")
        request.user = self.user
        request.session = SessionStore()
        with self.assertRaises(NotImplementedError):
            NoLabelView.as_view()(request)

    def test_dispatches_generic_task(self):
        class LabelView(GenericUserCreatedObjectExportView):
            model_label = "auth.User"

        request = self.factory.get("/dummy/?format=xlsx&list_type=public")
        request.user = self.user
        request.session = SessionStore()

        # The view imports the task inside get() from .generic_tasks
        with patch(
            "utils.file_export.generic_tasks.export_user_created_object_to_file"
        ) as mock_task:
            mock_task.delay.return_value = MagicMock(task_id="generic-task-id")
            response = LabelView.as_view()(request)
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.content)
            self.assertEqual(data["task_id"], "generic-task-id")
            mock_task.delay.assert_called_once()
            call_args, _ = mock_task.delay.call_args
            self.assertEqual(call_args[0], "auth.User")
            self.assertEqual(call_args[1], "xlsx")


class ExportModalViewTests(TestCase):
    """Tests for ExportModalView."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="testuser")

    def test_login_required(self):
        request = self.factory.get("/export-modal/")
        request.user = AnonymousUser()
        response = ExportModalView.as_view()(request)
        self.assertEqual(response.status_code, 302)

    def test_passes_export_url_to_context(self):
        request = self.factory.get("/export-modal/?export_url=/some/export/")
        request.user = self.user
        view = ExportModalView()
        view.request = request
        view.kwargs = {}
        context = view.get_context_data()
        self.assertEqual(context["export_url"], "/some/export/")

    def test_passes_extra_params_to_context(self):
        request = self.factory.get("/export-modal/?export_url=/x/&foo=bar&baz=qux")
        request.user = self.user
        view = ExportModalView()
        view.request = request
        view.kwargs = {}
        context = view.get_context_data()
        self.assertEqual(context["foo"], "bar")
        self.assertEqual(context["baz"], "qux")
        self.assertNotIn("export_url_extra", context)


class FilteredListFileExportProgressViewTests(TestCase):
    """Tests for the progress-polling view with mocked AsyncResult."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="testuser")

    def _make_request(self, task_id, session_task_ids=None):
        request = self.factory.get(f"/tasks/{task_id}/progress/")
        request.user = self.user
        request.session = SessionStore()
        if session_task_ids:
            request.session[SESSION_KEY] = list(session_task_ids)
            request.session.save()
        return request

    def test_denies_access_for_unknown_task_id(self):
        request = self._make_request("unknown-task", session_task_ids=["other-task"])
        response = FilteredListFileExportProgressView.as_view()(
            request, task_id="unknown-task"
        )
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertEqual(data["state"], "DENIED")

    def test_denies_access_when_session_has_no_tasks(self):
        request = self._make_request("any-task")
        response = FilteredListFileExportProgressView.as_view()(
            request, task_id="any-task"
        )
        self.assertEqual(response.status_code, 403)

    @patch("utils.file_export.views.AsyncResult")
    def test_returns_progress_state(self, mock_async_result_cls):
        mock_result = MagicMock()
        mock_result.state = "PROGRESS"
        mock_result.info = {"current": 25, "total": 100, "percent": 25}
        mock_async_result_cls.return_value = mock_result

        request = self._make_request("task-123", session_task_ids=["task-123"])
        response = FilteredListFileExportProgressView.as_view()(
            request, task_id="task-123"
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["state"], "PROGRESS")
        self.assertEqual(data["details"]["percent"], 25)

    @patch("utils.file_export.views.AsyncResult")
    def test_cleans_up_session_on_success(self, mock_async_result_cls):
        mock_result = MagicMock()
        mock_result.state = "SUCCESS"
        mock_result.info = "https://example.com/file.csv"
        mock_async_result_cls.return_value = mock_result

        request = self._make_request(
            "task-done", session_task_ids=["task-done", "task-other"]
        )
        response = FilteredListFileExportProgressView.as_view()(
            request, task_id="task-done"
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["state"], "SUCCESS")
        self.assertNotIn("task-done", request.session.get(SESSION_KEY, []))
        self.assertIn("task-other", request.session.get(SESSION_KEY, []))

    @patch("utils.file_export.views.AsyncResult")
    def test_cleans_up_session_on_failure(self, mock_async_result_cls):
        mock_result = MagicMock()
        mock_result.state = "FAILURE"
        mock_result.info = ValueError("Something broke")
        mock_async_result_cls.return_value = mock_result

        request = self._make_request("task-fail", session_task_ids=["task-fail"])
        response = FilteredListFileExportProgressView.as_view()(
            request, task_id="task-fail"
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["state"], "FAILURE")
        self.assertIn("error", data["details"])
        self.assertIn("Something broke", data["details"]["error"])
        self.assertEqual(request.session.get(SESSION_KEY, []), [])
