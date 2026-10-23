import io
from unittest import mock

from django.core.management import call_command
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.test import SimpleTestCase

CALL_COMMAND = "brit.management.commands.bootstrap_database.call_command"
LEGACY_HELPER = (
    "brit.management.commands.bootstrap_database.Command._requires_legacy_bootstrap"
)

SQUASHED_KEYS = {
    ("properties", "0001_squashed_0010"),
    ("materials", "0001_squashed_0032"),
    ("waste_atlas", "0001_squashed_0027"),
    ("maps", "0001_squashed_0020"),
    ("processes", "0001_squashed_0016"),
    ("inventories", "0001_squashed_0008"),
    ("distributions", "0001_squashed_0004"),
    ("layer_manager", "0001_squashed_0004"),
    ("object_management", "0001_squashed_0006"),
    ("closecycle", "0001_squashed_0007"),
    ("population", "0001_squashed_0002"),
    ("waste_collection", "0001_squashed_0008"),
}


class BootstrapDatabaseCommandTests(SimpleTestCase):
    def _run_stages(self, legacy=False):
        with (
            mock.patch(CALL_COMMAND) as mocked_call_command,
            mock.patch(LEGACY_HELPER, return_value=legacy, create=True),
        ):
            call_command(
                "bootstrap_database", stdout=io.StringIO(), stderr=io.StringIO()
            )
        return mocked_call_command.call_args_list

    def test_normal_path_migrates_then_ensures_all_initial_data(self):
        calls = self._run_stages()

        commands = [call.args[0] for call in calls]
        self.assertEqual(commands, ["migrate", "ensure_initial_data"])
        self.assertEqual(calls[0].args[1:], ())
        self.assertFalse(calls[0].kwargs["interactive"])
        self.assertEqual(calls[1].args[1:], ())
        self.assertNotIn("app_label", calls[1].kwargs)
        for call in calls:
            self.assertIn("stdout", call.kwargs)
            self.assertIn("verbosity", call.kwargs)

    def test_system_checks_are_disabled(self):
        from brit.management.commands.bootstrap_database import Command

        self.assertEqual(Command.requires_system_checks, [])

    def test_failure_stops_the_sequence_and_propagates(self):
        with (
            mock.patch(CALL_COMMAND) as mocked_call_command,
            mock.patch(LEGACY_HELPER, return_value=False, create=True),
        ):
            mocked_call_command.side_effect = [None, RuntimeError("boom")]
            with self.assertRaises(RuntimeError):
                call_command(
                    "bootstrap_database",
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                )

        self.assertEqual(len(mocked_call_command.call_args_list), 2)

    def test_repeated_runs_reinvoke_all_stages(self):
        self._run_stages()
        calls = self._run_stages()

        self.assertEqual(len(calls), 2)

    def test_legacy_path_runs_staged_migrations_and_initializers(self):
        calls = self._run_stages(legacy=True)

        commands = [call.args[0] for call in calls]
        self.assertEqual(
            commands,
            [
                "migrate",
                "ensure_initial_data",
                "ensure_initial_data",
                "migrate",
                "ensure_initial_data",
                "migrate",
                "ensure_initial_data",
            ],
        )
        self.assertEqual(calls[0].args[1:], ("auth",))
        self.assertEqual(calls[1].kwargs["app_label"], "users")
        self.assertEqual(calls[2].kwargs["app_label"], "object_management")
        self.assertEqual(calls[3].args[1:], ("properties",))
        self.assertEqual(calls[4].kwargs["app_label"], "properties")
        self.assertEqual(calls[5].args[1:], ())
        self.assertNotIn("app_label", calls[6].kwargs)
        for call in calls:
            if call.args[0] == "migrate":
                self.assertFalse(call.kwargs["interactive"])


class LegacyBootstrapDetectionTests(SimpleTestCase):
    """Selection between normal and legacy stages from the migration graph."""

    def _requires_legacy(self, applied):
        from brit.management.commands.bootstrap_database import Command

        with mock.patch.object(
            MigrationRecorder,
            "applied_migrations",
            return_value=dict.fromkeys(applied),
        ):
            return Command()._requires_legacy_bootstrap()

    def _disk_keys(self):
        return set(MigrationLoader(None).disk_migrations)

    def test_fresh_database_without_records_uses_normal_stages(self):
        self.assertFalse(self._requires_legacy(set()))

    def test_all_originals_applied_without_markers_uses_normal_stages(self):
        applied = self._disk_keys() - SQUASHED_KEYS
        self.assertFalse(self._requires_legacy(applied))

    def test_partial_properties_history_uses_legacy_stages(self):
        applied = (
            self._disk_keys()
            - SQUASHED_KEYS
            - {
                ("properties", "0008_materialproperty_unit_optional"),
                ("properties", "0009_collection_point_property"),
                ("properties", "0010_remove_property_unit"),
            }
        )
        self.assertTrue(self._requires_legacy(applied))

    def test_partial_materials_history_uses_legacy_stages(self):
        applied = (
            self._disk_keys()
            - SQUASHED_KEYS
            - {
                ("materials", "0030_product_material_category"),
                ("materials", "0031_sample_region_sample_site"),
                ("materials", "0032_sampleauthor_sample_authors_and_more"),
            }
        )
        self.assertTrue(self._requires_legacy(applied))
