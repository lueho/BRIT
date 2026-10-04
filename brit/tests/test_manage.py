import os
from unittest import mock

from django.test import SimpleTestCase

import manage


class ManageSettingsSelectionTests(SimpleTestCase):
    def selected_settings(self, argv):
        environment = {"DJANGO_SETTINGS_MODULE": "brit.settings.heroku"}
        with (
            mock.patch.dict(os.environ, environment, clear=True),
            mock.patch.object(manage.sys, "argv", argv),
            mock.patch("django.core.management.execute_from_command_line"),
        ):
            manage.main()
            return os.environ["DJANGO_SETTINGS_MODULE"]

    def test_test_subcommand_uses_testrunner_settings(self):
        self.assertEqual(
            self.selected_settings(["manage.py", "test", "brit"]),
            "brit.settings.testrunner",
        )

    def test_argument_named_test_keeps_configured_settings(self):
        self.assertEqual(
            self.selected_settings(["manage.py", "dumpdata", "--output", "test"]),
            "brit.settings.heroku",
        )
