import json
import os
import shlex
import socket
import subprocess
import sys
import time
from contextlib import closing
from http.client import HTTPConnection
from pathlib import Path

import yaml
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


class ProductionReleasePhaseTests(SimpleTestCase):
    def setUp(self):
        deployment = yaml.safe_load(
            (Path(settings.BASE_DIR) / "heroku.yml").read_text()
        )
        # Heroku's release phase runs only the first command entry, so every
        # release step must be chained there.
        self.release = deployment["release"]["command"][0]
        self.steps = [step.strip() for step in self.release.split("&&")]

    def test_migrations_run_first(self):
        self.assertEqual(self.steps[0], "python manage.py migrate --noinput")

    def test_waste_atlas_defaults_follow_migrations(self):
        self.assertIn(
            "python manage.py ensure_initial_data --app waste_atlas",
            self.steps[1:],
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

    def test_keepalive_is_disabled_for_single_worker_recycling(self):
        self.assertEqual(self.arguments.keepalive, 0)

    def test_idle_client_does_not_stall_worker_replacement(self):
        with closing(socket.socket()) as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        options = {
            "bind": f"127.0.0.1:{port}",
            "workers": self.arguments.workers,
            "threads": self.arguments.threads,
            "worker_class": self.arguments.worker_class,
            "keepalive": (
                Config().keepalive
                if self.arguments.keepalive is None
                else self.arguments.keepalive
            ),
            "max_requests": 3,
            "max_requests_jitter": 0,
            "timeout": 30,
            "graceful_timeout": 30,
            "control_socket_disable": True,
            "accesslog": "-",
            "errorlog": "-",
        }
        environment = {**os.environ, "GUNICORN_PROBE_OPTIONS": json.dumps(options)}
        server = subprocess.Popen(
            [
                sys.executable,
                "-c",
                """
import json
import os
from gunicorn.app.base import BaseApplication


def application(environ, start_response):
    start_response("200 OK", [("Content-Type", "text/plain"), ("Content-Length", "2")])
    return [b"OK"]


class Probe(BaseApplication):
    def load_config(self):
        for name, value in json.loads(os.environ["GUNICORN_PROBE_OPTIONS"]).items():
            self.cfg.set(name, value)

    def load(self):
        return application


Probe().run()
""",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=environment,
            text=True,
        )
        idle = None
        try:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                idle = HTTPConnection("127.0.0.1", port, timeout=1)
                try:
                    idle.request("GET", "/first")
                    response = idle.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.read(), b"OK")
                    break
                except OSError:
                    idle.close()
                    time.sleep(0.05)
            else:
                self.fail("Gunicorn probe did not start")
            for path in ("/second", "/recycle"):
                with closing(HTTPConnection("127.0.0.1", port, timeout=40)) as client:
                    client.request("GET", path, headers={"Connection": "close"})
                    response = client.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.read(), b"OK")
            time.sleep(0.2)
            with closing(HTTPConnection("127.0.0.1", port, timeout=40)) as client:
                started = time.monotonic()
                client.request("GET", "/after-recycle", headers={"Connection": "close"})
                response = client.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.read(), b"OK")
                elapsed = time.monotonic() - started
        finally:
            if idle is not None:
                idle.close()
            server.terminate()
            try:
                output, _ = server.communicate(timeout=40)
            except subprocess.TimeoutExpired:
                server.kill()
                output, _ = server.communicate()
        self.assertLess(elapsed, 5, output)
        self.assertNotIn("WORKER TIMEOUT", output)
        self.assertIn("Autorestarting worker after current request.", output)
        self.assertGreaterEqual(output.count("Booting worker with pid:"), 2)


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
