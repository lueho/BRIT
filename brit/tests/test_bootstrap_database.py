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
        with mock.patch(CALL_COMMAND) as mocked_call_command:
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
