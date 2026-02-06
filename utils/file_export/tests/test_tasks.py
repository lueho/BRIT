from collections import OrderedDict, namedtuple
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


ExportSpec = namedtuple("ExportSpec", ["model", "filterset", "serializer", "renderers"])


class ExportTaskTestCase(TestCase):
    """Tests for export_user_created_object_to_file.

    Because the task uses ``@shared_task(bind=True)``, Celery injects ``self``
    automatically via ``__call__``.  We bypass that by calling ``.run()``
    directly with a ``MagicMock`` as the ``self`` argument, giving us full
    control over ``update_state`` and ``request.id``.
    """

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="export_owner")
        cls.other = User.objects.create_user(username="export_other")

    def _run_task(self, model_label, file_format, query_params, context):
        """Invoke the task's run() with a mock self and return (result, mock_self).

        ``run`` is a bound method on the Task instance, so we use ``__func__``
        to access the raw function and pass our own mock as ``self``.
        """
        mock_self = MagicMock()
        mock_self.request.id = "fake-request-id"
        run_fn = export_user_created_object_to_file.run.__func__
        result = run_fn(mock_self, model_label, file_format, query_params, context)
        return result, mock_self

    def _make_spec(self, model=User):
        """Build an ExportSpec using User as the model (no publication_status field)."""
        return ExportSpec(
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

        result, mock_self = self._run_task(
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
        """Private scope should filter by owner_id.

        We use a mock model whose manager supports filter(owner_id=...) because
        the generic User model has no owner_id field.
        """
        mock_model = MagicMock()
        mock_qs = MagicMock()
        mock_model.objects.filter.return_value = mock_qs
        mock_model._meta.get_fields.return_value = []
        mock_model._meta.model_name = "mockmodel"

        # Make the filterset pass-through
        mock_filtered = MagicMock()
        mock_filtered.qs = mock_qs
        mock_qs.count.return_value = 0

        spec = ExportSpec(
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
    @patch("utils.file_export.generic_tasks.get_export_spec")
    def test_review_scope_returns_empty_for_model_without_publication_status(
        self, mock_get_spec, mock_write
    ):
        """Review scope on a model without publication_status should yield empty qs."""
        spec = self._make_spec()
        mock_get_spec.return_value = spec
        mock_write.return_value = "https://example.com/file.csv"

        _, mock_self = self._run_task(
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

        # Only the initial progress call, no batch calls
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

        _, mock_self = self._run_task(
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
        # initial call + ceil(total / BATCH_SIZE) batch calls
        expected_calls = 1 + ((total + BATCH_SIZE - 1) // BATCH_SIZE)
        self.assertEqual(mock_self.update_state.call_count, expected_calls)

        # Last batch call should report 100%
        last_call = mock_self.update_state.call_args_list[-1]
        self.assertEqual(last_call[1]["meta"]["percent"], 100)
        self.assertEqual(last_call[1]["meta"]["current"], total)
