from collections import OrderedDict, namedtuple
from datetime import timedelta
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ..generic_tasks import cleanup_expired_exports, export_user_created_object_to_file
from ..models import UserExport
from ..storages import get_file_export_storage

TaskExportSpec = namedtuple(
    "TaskExportSpec", ["model", "filterset", "serializer", "renderers"]
)


class DummyFilterSet:
    def __init__(self, data, queryset):
        self.qs = queryset


class DummySerializer:
    def __init__(self, instances, many=False):
        self.data = [OrderedDict({"pk": obj.pk}) for obj in instances]


class UserExportModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="export_owner")

    @override_settings(FILE_EXPORT_RETENTION_DAYS=5)
    def test_expires_at_defaults_to_retention_period(self):
        before = timezone.now()
        export = UserExport.objects.create(
            owner=self.owner,
            model_label="auth.User",
            file_format="csv",
            file_name="user_test.csv",
        )
        self.assertGreaterEqual(export.expires_at, before + timedelta(days=5))
        self.assertLessEqual(export.expires_at, timezone.now() + timedelta(days=5))
        self.assertFalse(export.is_expired)

    def test_is_expired(self):
        export = UserExport.objects.create(
            owner=self.owner,
            model_label="auth.User",
            file_format="csv",
            file_name="user_test.csv",
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.assertTrue(export.is_expired)

    def test_active_and_expired_querysets(self):
        active = UserExport.objects.create(
            owner=self.owner,
            model_label="auth.User",
            file_format="csv",
            file_name="active.csv",
        )
        expired = UserExport.objects.create(
            owner=self.owner,
            model_label="auth.User",
            file_format="csv",
            file_name="expired.csv",
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.assertEqual(list(UserExport.objects.active()), [active])
        self.assertEqual(list(UserExport.objects.expired()), [expired])


class ExportTaskRecordTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="export_owner")

    def _run_task(self, model_label, file_format, query_params, context):
        mock_self = MagicMock()
        mock_self.request.id = "fake-request-id"
        run_fn = export_user_created_object_to_file.run.__func__
        result = run_fn(mock_self, model_label, file_format, query_params, context)
        return result, mock_self

    def _make_spec(self):
        return TaskExportSpec(
            model=User,
            filterset=DummyFilterSet,
            serializer=DummySerializer,
            renderers={"csv": MagicMock(), "xlsx": MagicMock()},
        )

    @patch("utils.file_export.generic_tasks.get_export_spec")
    def test_task_creates_user_export_record_with_metadata(self, mock_get_spec):
        mock_get_spec.return_value = self._make_spec()
        with TemporaryDirectory() as tmpdir:
            with override_settings(
                FILE_EXPORT_USE_LOCAL_STORAGE=True,
                MEDIA_ROOT=tmpdir,
                MEDIA_URL="/media/",
            ):
                self._run_task(
                    "auth.User",
                    "csv",
                    {"some_filter": ["value"]},
                    {"user_id": self.owner.pk, "list_type": "public"},
                )

                export = UserExport.objects.get(owner=self.owner)
                self.assertEqual(export.model_label, "auth.User")
                self.assertEqual(export.file_format, "csv")
                self.assertEqual(export.file_name, "user_fake-request-id.csv")
                self.assertEqual(export.task_id, "fake-request-id")
                self.assertEqual(export.row_count, User.objects.count())
                self.assertEqual(export.filter_params, {"some_filter": ["value"]})
                self.assertIsNotNone(export.expires_at)

    @patch("utils.file_export.generic_tasks.get_export_spec")
    def test_task_without_user_creates_no_record(self, mock_get_spec):
        mock_get_spec.return_value = self._make_spec()
        with TemporaryDirectory() as tmpdir:
            with override_settings(
                FILE_EXPORT_USE_LOCAL_STORAGE=True,
                MEDIA_ROOT=tmpdir,
                MEDIA_URL="/media/",
            ):
                self._run_task("auth.User", "csv", {}, {"list_type": "public"})
                self.assertFalse(UserExport.objects.exists())

    @patch("utils.file_export.generic_tasks.get_export_spec")
    def test_task_removes_expired_exports_opportunistically(self, mock_get_spec):
        mock_get_spec.return_value = self._make_spec()
        with TemporaryDirectory() as tmpdir:
            with override_settings(
                FILE_EXPORT_USE_LOCAL_STORAGE=True,
                MEDIA_ROOT=tmpdir,
                MEDIA_URL="/media/",
            ):
                expired = UserExport.objects.create(
                    owner=self.owner,
                    model_label="auth.User",
                    file_format="csv",
                    file_name="old.csv",
                    expires_at=timezone.now() - timedelta(minutes=1),
                )
                self._run_task(
                    "auth.User",
                    "csv",
                    {},
                    {"user_id": self.owner.pk, "list_type": "public"},
                )
                self.assertFalse(UserExport.objects.filter(pk=expired.pk).exists())


class CleanupExpiredExportsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="export_owner")

    def test_cleanup_deletes_expired_files_and_records(self):
        with TemporaryDirectory() as tmpdir:
            with override_settings(
                FILE_EXPORT_USE_LOCAL_STORAGE=True,
                MEDIA_ROOT=tmpdir,
                MEDIA_URL="/media/",
            ):
                storage = get_file_export_storage()
                with storage.open("expired.csv", "wb") as f:
                    f.write(b"data")
                with storage.open("fresh.csv", "wb") as f:
                    f.write(b"data")

                UserExport.objects.create(
                    owner=self.owner,
                    model_label="auth.User",
                    file_format="csv",
                    file_name="expired.csv",
                    expires_at=timezone.now() - timedelta(minutes=1),
                )
                fresh = UserExport.objects.create(
                    owner=self.owner,
                    model_label="auth.User",
                    file_format="csv",
                    file_name="fresh.csv",
                )

                deleted = cleanup_expired_exports.run()

                self.assertEqual(deleted, 1)
                self.assertEqual(list(UserExport.objects.all()), [fresh])
                self.assertFalse(storage.exists("expired.csv"))
                self.assertTrue(storage.exists("fresh.csv"))


class UserExportListViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="export_owner")
        cls.other = User.objects.create_user(username="export_other")
        cls.own_export = UserExport.objects.create(
            owner=cls.owner,
            model_label="auth.User",
            file_format="csv",
            file_name="own.csv",
        )
        cls.expired_export = UserExport.objects.create(
            owner=cls.owner,
            model_label="auth.User",
            file_format="csv",
            file_name="expired.csv",
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        cls.foreign_export = UserExport.objects.create(
            owner=cls.other,
            model_label="auth.User",
            file_format="csv",
            file_name="foreign.csv",
        )
        cls.url = reverse("user-export-list")

    def test_login_required(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_lists_only_own_active_exports(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        exports = list(response.context["object_list"])
        self.assertEqual(exports, [self.own_export])

    def test_profile_links_to_exports(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("user_profile"))
        self.assertContains(response, self.url)


class UserExportDownloadViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="export_owner")
        cls.other = User.objects.create_user(username="export_other")
        cls.export = UserExport.objects.create(
            owner=cls.owner,
            model_label="auth.User",
            file_format="csv",
            file_name="own.csv",
        )
        cls.url = reverse("user-export-download", kwargs={"pk": cls.export.pk})

    def test_login_required(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_owner_is_redirected_to_file_url(self):
        self.client.force_login(self.owner)
        with TemporaryDirectory() as tmpdir:
            with override_settings(
                FILE_EXPORT_USE_LOCAL_STORAGE=True,
                MEDIA_ROOT=tmpdir,
                MEDIA_URL="/media/",
            ):
                response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/media/tmp/own.csv")

    def test_other_user_gets_404(self):
        self.client.force_login(self.other)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_expired_export_returns_410(self):
        UserExport.objects.filter(pk=self.export.pk).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 410)
