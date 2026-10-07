import os
import shlex
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from gunicorn.config import Config


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


class ProductionWebMemoryTests(SimpleTestCase):
    def setUp(self):
        deployment = (Path(settings.BASE_DIR) / "heroku.yml").read_text()
        command = next(
            line.split(":", 1)[1]
            for line in deployment.splitlines()
            if line.startswith("  web:")
        )
        arguments = shlex.split(command)
        self.assertEqual(arguments[0], "gunicorn")
        self.arguments = Config().parser().parse_args(arguments[1:])

    def test_threads_share_one_application_process(self):
        self.assertEqual(self.arguments.workers, 1)
        self.assertEqual(self.arguments.threads, 4)

    def test_threaded_worker_is_explicit(self):
        self.assertEqual(self.arguments.worker_class, "gthread")

    def test_requests_trigger_bounded_worker_recycling(self):
        self.assertEqual(self.arguments.max_requests, 1000)
        self.assertEqual(self.arguments.max_requests_jitter, 100)


class ProductionReleasePhaseTests(SimpleTestCase):
    def release_commands(self):
        deployment = (Path(settings.BASE_DIR) / "heroku.yml").read_text()
        release = deployment.split("\nrelease:\n", 1)[1].split("\nrun:\n", 1)[0]
        return [
            line.strip()[2:]
            for line in release.splitlines()
            if line.strip().startswith("- ")
        ]

    def test_release_runs_migrations_and_collectstatic_in_one_command(self):
        # Heroku runs only the first entry of a release command list, so a
        # second entry such as collectstatic would silently never run.
        commands = self.release_commands()
        self.assertEqual(len(commands), 1, commands)
        steps = [shlex.split(step) for step in commands[0].split("&&")]
        self.assertEqual(
            steps,
            [
                ["python", "manage.py", "migrate", "--noinput"],
                ["python", "manage.py", "collectstatic", "--noinput"],
            ],
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
