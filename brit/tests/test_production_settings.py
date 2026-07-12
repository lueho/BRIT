import os
import subprocess
import sys

from django.test import SimpleTestCase


class ProductionSecretKeyTests(SimpleTestCase):
    def test_configured_secret_key_imports_production_settings(self):
        environment = os.environ.copy()
        environment["DJANGO_SETTINGS_MODULE"] = "brit.settings.heroku"
        environment["SECRET_KEY"] = "configured-secret-key"
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import brit.settings.heroku as production_settings; "
                    "assert production_settings.SECRET_KEY == "
                    "'configured-secret-key'"
                ),
            ],
            capture_output=True,
            check=False,
            env=environment,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_missing_secret_key_fails_settings_import(self):
        environment = os.environ.copy()
        environment["DJANGO_SETTINGS_MODULE"] = "brit.settings.heroku"
        environment.pop("SECRET_KEY", None)
        completed = subprocess.run(
            [sys.executable, "-c", "import brit.settings.heroku"],
            capture_output=True,
            check=False,
            env=environment,
            text=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(
            "django.core.exceptions.ImproperlyConfigured: "
            "SECRET_KEY must be set in production.",
            completed.stderr,
        )
