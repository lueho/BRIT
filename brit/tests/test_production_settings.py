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


class ProductionStoragesTests(SimpleTestCase):
    def test_staticfiles_overrides_base_storages_without_mutating(self):
        environment = os.environ.copy()
        environment["DJANGO_SETTINGS_MODULE"] = "brit.settings.heroku"
        environment["SECRET_KEY"] = "test-secret-key"
        environment["AWS_STORAGE_BUCKET_NAME"] = "brit-test-assets"
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import brit.settings.settings as base
import brit.settings.heroku as h

assert base.STORAGES["staticfiles"]["BACKEND"] == (
    "django.contrib.staticfiles.storage.StaticFilesStorage"
)
assert h.STORAGES["default"] is base.STORAGES["default"]
assert h.STORAGES["default"]["BACKEND"] == "storages.backends.s3boto3.S3Boto3Storage"
assert h.STORAGES["default"]["OPTIONS"]["location"] == "media"
assert h.STORAGES["staticfiles"]["BACKEND"] == "brit.storages.StaticStorage"
assert h.STORAGES["staticfiles"]["OPTIONS"]["bucket_name"] == "brit-test-assets"
assert h.STORAGES["staticfiles"]["OPTIONS"]["location"] == "static"
""",
            ],
            capture_output=True,
            check=False,
            env=environment,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
