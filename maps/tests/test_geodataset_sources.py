from datetime import timedelta

from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import RequestFactory, TestCase
from django.utils import timezone

from bibliography.models import Source
from maps.admin import (
    GeoDatasetImportRunAdmin,
    GeoDatasetSnapshotAdmin,
    GeoDatasetSourceAdmin,
)
from maps.models import (
    GeoDataset,
    GeoDatasetImportRun,
    GeoDatasetRuntimeConfiguration,
    GeoDatasetSnapshot,
    GeoDatasetSource,
    Region,
)


class GeoDatasetSourceTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bibliography_source = Source.objects.create(title="Provider reference")
        cls.region = Region.objects.create(name="Test region", country="DE")

    def make_source(self, **overrides):
        defaults = {
            "slug": "test-source",
            "name": "Test source",
            "endpoint_url": "https://example.test/wfs",
            "feature_type": "test:features",
            "bibliography_source": self.bibliography_source,
            "attribution": "Test provider",
            "license_url": "https://example.test/license",
        }
        defaults.update(overrides)
        return GeoDatasetSource(**defaults)

    def test_str_returns_name(self):
        source = self.make_source()
        self.assertEqual(str(source), "Test source")

    def test_defaults(self):
        source = self.make_source()
        self.assertEqual(source.connector_type, GeoDatasetSource.ConnectorType.WFS)
        self.assertFalse(source.is_enabled)

    def test_sources_order_by_name(self):
        self.make_source(slug="zeta", name="Zeta").save()
        self.make_source(slug="alpha", name="Alpha").save()
        names = list(GeoDatasetSource.objects.values_list("name", flat=True))
        self.assertEqual(names, ["Alpha", "Zeta"])

    def test_required_fields_validated(self):
        source = GeoDatasetSource(slug="incomplete")
        with self.assertRaises(ValidationError) as ctx:
            source.full_clean()
        for field in (
            "name",
            "endpoint_url",
            "feature_type",
            "bibliography_source",
            "attribution",
            "license_url",
        ):
            self.assertIn(field, ctx.exception.error_dict)

    def test_invalid_endpoint_url_rejected(self):
        source = self.make_source(endpoint_url="not-a-url")
        with self.assertRaises(ValidationError) as ctx:
            source.full_clean()
        self.assertIn("endpoint_url", ctx.exception.error_dict)

    def test_slug_must_be_unique(self):
        self.make_source().save()
        with self.assertRaises(ValidationError) as ctx:
            self.make_source(name="Other").full_clean()
        self.assertIn("slug", ctx.exception.error_dict)

    def test_bibliography_source_deletion_protected(self):
        self.make_source().save()
        with self.assertRaises(ProtectedError):
            self.bibliography_source.delete()


class GeoDatasetImportRunTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bibliography_source = Source.objects.create(title="Provider reference")
        cls.region = Region.objects.create(name="Test region", country="DE")
        cls.source = GeoDatasetSource.objects.create(
            slug="test-source",
            name="Test source",
            endpoint_url="https://example.test/wfs",
            feature_type="test:features",
            bibliography_source=cls.bibliography_source,
            attribution="Test provider",
            license_url="https://example.test/license",
        )

    def make_run(self, **overrides):
        defaults = {"source": self.source}
        defaults.update(overrides)
        return GeoDatasetImportRun.objects.create(**defaults)

    def test_default_status_is_running(self):
        run = self.make_run()
        self.assertEqual(run.status, GeoDatasetImportRun.Status.RUNNING)
        self.assertIsNone(run.finished_at)
        self.assertEqual(run.error_message, "")

    def test_captures_exact_source_configuration_on_create(self):
        run = self.make_run()
        self.assertEqual(
            run.source_configuration,
            {
                "connector_type": "wfs",
                "endpoint_url": "https://example.test/wfs",
                "feature_type": "test:features",
                "bibliography_source_id": self.bibliography_source.pk,
                "license_url": "https://example.test/license",
                "attribution": "Test provider",
            },
        )

    def test_capture_uses_persisted_source_not_unsaved_instance_state(self):
        self.source.endpoint_url = "https://unsaved.test/wfs"
        run = self.make_run()
        self.assertEqual(
            run.source_configuration["endpoint_url"], "https://example.test/wfs"
        )

    def test_caller_supplied_source_configuration_is_overwritten(self):
        run = self.make_run(source_configuration={"forged": True})
        self.assertNotIn("forged", run.source_configuration)
        self.assertEqual(run.source_configuration["connector_type"], "wfs")

    def test_nonserializable_source_configuration_is_overwritten(self):
        run = self.make_run(source_configuration={"unserializable": object()})
        self.assertEqual(run.source_configuration["connector_type"], "wfs")
        self.assertNotIn("unserializable", run.source_configuration)

    def test_run_requires_valid_source(self):
        with self.assertRaises(ValidationError):
            GeoDatasetImportRun.objects.create(source_id=0)

    def test_captures_bibliography_source_from_persisted_source(self):
        run = self.make_run()
        self.assertEqual(run.bibliography_source_id, self.bibliography_source.pk)

    def test_caller_supplied_bibliography_source_is_overwritten(self):
        other = Source.objects.create(title="Decoy reference")
        run = self.make_run(bibliography_source=other)
        self.assertEqual(run.bibliography_source_id, self.bibliography_source.pk)

    def test_captured_bibliography_source_survives_source_switch(self):
        run = self.make_run()
        other = Source.objects.create(title="Replacement reference")
        self.source.bibliography_source = other
        self.source.save()

        run.refresh_from_db()
        self.assertEqual(run.bibliography_source_id, self.bibliography_source.pk)
        with self.assertRaises(ProtectedError):
            self.bibliography_source.delete()

    def test_bibliography_source_is_frozen_after_create(self):
        run = self.make_run()
        run.bibliography_source = Source.objects.create(title="Other reference")
        with self.assertRaises(ValidationError):
            run.save()

    def test_later_source_edits_do_not_change_captured_configuration(self):
        run = self.make_run()
        self.source.endpoint_url = "https://changed.test/wfs"
        self.source.save()
        run.refresh_from_db()
        self.assertEqual(
            run.source_configuration["endpoint_url"], "https://example.test/wfs"
        )

    def test_running_run_cannot_have_finished_at(self):
        with self.assertRaises(ValidationError):
            self.make_run(finished_at=timezone.now())

    def test_running_run_cannot_have_error_message(self):
        with self.assertRaises(ValidationError):
            self.make_run(error_message="boom")

    def test_succeeded_requires_finished_at(self):
        with self.assertRaises(ValidationError):
            self.make_run(status=GeoDatasetImportRun.Status.SUCCEEDED)

    def test_succeeded_rejects_error_message(self):
        with self.assertRaises(ValidationError):
            self.make_run(
                status=GeoDatasetImportRun.Status.SUCCEEDED,
                finished_at=timezone.now(),
                error_message="boom",
            )

    def test_failed_requires_error_message(self):
        with self.assertRaises(ValidationError):
            self.make_run(
                status=GeoDatasetImportRun.Status.FAILED,
                finished_at=timezone.now(),
            )

    def test_failed_rejects_whitespace_only_error_message(self):
        with self.assertRaises(ValidationError):
            self.make_run(
                status=GeoDatasetImportRun.Status.FAILED,
                finished_at=timezone.now(),
                error_message="   ",
            )

    def test_failed_requires_finished_at(self):
        with self.assertRaises(ValidationError):
            self.make_run(
                status=GeoDatasetImportRun.Status.FAILED,
                error_message="boom",
            )

    def test_finished_at_before_started_at_rejected(self):
        started = timezone.now()
        with self.assertRaises(ValidationError):
            self.make_run(
                started_at=started,
                status=GeoDatasetImportRun.Status.SUCCEEDED,
                finished_at=started - timedelta(hours=1),
            )

    def test_extraction_specification_must_be_a_json_object(self):
        with self.assertRaises(ValidationError):
            self.make_run(extraction_specification=["not", "a", "dict"])

    def test_invalid_status_choice_rejected(self):
        with self.assertRaises(ValidationError):
            self.make_run(status="bogus")

    def test_run_completes_successfully(self):
        run = self.make_run()
        run.status = GeoDatasetImportRun.Status.SUCCEEDED
        run.finished_at = timezone.now()
        run.save()
        run.refresh_from_db()
        self.assertEqual(run.status, GeoDatasetImportRun.Status.SUCCEEDED)
        self.assertIsNotNone(run.finished_at)

    def test_run_completes_failed(self):
        run = self.make_run()
        run.status = GeoDatasetImportRun.Status.FAILED
        run.finished_at = timezone.now()
        run.error_message = "upstream timeout"
        run.save()
        run.refresh_from_db()
        self.assertEqual(run.status, GeoDatasetImportRun.Status.FAILED)
        self.assertEqual(run.error_message, "upstream timeout")

    def test_source_link_is_frozen_after_create(self):
        other = GeoDatasetSource.objects.create(
            slug="other",
            name="Other",
            endpoint_url="https://example.test/other",
            feature_type="t:o",
            bibliography_source=self.bibliography_source,
            attribution="O",
            license_url="https://example.test/o-license",
        )
        run = self.make_run()
        run.source = other
        with self.assertRaises(ValidationError):
            run.save()

    def test_source_configuration_is_frozen_after_create(self):
        run = self.make_run()
        run.source_configuration = {"connector_type": "forged"}
        with self.assertRaises(ValidationError):
            run.save()

    def test_extraction_specification_is_frozen_after_create(self):
        run = self.make_run()
        run.extraction_specification = {"changed": True}
        with self.assertRaises(ValidationError):
            run.save()

    def test_started_at_is_frozen_after_create(self):
        run = self.make_run()
        run.started_at = run.started_at - timedelta(days=7)
        with self.assertRaises(ValidationError):
            run.save()

    def test_terminal_run_cannot_change_back_to_running(self):
        run = self.make_run()
        run.status = GeoDatasetImportRun.Status.SUCCEEDED
        run.finished_at = timezone.now()
        run.save()
        run.status = GeoDatasetImportRun.Status.RUNNING
        run.finished_at = None
        with self.assertRaises(ValidationError):
            run.save()

    def test_terminal_run_rejects_field_edits(self):
        run = self.make_run()
        run.status = GeoDatasetImportRun.Status.SUCCEEDED
        run.finished_at = timezone.now()
        run.save()
        run.error_message = "retroactive note"
        with self.assertRaises(ValidationError):
            run.save()

    def test_terminal_run_resave_unchanged_is_allowed(self):
        run = self.make_run()
        run.status = GeoDatasetImportRun.Status.SUCCEEDED
        run.finished_at = timezone.now()
        run.save()
        run.save()
        run.refresh_from_db()
        self.assertEqual(run.status, GeoDatasetImportRun.Status.SUCCEEDED)

    def test_stale_running_instance_cannot_overwrite_terminal_state(self):
        run = self.make_run()
        stale = GeoDatasetImportRun.objects.get(pk=run.pk)
        run.status = GeoDatasetImportRun.Status.SUCCEEDED
        run.finished_at = timezone.now()
        run.save()

        stale.status = GeoDatasetImportRun.Status.FAILED
        stale.finished_at = timezone.now()
        stale.error_message = "late failure"
        with self.assertRaises(ValidationError):
            stale.save()

        run.refresh_from_db()
        self.assertEqual(run.status, GeoDatasetImportRun.Status.SUCCEEDED)
        self.assertEqual(run.error_message, "")

    def test_source_deletion_protected_once_run_exists(self):
        self.make_run()
        with self.assertRaises(ProtectedError):
            self.source.delete()

    def test_db_constraints_reject_invalid_states_via_queryset_update(self):
        run = self.make_run()
        runs = GeoDatasetImportRun.objects.filter(pk=run.pk)

        with self.assertRaises(IntegrityError), transaction.atomic():
            runs.update(finished_at=timezone.now())
        with self.assertRaises(IntegrityError), transaction.atomic():
            runs.update(status=GeoDatasetImportRun.Status.SUCCEEDED)
        with self.assertRaises(IntegrityError), transaction.atomic():
            runs.update(
                status=GeoDatasetImportRun.Status.FAILED,
                finished_at=timezone.now(),
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            runs.update(
                status=GeoDatasetImportRun.Status.SUCCEEDED,
                finished_at=run.started_at - timedelta(hours=1),
            )

        run.refresh_from_db()
        self.assertEqual(run.status, GeoDatasetImportRun.Status.RUNNING)
        self.assertIsNone(run.finished_at)


class GeoDatasetSnapshotTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bibliography_source = Source.objects.create(title="Provider reference")
        cls.region = Region.objects.create(name="Test region", country="DE")
        cls.source = GeoDatasetSource.objects.create(
            slug="test-source",
            name="Test source",
            endpoint_url="https://example.test/wfs",
            feature_type="test:features",
            bibliography_source=cls.bibliography_source,
            attribution="Test provider",
            license_url="https://example.test/license",
        )

    def make_dataset(self, name="Local dataset", **config_overrides):
        dataset = GeoDataset.objects.create(name=name, region=self.region)
        config = {
            "dataset": dataset,
            "backend_type": "local_relation",
            "schema_name": "public",
            "relation_name": "issue85_features",
            "geometry_column": "geom",
            "primary_key_column": "id",
        }
        config.update(config_overrides)
        GeoDatasetRuntimeConfiguration.objects.create(**config)
        return dataset

    def make_succeeded_run(self):
        run = GeoDatasetImportRun.objects.create(source=self.source)
        run.status = GeoDatasetImportRun.Status.SUCCEEDED
        run.finished_at = timezone.now()
        run.save()
        return run

    def make_snapshot(self, dataset=None, import_run=None):
        dataset = dataset or self.make_dataset()
        import_run = import_run or self.make_succeeded_run()
        return GeoDatasetSnapshot.objects.create(dataset=dataset, import_run=import_run)

    def test_snapshot_links_succeeded_run_and_dataset(self):
        snapshot = self.make_snapshot()
        self.assertEqual(snapshot.import_run.source, self.source)
        self.assertEqual(snapshot.dataset.external_snapshot, snapshot)
        self.assertEqual(snapshot.import_run.snapshot, snapshot)

    def test_snapshot_derives_source_via_import_run(self):
        snapshot = self.make_snapshot()
        self.assertEqual(snapshot.import_run.source_id, self.source.pk)

    def test_snapshot_rejects_running_run(self):
        run = GeoDatasetImportRun.objects.create(source=self.source)
        with self.assertRaises(ValidationError):
            GeoDatasetSnapshot.objects.create(
                dataset=self.make_dataset(), import_run=run
            )

    def test_snapshot_rejects_failed_run(self):
        run = GeoDatasetImportRun.objects.create(source=self.source)
        run.status = GeoDatasetImportRun.Status.FAILED
        run.finished_at = timezone.now()
        run.error_message = "boom"
        run.save()
        with self.assertRaises(ValidationError):
            GeoDatasetSnapshot.objects.create(
                dataset=self.make_dataset(), import_run=run
            )

    def test_snapshot_queries_persisted_run_status_not_cached_instance(self):
        run = GeoDatasetImportRun.objects.create(source=self.source)
        run.status = GeoDatasetImportRun.Status.SUCCEEDED
        run.finished_at = timezone.now()
        with self.assertRaises(ValidationError):
            GeoDatasetSnapshot.objects.create(
                dataset=self.make_dataset(), import_run=run
            )
        run.refresh_from_db()
        self.assertEqual(run.status, GeoDatasetImportRun.Status.RUNNING)

    def test_snapshot_rejects_dataset_without_runtime_configuration(self):
        dataset = GeoDataset.objects.create(name="Bare dataset", region=self.region)
        with self.assertRaises(ValidationError) as ctx:
            GeoDatasetSnapshot.objects.create(
                dataset=dataset, import_run=self.make_succeeded_run()
            )
        self.assertIn("dataset", ctx.exception.error_dict)

    def test_snapshot_rejects_model_backed_runtime_configuration(self):
        dataset = GeoDataset.objects.create(
            name="Model dataset",
            region=self.region,
            model_name="NutsRegion",
        )
        GeoDatasetRuntimeConfiguration.objects.create(
            dataset=dataset,
            backend_type="django_model",
            runtime_model_name="NutsRegion",
        )
        with self.assertRaises(ValidationError) as ctx:
            GeoDatasetSnapshot.objects.create(
                dataset=dataset, import_run=self.make_succeeded_run()
            )
        self.assertIn("dataset", ctx.exception.error_dict)

    def test_snapshot_rejects_incomplete_local_relation_configuration(self):
        dataset = self.make_dataset(schema_name="")
        with self.assertRaises(ValidationError) as ctx:
            GeoDatasetSnapshot.objects.create(
                dataset=dataset, import_run=self.make_succeeded_run()
            )
        self.assertIn("dataset", ctx.exception.error_dict)

    def test_snapshot_rejects_invalid_relation_identifier(self):
        dataset = self.make_dataset(relation_name="bad;drop")
        with self.assertRaises(ValidationError) as ctx:
            GeoDatasetSnapshot.objects.create(
                dataset=dataset, import_run=self.make_succeeded_run()
            )
        self.assertIn("dataset", ctx.exception.error_dict)

    def test_snapshot_accepts_local_relation_without_existing_table(self):
        snapshot = self.make_snapshot()
        self.assertIsNotNone(snapshot.pk)

    def test_one_snapshot_per_import_run(self):
        run = self.make_succeeded_run()
        self.make_snapshot(import_run=run)
        with self.assertRaises(ValidationError):
            self.make_snapshot(import_run=run)

    def test_one_snapshot_per_dataset(self):
        dataset = self.make_dataset()
        self.make_snapshot(dataset=dataset)
        with self.assertRaises(ValidationError):
            self.make_snapshot(dataset=dataset)

    def test_dataset_link_cannot_be_reassigned(self):
        snapshot = self.make_snapshot()
        snapshot.dataset = self.make_dataset(name="Replacement")
        with self.assertRaises(ValidationError):
            snapshot.save()

    def test_import_run_link_cannot_be_reassigned(self):
        snapshot = self.make_snapshot()
        snapshot.import_run = self.make_succeeded_run()
        with self.assertRaises(ValidationError):
            snapshot.save()

    def test_run_deletion_protected_once_snapshot_exists(self):
        snapshot = self.make_snapshot()
        with self.assertRaises(ProtectedError):
            snapshot.import_run.delete()

    def test_dataset_deletion_protected_once_snapshot_exists(self):
        snapshot = self.make_snapshot()
        with self.assertRaises(ProtectedError):
            snapshot.dataset.delete()

    def test_registration_does_not_publish_repoint_or_promote(self):
        dataset = self.make_dataset()
        snapshot = self.make_snapshot(dataset=dataset)

        dataset.refresh_from_db()
        self.assertFalse(dataset.publish)
        self.assertEqual(dataset.column_policies.count(), 0)
        config = dataset.get_runtime_configuration()
        self.assertEqual(config.backend_type, "local_relation")
        self.assertEqual(config.relation_name, "issue85_features")
        self.assertEqual(snapshot.dataset_id, dataset.pk)


class GeoDatasetSourceAdminTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bibliography_source = Source.objects.create(title="Provider reference")
        cls.region = Region.objects.create(name="Test region", country="DE")
        cls.source = GeoDatasetSource.objects.create(
            slug="test-source",
            name="Test source",
            endpoint_url="https://example.test/wfs",
            feature_type="test:features",
            bibliography_source=cls.bibliography_source,
            attribution="Test provider",
            license_url="https://example.test/license",
        )
        cls.user = User.objects.create_superuser(
            username="snapshot-admin",
            email="snapshot-admin@example.test",
            password="x",
        )

    def setUp(self):
        self.site = AdminSite()
        self.request = RequestFactory().get("/admin/")
        self.request.user = self.user

    def test_models_are_registered(self):
        self.assertTrue(admin.site.is_registered(GeoDatasetSource))
        self.assertTrue(admin.site.is_registered(GeoDatasetImportRun))
        self.assertTrue(admin.site.is_registered(GeoDatasetSnapshot))

    def test_source_admin_keeps_config_editable(self):
        model_admin = GeoDatasetSourceAdmin(GeoDatasetSource, self.site)
        readonly = model_admin.get_readonly_fields(self.request, self.source)
        for field in (
            "endpoint_url",
            "feature_type",
            "attribution",
            "license_url",
            "is_enabled",
        ):
            self.assertNotIn(field, readonly)

    def test_run_admin_freezes_provenance_after_creation(self):
        model_admin = GeoDatasetImportRunAdmin(GeoDatasetImportRun, self.site)
        run = GeoDatasetImportRun.objects.create(source=self.source)

        add_readonly = model_admin.get_readonly_fields(self.request, None)
        self.assertIn("source_configuration", add_readonly)
        self.assertNotIn("source", add_readonly)
        self.assertNotIn("extraction_specification", add_readonly)

        change_readonly = model_admin.get_readonly_fields(self.request, run)
        for field in (
            "source",
            "bibliography_source",
            "source_configuration",
            "extraction_specification",
            "started_at",
        ):
            self.assertIn(field, change_readonly)
        for field in ("status", "finished_at", "error_message"):
            self.assertNotIn(field, change_readonly)

    def test_run_admin_readonly_all_fields_once_terminal(self):
        model_admin = GeoDatasetImportRunAdmin(GeoDatasetImportRun, self.site)
        run = GeoDatasetImportRun.objects.create(source=self.source)
        run.status = GeoDatasetImportRun.Status.SUCCEEDED
        run.finished_at = timezone.now()
        run.save()

        readonly = model_admin.get_readonly_fields(self.request, run)
        for field in (
            "source",
            "bibliography_source",
            "source_configuration",
            "extraction_specification",
            "started_at",
            "status",
            "finished_at",
            "error_message",
        ):
            self.assertIn(field, readonly)

    def test_run_admin_disallows_delete(self):
        model_admin = GeoDatasetImportRunAdmin(GeoDatasetImportRun, self.site)
        self.assertFalse(model_admin.has_delete_permission(self.request))
        run = GeoDatasetImportRun.objects.create(source=self.source)
        self.assertFalse(model_admin.has_delete_permission(self.request, run))

    def test_snapshot_admin_readonly_links_and_disallows_delete(self):
        model_admin = GeoDatasetSnapshotAdmin(GeoDatasetSnapshot, self.site)

        add_readonly = model_admin.get_readonly_fields(self.request, None)
        self.assertNotIn("dataset", add_readonly)
        self.assertNotIn("import_run", add_readonly)

        dataset = GeoDataset.objects.create(name="ds", region=self.region)
        GeoDatasetRuntimeConfiguration.objects.create(
            dataset=dataset,
            backend_type="local_relation",
            schema_name="public",
            relation_name="issue85_features",
            geometry_column="geom",
            primary_key_column="id",
        )
        run = GeoDatasetImportRun.objects.create(source=self.source)
        run.status = GeoDatasetImportRun.Status.SUCCEEDED
        run.finished_at = timezone.now()
        run.save()
        snapshot = GeoDatasetSnapshot.objects.create(dataset=dataset, import_run=run)

        change_readonly = model_admin.get_readonly_fields(self.request, snapshot)
        self.assertIn("dataset", change_readonly)
        self.assertIn("import_run", change_readonly)
        self.assertIn("created_at", change_readonly)
        self.assertFalse(model_admin.has_delete_permission(self.request))
        self.assertFalse(model_admin.has_delete_permission(self.request, snapshot))
