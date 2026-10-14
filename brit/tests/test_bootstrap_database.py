import io
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase

CALL_COMMAND = "brit.management.commands.bootstrap_database.call_command"


class BootstrapDatabaseCommandTests(SimpleTestCase):
    def _run_stages(self):
        with mock.patch(CALL_COMMAND) as mocked_call_command:
            call_command(
                "bootstrap_database", stdout=io.StringIO(), stderr=io.StringIO()
            )
        return mocked_call_command.call_args_list

    def test_runs_migrations_and_initial_data_in_dependency_order(self):
        calls = self._run_stages()

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

    def test_all_migrations_run_noninteractively(self):
        for call in self._run_stages():
            if call.args[0] == "migrate":
                self.assertFalse(call.kwargs["interactive"])

    def test_system_checks_are_disabled(self):
        from brit.management.commands.bootstrap_database import Command

        self.assertEqual(Command.requires_system_checks, [])

    def test_failure_stops_the_sequence_and_propagates(self):
        with mock.patch(CALL_COMMAND) as mocked_call_command:
            mocked_call_command.side_effect = [None, None, RuntimeError("boom")]
            with self.assertRaises(RuntimeError):
                call_command(
                    "bootstrap_database",
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                )

        self.assertEqual(len(mocked_call_command.call_args_list), 3)

    def test_repeated_runs_reinvoke_all_stages(self):
        self._run_stages()
        calls = self._run_stages()

        self.assertEqual(len(calls), 7)
