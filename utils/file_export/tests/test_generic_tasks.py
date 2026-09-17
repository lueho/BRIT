"""Tests for utils.file_export.generic_tasks."""

import logging
from collections import OrderedDict, namedtuple
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase

from ..generic_tasks import BATCH_SIZE, export_user_created_object_to_file


class DummyFilterSet:
    """Minimal filterset stand-in that passes through the queryset unchanged."""

    def __init__(self, data, queryset):
        self.qs = queryset


class DummySerializer:
    """Minimal serializer stand-in that returns dicts with a pk key."""

    def __init__(self, instances, many=False):
        self.data = [OrderedDict({"pk": obj.pk}) for obj in instances]


TaskExportSpec = namedtuple(
    "TaskExportSpec", ["model", "filterset", "serializer", "renderers"]
)


@contextmanager
def silence_export_task_logging():
    """Silence expected export-task error logs.

    These unit tests mock ``write_file_for_download``, so the export file is
    never written and the task's file-size lookup raises an expected error.
    That error is handled gracefully; suppressing it keeps the test output
    clean without hiding genuine failures (assertions still catch those).
    """
    logger = logging.getLogger("utils.file_export.generic_tasks")
    handler = logging.NullHandler()
    original_level = logger.level
    original_propagate = logger.propagate
    logger.addHandler(handler)
    logger.propagate = False
    logger.setLevel(logging.CRITICAL)
    try:
        yield
    finally:
        logger.removeHandler(handler)
        logger.setLevel(original_level)
        logger.propagate = original_propagate


class ExportTaskTestCase(TestCase):
    """Tests for export_user_created_object_to_file."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="export_owner")
        cls.other = User.objects.create_user(username="export_other")

    def _run_task(self, model_label, file_format, query_params, context):
        """Invoke the task's run() with a mock self and return (result, mock_self)."""
        mock_self = MagicMock()
        mock_self.request.id = "fake-request-id"
        run_fn = export_user_created_object_to_file.run.__func__
        with silence_export_task_logging():
            result = run_fn(mock_self, model_label, file_format, query_params, context)
        return result, mock_self

    def _make_spec(self, model=User):
        """Build a task export spec using User as the model."""
        return TaskExportSpec(
            model=model,
            filterset=DummyFilterSet,
            serializer=DummySerializer,
            renderers={"csv": MagicMock(), "xlsx": MagicMock()},
        )

    @patch(
        "utils.file_export.generic_tasks.utils.file_export.storages.write_file_for_download"
    )
    @patch("utils.file_export.generic_tasks.get_export_spec")
    def test_public_scope_returns_all_for_model_without_publication_status(
        self, mock_get_spec, mock_write
    ):
        """User model has no publication_status, so public scope should return all."""
        spec = self._make_spec()
        mock_get_spec.return_value = spec
        mock_write.return_value = "https://example.com/file.csv"

        result, _mock_self = self._run_task(
            "auth.User", "csv", {}, {"user_id": self.owner.pk, "list_type": "public"}
        )

        self.assertEqual(result, "https://example.com/file.csv")
        mock_write.assert_called_once()
        call_args, _ = mock_write.call_args
        self.assertEqual(call_args[0], "user_fake-request-id.csv")

    @patch(
        "utils.file_export.generic_tasks.utils.file_export.storages.write_file_for_download"
    )
    @patch("utils.file_export.generic_tasks.get_export_spec")
    def test_private_scope_filters_by_owner(self, mock_get_spec, mock_write):
        """Private scope should filter by owner_id."""
        mock_model = MagicMock()
        mock_qs = MagicMock()
        mock_model.objects.filter.return_value = mock_qs
        mock_model._meta.get_fields.return_value = []
        mock_model._meta.model_name = "mockmodel"

        mock_filtered = MagicMock()
        mock_filtered.qs = mock_qs
        mock_qs.count.return_value = 0

        spec = TaskExportSpec(
            model=mock_model,
            filterset=lambda data, queryset: mock_filtered,
            serializer=DummySerializer,
            renderers={"csv": MagicMock()},
        )
        mock_get_spec.return_value = spec
        mock_write.return_value = "url"

        self._run_task("test.Model", "csv", {}, {"user_id": 42, "list_type": "private"})

        mock_model.objects.filter.assert_called_once_with(owner_id=42)

    @patch(
        "utils.file_export.generic_tasks.utils.file_export.storages.write_file_for_download"
    )
    @patch("utils.file_export.generic_tasks.apply_scope_filter")
    @patch("utils.file_export.generic_tasks.filter_queryset_for_user")
    @patch("utils.file_export.generic_tasks.get_export_spec")
    def test_models_with_publication_status_use_visibility_helpers(
        self,
        mock_get_spec,
        mock_filter_queryset_for_user,
        mock_apply_scope_filter,
        mock_write,
    ):
        """Models with publication_status must use centralized visibility helpers."""
        mock_model = MagicMock()
        publication_field = MagicMock()
        publication_field.name = "publication_status"
        mock_model._meta.get_fields.return_value = [publication_field]
        mock_model._meta.model_name = "mockmodel"

        all_qs = MagicMock()
        visible_qs = MagicMock()
        scoped_qs = MagicMock()
        scoped_qs.count.return_value = 0

        mock_model.objects.all.return_value = all_qs
        mock_filter_queryset_for_user.return_value = visible_qs
        mock_apply_scope_filter.return_value = scoped_qs

        mock_filtered = MagicMock()
        mock_filtered.qs = scoped_qs

        spec = TaskExportSpec(
            model=mock_model,
            filterset=lambda data, queryset: mock_filtered,
            serializer=DummySerializer,
            renderers={"csv": MagicMock()},
        )
        mock_get_spec.return_value = spec
        mock_write.return_value = "url"

        self._run_task(
            "test.Model", "csv", {}, {"user_id": self.owner.pk, "list_type": "review"}
        )

        mock_model.objects.all.assert_called_once_with()
        mock_filter_queryset_for_user.assert_called_once()
        filter_user = mock_filter_queryset_for_user.call_args.args[1]
        self.assertEqual(filter_user.pk, self.owner.pk)

        mock_apply_scope_filter.assert_called_once()
        apply_scope_user = mock_apply_scope_filter.call_args.kwargs["user"]
        self.assertEqual(apply_scope_user.pk, self.owner.pk)
        self.assertEqual(mock_apply_scope_filter.call_args.args[1], "review")

        mock_model.objects.filter.assert_not_called()

    @patch(
        "utils.file_export.generic_tasks.utils.file_export.storages.write_file_for_download"
    )
    @patch("utils.file_export.generic_tasks.get_export_spec")
    def test_review_scope_returns_empty_for_model_without_publication_status(
        self, mock_get_spec, mock_write
    ):
        """Review scope on a model without publication_status should yield empty qs."""
        spec = self._make_spec()
        mock_get_spec.return_value = spec
        mock_write.return_value = "https://example.com/file.csv"

        _, _mock_self = self._run_task(
            "auth.User", "csv", {}, {"user_id": self.owner.pk, "list_type": "review"}
        )

        call_args, _ = mock_write.call_args
        data = call_args[1]
        self.assertEqual(data, [])

    @patch(
        "utils.file_export.generic_tasks.utils.file_export.storages.write_file_for_download"
    )
    @patch("utils.file_export.generic_tasks.get_export_spec")
    def test_reports_initial_progress_with_zero(self, mock_get_spec, mock_write):
        """Task should report initial progress with current=0."""
        spec = self._make_spec()
        mock_get_spec.return_value = spec
        mock_write.return_value = "url"

        _, mock_self = self._run_task(
            "auth.User", "csv", {}, {"user_id": self.owner.pk, "list_type": "public"}
        )

        first_call = mock_self.update_state.call_args_list[0]
        self.assertEqual(first_call[1]["state"], "PROGRESS")
        self.assertEqual(first_call[1]["meta"]["current"], 0)
        self.assertEqual(first_call[1]["meta"]["percent"], 0)

    @patch(
        "utils.file_export.generic_tasks.utils.file_export.storages.write_file_for_download"
    )
    @patch("utils.file_export.generic_tasks.get_export_spec")
    def test_empty_queryset_reports_progress_correctly(self, mock_get_spec, mock_write):
        """Empty queryset should report initial progress and not enter the batch loop."""
        spec = self._make_spec()
        mock_get_spec.return_value = spec
        mock_write.return_value = "url"

        _, mock_self = self._run_task(
            "auth.User", "csv", {}, {"user_id": self.owner.pk, "list_type": "review"}
        )

        mock_self.update_state.assert_called_once_with(
            state="PROGRESS", meta={"current": 0, "total": 0, "percent": 0}
        )

    @patch(
        "utils.file_export.generic_tasks.utils.file_export.storages.write_file_for_download"
    )
    @patch("utils.file_export.generic_tasks.get_export_spec")
    def test_uses_correct_renderer_for_format(self, mock_get_spec, mock_write):
        """Task should select the renderer matching the requested format."""
        spec = self._make_spec()
        mock_get_spec.return_value = spec
        mock_write.return_value = "url"

        _, _mock_self = self._run_task(
            "auth.User", "xlsx", {}, {"user_id": self.owner.pk, "list_type": "public"}
        )

        call_args, _ = mock_write.call_args
        self.assertIs(call_args[2], spec.renderers["xlsx"])
        self.assertTrue(call_args[0].endswith(".xlsx"))

    @patch(
        "utils.file_export.generic_tasks.utils.file_export.storages.write_file_for_download"
    )
    @patch("utils.file_export.generic_tasks.get_export_spec")
    def test_batch_progress_reporting(self, mock_get_spec, mock_write):
        """Verify progress is reported for each batch when total > BATCH_SIZE."""
        users_needed = BATCH_SIZE + 10
        existing = User.objects.count()
        for i in range(users_needed - existing):
            User.objects.create_user(username=f"batch_user_{i}")

        spec = self._make_spec()
        mock_get_spec.return_value = spec
        mock_write.return_value = "url"

        _, mock_self = self._run_task(
            "auth.User", "csv", {}, {"user_id": self.owner.pk, "list_type": "public"}
        )

        total = User.objects.count()
        expected_calls = 1 + ((total + BATCH_SIZE - 1) // BATCH_SIZE)
        self.assertEqual(mock_self.update_state.call_count, expected_calls)

        last_call = mock_self.update_state.call_args_list[-1]
        self.assertEqual(last_call[1]["meta"]["percent"], 100)
        self.assertEqual(last_call[1]["meta"]["current"], total)
