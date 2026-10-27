from unittest.mock import MagicMock, patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import ProtectedError
from django.forms import modelform_factory
from django.http import QueryDict
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from bibliography.models import Source
from maps.admin import (
    GeoDatasetModelAdmin,
    GeoDatasetRuntimeConfigurationAdmin,
    GeoDatasetRuntimeConfigurationInline,
)
from maps.forms import GeoDataSetModelForm
from maps.models import (
    GeoDataset,
    GeoDatasetColumnPolicy,
    GeoDatasetImportRun,
    GeoDatasetRuntimeConfiguration,
    GeoDatasetSnapshot,
    GeoDatasetSource,
    Region,
)


def _create_succeeded_run(source):
    run = GeoDatasetImportRun.objects.create(source=source)
    run.status = GeoDatasetImportRun.Status.SUCCEEDED
    run.finished_at = timezone.now()
    run.save()
    return run


class SnapshottedDatasetFixturesMixin:
    @classmethod
    def setUpTestData(cls):
        cls.bibliography_source = Source.objects.create(title="Provider reference")
        cls.region = Region.objects.create(
            name="Guard region", country="DE", publication_status="published"
        )
        cls.source = GeoDatasetSource.objects.create(
            slug="guard-source",
            name="Guard source",
            endpoint_url="https://example.test/wfs",
            feature_type="test:features",
            bibliography_source=cls.bibliography_source,
            attribution="Test provider",
            license_url="https://example.test/license",
        )
        cls.dataset = cls.create_local_relation_dataset("Snapshotted dataset")
        cls.import_run = _create_succeeded_run(cls.source)
        cls.snapshot = GeoDatasetSnapshot.objects.create(
            dataset=cls.dataset, import_run=cls.import_run
        )

    @classmethod
    def create_local_relation_dataset(cls, name, **config_overrides):
        dataset = GeoDataset.objects.create(name=name, region=cls.region)
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

    @classmethod
    def create_snapshotted_dataset(cls, name, **config_overrides):
        dataset = cls.create_local_relation_dataset(name, **config_overrides)
        GeoDatasetSnapshot.objects.create(
            dataset=dataset, import_run=_create_succeeded_run(cls.source)
        )
        return dataset


class SnapshottedRuntimeConfigurationTestCase(
    SnapshottedDatasetFixturesMixin, TestCase
):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.plain_dataset = cls.create_local_relation_dataset(
            "Plain dataset", relation_name="plain_features"
        )
        cls.other_snapshotted = cls.create_snapshotted_dataset(
            "Other snapshotted", relation_name="other_features"
        )

    def test_each_identity_field_change_is_rejected(self):
        changes = {
            "dataset_id": self.plain_dataset.pk,
            "backend_type": "django_model",
            "runtime_model_name": "NutsRegion",
            "schema_name": "other_schema",
            "relation_name": "other_relation",
            "geometry_column": "other_geom",
            "primary_key_column": "other_pk",
            "features_api_basename": "other-basename",
        }
        for field_name, new_value in changes.items():
            with self.subTest(field=field_name):
                config = GeoDatasetRuntimeConfiguration.objects.get(
                    pk=self.dataset.runtime_configuration.pk
                )
                originals = {
                    field.attname: getattr(config, field.attname)
                    for field in config._meta.fields
                }
                setattr(config, field_name, new_value)
                with self.assertRaises(ValidationError):
                    config.save()
                config.refresh_from_db()
                for field in config._meta.fields:
                    self.assertEqual(
                        getattr(config, field.attname),
                        originals[field.attname],
                        f"{field.attname} changed despite rejection",
                    )

    def test_repoint_to_other_snapshotted_dataset_rejected(self):
        config = self.plain_dataset.runtime_configuration
        config.dataset = self.other_snapshotted
        with self.assertRaises(ValidationError):
            config.save()
        config.refresh_from_db()
        self.assertEqual(config.dataset_id, self.plain_dataset.pk)

    def test_new_runtime_config_on_snapshotted_dataset_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            GeoDatasetRuntimeConfiguration(
                dataset=self.dataset,
                backend_type="local_relation",
                schema_name="public",
                relation_name="replacement",
                geometry_column="geom",
                primary_key_column="id",
            ).save()
        self.assertIn("dataset", ctx.exception.error_dict)

    def test_relation_name_change_rejected(self):
        config = self.dataset.runtime_configuration
        config.relation_name = "repointed_relation"
        with self.assertRaises(ValidationError) as ctx:
            config.save()
        self.assertIn("relation_name", ctx.exception.error_dict)
        config.refresh_from_db()
        self.assertEqual(config.relation_name, "issue85_features")

    def test_unchanged_save_is_allowed(self):
        config = GeoDatasetRuntimeConfiguration.objects.get(
            pk=self.dataset.runtime_configuration.pk
        )
        config.save()
        config.refresh_from_db()
        self.assertEqual(config.relation_name, "issue85_features")

    def test_label_field_remains_editable(self):
        config = self.dataset.runtime_configuration
        config.label_field = "feature_label"
        config.save()
        config.refresh_from_db()
        self.assertEqual(config.label_field, "feature_label")

    def test_update_fields_cannot_bypass_guard(self):
        config = self.dataset.runtime_configuration
        config.relation_name = "repointed"
        with self.assertRaises(ValidationError):
            config.save(update_fields=["relation_name"])
        config.refresh_from_db()
        self.assertEqual(config.relation_name, "issue85_features")

    def test_full_clean_reports_identity_fields(self):
        config = self.dataset.runtime_configuration
        config.relation_name = "repointed"
        with self.assertRaises(ValidationError) as ctx:
            config.full_clean()
        self.assertIn("relation_name", ctx.exception.error_dict)

    def test_runtime_instance_delete_blocked_by_snapshot(self):
        runtime = self.dataset.runtime_configuration
        with self.assertRaises(ProtectedError), transaction.atomic():
            runtime.delete()
        self.assertTrue(
            GeoDatasetRuntimeConfiguration.objects.filter(pk=runtime.pk).exists()
        )

    def test_runtime_queryset_delete_blocked_by_snapshot(self):
        runtime = self.dataset.runtime_configuration
        with self.assertRaises(ProtectedError), transaction.atomic():
            GeoDatasetRuntimeConfiguration.objects.filter(pk=runtime.pk).delete()
        self.assertTrue(
            GeoDatasetRuntimeConfiguration.objects.filter(pk=runtime.pk).exists()
        )

    def test_stale_runtime_instance_delete_blocked(self):
        runtime = self.dataset.runtime_configuration
        runtime.dataset_id = self.plain_dataset.pk
        with self.assertRaises(ProtectedError), transaction.atomic():
            runtime.delete()
        self.assertTrue(
            GeoDatasetRuntimeConfiguration.objects.filter(pk=runtime.pk).exists()
        )
        runtime.refresh_from_db()
        self.assertEqual(runtime.dataset_id, self.dataset.pk)

    def test_mixed_runtime_queryset_delete_preserves_all_rows(self):
        protected_pk = self.dataset.runtime_configuration.pk
        plain_pk = self.plain_dataset.runtime_configuration.pk
        with self.assertRaises(ProtectedError), transaction.atomic():
            GeoDatasetRuntimeConfiguration.objects.filter(
                pk__in=[protected_pk, plain_pk]
            ).delete()
        self.assertEqual(
            GeoDatasetRuntimeConfiguration.objects.filter(
                pk__in=[protected_pk, plain_pk]
            ).count(),
            2,
        )

    def test_plain_runtime_delete_is_allowed(self):
        runtime = self.plain_dataset.runtime_configuration
        runtime_pk = runtime.pk
        runtime.delete()
        self.assertFalse(
            GeoDatasetRuntimeConfiguration.objects.filter(pk=runtime_pk).exists()
        )

    def test_plain_runtime_identity_change_allowed(self):
        runtime = self.plain_dataset.runtime_configuration
        runtime.relation_name = "repointed_features"
        runtime.save()
        runtime.refresh_from_db()
        self.assertEqual(runtime.relation_name, "repointed_features")


class SnapshottedDatasetModelNameTestCase(SnapshottedDatasetFixturesMixin, TestCase):
    def test_model_name_change_rejected_for_snapshotted_dataset(self):
        self.assertEqual(self.dataset.get_features_api_basename(), "")
        self.dataset.model_name = "NutsRegion"

        with self.assertRaises(ValidationError) as ctx:
            self.dataset.save()

        self.assertIn("model_name", ctx.exception.message_dict)
        self.dataset.refresh_from_db()
        self.assertIsNone(self.dataset.model_name)
        self.assertEqual(self.dataset.get_features_api_basename(), "")

    def test_other_fields_stay_editable_for_snapshotted_dataset(self):
        self.dataset.name = "Renamed snapshotted"
        self.dataset.save()
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.name, "Renamed snapshotted")

    def test_model_name_change_allowed_for_plain_dataset(self):
        plain = self.create_local_relation_dataset(
            "Plain model name", relation_name="plain_model_name"
        )
        plain.model_name = "NutsRegion"
        plain.save()
        plain.refresh_from_db()
        self.assertEqual(plain.model_name, "NutsRegion")


class SnapshotDeletionGuardTestCase(SnapshottedDatasetFixturesMixin, TestCase):
    def test_snapshot_instance_delete_raises_protected_error(self):
        with self.assertRaises(ProtectedError), transaction.atomic():
            self.snapshot.delete()
        self.assertTrue(GeoDatasetSnapshot.objects.filter(pk=self.snapshot.pk).exists())

    def test_snapshot_queryset_delete_raises_protected_error(self):
        with self.assertRaises(ProtectedError), transaction.atomic():
            GeoDatasetSnapshot.objects.filter(pk=self.snapshot.pk).delete()
        self.assertTrue(GeoDatasetSnapshot.objects.filter(pk=self.snapshot.pk).exists())

    def test_mixed_snapshot_queryset_delete_preserves_all_rows(self):
        other_dataset = self.create_snapshotted_dataset(
            "Second snapshotted", relation_name="second_features"
        )
        other_snapshot = other_dataset.external_snapshot
        with self.assertRaises(ProtectedError), transaction.atomic():
            GeoDatasetSnapshot.objects.filter(
                pk__in=[self.snapshot.pk, other_snapshot.pk]
            ).delete()
        self.assertEqual(
            GeoDatasetSnapshot.objects.filter(
                pk__in=[self.snapshot.pk, other_snapshot.pk]
            ).count(),
            2,
        )

    def test_run_delete_remains_protected(self):
        with self.assertRaises(ProtectedError), transaction.atomic():
            self.import_run.delete()

    def test_dataset_delete_remains_protected(self):
        with self.assertRaises(ProtectedError), transaction.atomic():
            self.dataset.delete()

    def test_snapshot_links_survive_failed_delete(self):
        try:
            with transaction.atomic():
                self.snapshot.delete()
        except ProtectedError:
            pass
        snapshot = GeoDatasetSnapshot.objects.get(pk=self.snapshot.pk)
        self.assertEqual(snapshot.dataset_id, self.dataset.pk)
        self.assertEqual(snapshot.import_run_id, self.import_run.pk)


class SnapshotLockSeamTestCase(SnapshottedDatasetFixturesMixin, TestCase):
    def test_snapshot_save_locks_parent_dataset_row(self):
        other_dataset = self.create_local_relation_dataset(
            "Pending dataset", relation_name="pending_features"
        )
        run = _create_succeeded_run(self.source)
        with patch("maps.models._lock_geodataset_rows") as lock_mock:
            GeoDatasetSnapshot.objects.create(dataset=other_dataset, import_run=run)
        self.assertTrue(lock_mock.called)
        locked_ids = lock_mock.call_args[0][0]
        self.assertIn(other_dataset.pk, locked_ids)

    def test_runtime_save_locks_parent_dataset_row(self):
        config = self.dataset.runtime_configuration
        with patch("maps.models._lock_geodataset_rows") as lock_mock:
            config.save()
        self.assertTrue(lock_mock.called)
        locked_ids = lock_mock.call_args[0][0]
        self.assertIn(self.dataset.pk, locked_ids)

    def test_runtime_save_locks_parent_before_runtime_row(self):
        config = self.dataset.runtime_configuration
        call_order = []
        real_select_for_update = (
            GeoDatasetRuntimeConfiguration.objects.select_for_update
        )

        def recording_select_for_update(*args, **kwargs):
            call_order.append("runtime_row")
            return real_select_for_update(*args, **kwargs)

        with (
            patch(
                "maps.models._lock_geodataset_rows",
                side_effect=lambda *a, **k: call_order.append("parent_rows"),
            ),
            patch.object(
                GeoDatasetRuntimeConfiguration.objects,
                "select_for_update",
                side_effect=recording_select_for_update,
            ),
        ):
            config.save()
        self.assertEqual(call_order, ["parent_rows", "runtime_row"])

    def test_runtime_save_rejects_concurrent_parent_reassignment(self):
        config = self.dataset.runtime_configuration
        moved_target = self.create_local_relation_dataset(
            "Moved target", relation_name="moved_features"
        )
        moved = GeoDatasetRuntimeConfiguration(dataset_id=moved_target.pk)
        fake_queryset = MagicMock()
        fake_queryset.filter.return_value.first.return_value = moved
        with patch.object(
            GeoDatasetRuntimeConfiguration.objects,
            "select_for_update",
            return_value=fake_queryset,
        ):
            with self.assertRaises(ValidationError) as ctx:
                config.save()
        self.assertIn("dataset", ctx.exception.error_dict)

    def test_runtime_delete_locks_persisted_parent_row(self):
        plain_dataset = self.create_local_relation_dataset(
            "Deletable dataset", relation_name="deletable_features"
        )
        runtime = plain_dataset.runtime_configuration
        runtime_pk = runtime.pk
        with patch("maps.signals._lock_geodataset_rows") as lock_mock:
            runtime.delete()
        self.assertTrue(lock_mock.called)
        locked_ids = lock_mock.call_args[0][0]
        self.assertIn(plain_dataset.pk, locked_ids)
        self.assertFalse(
            GeoDatasetRuntimeConfiguration.objects.filter(pk=runtime_pk).exists()
        )


class SnapshottedDatasetFormTestCase(SnapshottedDatasetFixturesMixin, TestCase):
    def _post_data(self, **overrides):
        data = {
            "name": "Renamed dataset",
            "region": str(self.region.pk),
            "backend_type": "local_relation",
            "runtime_model_name": "",
            "schema_name": "public",
            "relation_name": "issue85_features",
            "geometry_column": "geom",
            "primary_key_column": "id",
            "label_field": "feature_label",
            "features_api_basename": "",
            "visible_columns": "name",
            "filterable_columns": "",
            "searchable_columns": "",
            "exportable_columns": "",
        }
        data.update(overrides)
        qdata = QueryDict("", mutable=True)
        for key, value in data.items():
            qdata[key] = value
        return qdata

    def test_identity_fields_disabled_for_snapshotted_dataset(self):
        form = GeoDataSetModelForm(instance=self.dataset)
        for field_name in GeoDatasetRuntimeConfiguration.IDENTITY_FIELDS:
            if field_name == "dataset":
                continue
            self.assertTrue(
                form.fields[field_name].disabled, f"{field_name} should be disabled"
            )
        self.assertTrue(form.fields["model_name"].disabled)
        self.assertFalse(form.fields["label_field"].disabled)

    def test_identity_fields_editable_for_plain_dataset(self):
        plain = self.create_local_relation_dataset(
            "Editable dataset", relation_name="editable_features"
        )
        form = GeoDataSetModelForm(instance=plain)
        for field_name in ("relation_name", "schema_name", "model_name"):
            self.assertFalse(form.fields[field_name].disabled)

    def test_tampered_post_cannot_repoint_runtime(self):
        data = self._post_data(
            relation_name="hacked_table",
            schema_name="hacked",
            features_api_basename="hacked-api",
            model_name="NutsRegion",
        )
        form = GeoDataSetModelForm(data=data, instance=self.dataset)

        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        runtime = self.dataset.runtime_configuration
        runtime.refresh_from_db()
        self.assertEqual(runtime.relation_name, "issue85_features")
        self.assertEqual(runtime.schema_name, "public")
        self.assertEqual(runtime.features_api_basename, "")
        self.assertEqual(runtime.label_field, "feature_label")
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.name, "Renamed dataset")
        self.assertIsNone(self.dataset.model_name)
        self.assertEqual(self.dataset.get_features_api_basename(), "")

    def test_form_save_guard_failure_rolls_back_dataset_changes(self):
        data = self._post_data(name="Should not persist")
        form = GeoDataSetModelForm(data=data, instance=self.dataset)
        self.assertTrue(form.is_valid(), form.errors)

        GeoDatasetRuntimeConfiguration.objects.filter(
            pk=self.dataset.runtime_configuration.pk
        ).update(relation_name="drifted")

        with self.assertRaises(ValidationError):
            form.save()

        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.name, "Snapshotted dataset")
        self.assertFalse(
            GeoDatasetColumnPolicy.objects.filter(dataset=self.dataset).exists()
        )

    def test_runtime_modelform_rejects_tampered_identity(self):
        form_class = modelform_factory(GeoDatasetRuntimeConfiguration, fields="__all__")
        runtime = self.dataset.runtime_configuration
        form = form_class(
            data={
                "dataset": str(self.dataset.pk),
                "backend_type": "local_relation",
                "runtime_model_name": "",
                "schema_name": "public",
                "relation_name": "tampered_relation",
                "geometry_column": "geom",
                "primary_key_column": "id",
                "label_field": "",
                "features_api_basename": "",
            },
            instance=runtime,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("relation_name", form.errors)


class SnapshottedDatasetUpdateViewTestCase(SnapshottedDatasetFixturesMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.dataset.owner = User.objects.create_superuser(
            username="guard-owner", email="guard-owner@example.test", password="x"
        )
        cls.dataset.save()

    def test_update_post_redirects_and_keeps_runtime_identity(self):
        self.client.force_login(self.dataset.owner)
        response = self.client.post(
            reverse("geodataset-update", kwargs={"pk": self.dataset.pk}),
            {
                "name": "Renamed via view",
                "region": str(self.region.pk),
                "backend_type": "local_relation",
                "schema_name": "hacked",
                "relation_name": "hacked_table",
                "geometry_column": "hacked",
                "primary_key_column": "hacked",
                "features_api_basename": "hacked-api",
                "label_field": "kept_label",
            },
        )
        self.assertEqual(response.status_code, 302)

        runtime = self.dataset.runtime_configuration
        runtime.refresh_from_db()
        self.assertEqual(runtime.relation_name, "issue85_features")
        self.assertEqual(runtime.schema_name, "public")
        self.assertEqual(runtime.label_field, "kept_label")
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.name, "Renamed via view")


class SnapshottedRuntimeAdminTestCase(SnapshottedDatasetFixturesMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.staff = User.objects.create_superuser(
            username="guard-admin", email="guard-admin@example.test", password="x"
        )

    def setUp(self):
        self.site = AdminSite()
        self.request = RequestFactory().get("/admin/")
        self.request.user = self.staff
        self.runtime = self.dataset.runtime_configuration

    def test_standalone_admin_readonly_identity_for_snapshotted(self):
        model_admin = GeoDatasetRuntimeConfigurationAdmin(
            GeoDatasetRuntimeConfiguration, self.site
        )
        readonly = model_admin.get_readonly_fields(self.request, self.runtime)
        for field_name in GeoDatasetRuntimeConfiguration.IDENTITY_FIELDS:
            self.assertIn(field_name, readonly)
        self.assertNotIn("label_field", readonly)

    def test_standalone_admin_plain_runtime_stays_editable(self):
        plain = self.create_local_relation_dataset(
            "Admin plain", relation_name="admin_plain"
        )
        model_admin = GeoDatasetRuntimeConfigurationAdmin(
            GeoDatasetRuntimeConfiguration, self.site
        )
        readonly = model_admin.get_readonly_fields(
            self.request, plain.runtime_configuration
        )
        self.assertNotIn("relation_name", readonly)
        self.assertTrue(
            model_admin.has_delete_permission(self.request, plain.runtime_configuration)
        )

    def test_standalone_admin_delete_denied_for_snapshotted(self):
        model_admin = GeoDatasetRuntimeConfigurationAdmin(
            GeoDatasetRuntimeConfiguration, self.site
        )
        self.assertFalse(model_admin.has_delete_permission(self.request, self.runtime))

    def test_inline_readonly_identity_and_no_delete_for_snapshot_parent(self):
        inline = GeoDatasetRuntimeConfigurationInline(GeoDataset, self.site)
        readonly = inline.get_readonly_fields(self.request, self.dataset)
        for field_name in GeoDatasetRuntimeConfiguration.IDENTITY_FIELDS:
            if field_name == "dataset":
                continue
            self.assertIn(field_name, readonly)
        self.assertNotIn("label_field", readonly)
        self.assertFalse(inline.has_delete_permission(self.request, self.dataset))

    def test_dataset_admin_readonly_model_name_for_snapshotted(self):
        model_admin = GeoDatasetModelAdmin(GeoDataset, self.site)
        readonly = model_admin.get_readonly_fields(self.request, self.dataset)
        self.assertIn("model_name", readonly)
        self.assertIn("relation_column_review", readonly)

    def test_dataset_admin_model_name_editable_for_plain(self):
        plain = self.create_local_relation_dataset(
            "Admin plain dataset", relation_name="admin_plain_dataset"
        )
        model_admin = GeoDatasetModelAdmin(GeoDataset, self.site)
        self.assertNotIn(
            "model_name", model_admin.get_readonly_fields(self.request, plain)
        )
        self.assertNotIn("model_name", model_admin.get_readonly_fields(self.request))

    def test_inline_stays_editable_and_deletable_for_plain_parent(self):
        plain = self.create_local_relation_dataset(
            "Inline plain", relation_name="inline_plain"
        )
        inline = GeoDatasetRuntimeConfigurationInline(GeoDataset, self.site)
        readonly = inline.get_readonly_fields(self.request, plain)
        self.assertNotIn("relation_name", readonly)
        self.assertTrue(inline.has_delete_permission(self.request, plain))

    def test_inline_formset_crafted_values_cannot_repoint_or_delete(self):
        inline = GeoDatasetRuntimeConfigurationInline(GeoDataset, self.site)
        formset_class = inline.get_formset(self.request, self.dataset)
        formset = formset_class(
            {
                "runtime_configuration-TOTAL_FORMS": "1",
                "runtime_configuration-INITIAL_FORMS": "1",
                "runtime_configuration-MIN_NUM_FORMS": "0",
                "runtime_configuration-MAX_NUM_FORMS": "1",
                "runtime_configuration-0-id": str(self.runtime.pk),
                "runtime_configuration-0-dataset": str(self.dataset.pk),
                "runtime_configuration-0-relation_name": "crafted_evil",
                "runtime_configuration-0-label_field": "kept_label",
                "runtime_configuration-0-DELETE": "on",
            },
            instance=self.dataset,
        )
        self.assertTrue(formset.is_valid(), formset.errors)
        formset.save()

        self.runtime.refresh_from_db()
        self.assertEqual(self.runtime.relation_name, "issue85_features")
        self.assertEqual(self.runtime.label_field, "kept_label")

    def test_inline_formset_for_plain_parent_can_delete(self):
        plain = self.create_local_relation_dataset(
            "Inline deletable", relation_name="inline_deletable"
        )
        runtime = plain.runtime_configuration
        inline = GeoDatasetRuntimeConfigurationInline(GeoDataset, self.site)
        formset_class = inline.get_formset(self.request, plain)
        formset = formset_class(
            {
                "runtime_configuration-TOTAL_FORMS": "1",
                "runtime_configuration-INITIAL_FORMS": "1",
                "runtime_configuration-MIN_NUM_FORMS": "0",
                "runtime_configuration-MAX_NUM_FORMS": "1",
                "runtime_configuration-0-id": str(runtime.pk),
                "runtime_configuration-0-dataset": str(plain.pk),
                "runtime_configuration-0-DELETE": "on",
            },
            instance=plain,
        )
        self.assertTrue(formset.is_valid(), formset.errors)
        formset.save()
        self.assertFalse(
            GeoDatasetRuntimeConfiguration.objects.filter(pk=runtime.pk).exists()
        )

    def test_standalone_admin_post_keeps_identity(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse(
                "admin:maps_geodatasetruntimeconfiguration_change",
                args=[self.runtime.pk],
            ),
            {
                "relation_name": "crafted_evil",
                "schema_name": "crafted",
                "label_field": "admin_label",
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.runtime.refresh_from_db()
        self.assertEqual(self.runtime.relation_name, "issue85_features")
        self.assertEqual(self.runtime.schema_name, "public")
        self.assertEqual(self.runtime.label_field, "admin_label")


class FormEdgeCaseTestCase(SnapshottedDatasetFixturesMixin, TestCase):
    def test_new_dataset_form_fields_stay_editable(self):
        form = GeoDataSetModelForm()
        for field_name in ("relation_name", "schema_name"):
            self.assertFalse(form.fields[field_name].disabled)

    def test_form_save_with_querydict(self):
        data = QueryDict("", mutable=True)
        data.update(
            {
                "name": "QueryDict dataset",
                "region": str(self.region.pk),
                "backend_type": "local_relation",
                "schema_name": "public",
                "relation_name": "qd_features",
                "geometry_column": "geom",
                "primary_key_column": "id",
            }
        )
        form = GeoDataSetModelForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        dataset = form.save()
        self.assertEqual(dataset.runtime_configuration.relation_name, "qd_features")
