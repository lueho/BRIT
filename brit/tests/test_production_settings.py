import json
import os
import shlex
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from http.client import HTTPConnection
from pathlib import Path
from unittest import mock

import yaml
from django.conf import settings
from django.test import SimpleTestCase
from gunicorn.config import Config
from gunicorn.workers.gthread import ThreadWorker

from brit.gunicorn import SocketTimeoutThreadWorker


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
        self.assertEqual(
            self.arguments.worker_class,
            "brit.gunicorn.SocketTimeoutThreadWorker",
        )
        self.assertTrue(issubclass(SocketTimeoutThreadWorker, ThreadWorker))

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

    def test_stalled_response_clients_do_not_block_new_requests(self):
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
            "max_requests": self.arguments.max_requests,
            "max_requests_jitter": self.arguments.max_requests_jitter,
            "timeout": 30,
            "graceful_timeout": 30,
            "control_socket_disable": True,
            "accesslog": "-",
            "errorlog": "-",
            # Probe-harness setting, not a Gunicorn one: applied as
            # worker_class.socket_timeout in the subprocess. Plain gthread
            # ignores it; the production worker bounds socket operations with
            # it so stalled clients cannot occupy every worker thread.
            "socket_timeout": 0.25,
        }
        environment = {**os.environ, "GUNICORN_PROBE_OPTIONS": json.dumps(options)}
        output = tempfile.TemporaryFile(mode="w+")
        server = subprocess.Popen(
            [
                sys.executable,
                "-c",
                """
import json
import os
from gunicorn.app.base import BaseApplication
from gunicorn.util import load_class

options = json.loads(os.environ["GUNICORN_PROBE_OPTIONS"])
worker_class = load_class(options.pop("worker_class"))
worker_class.socket_timeout = options.pop("socket_timeout")
options["worker_class"] = worker_class

LARGE = 8 * 1024 * 1024
CHUNK = 64 * 1024


def application(environ, start_response):
    if environ.get("PATH_INFO") == "/large":
        print("LARGE-REQUEST-START", flush=True)
        start_response("200 OK", [("Content-Type", "application/octet-stream"),
                                  ("Content-Length", str(LARGE))])
        return (b"x" * CHUNK for _ in range(LARGE // CHUNK))
    start_response("200 OK", [("Content-Type", "text/plain"),
                              ("Content-Length", "2")])
    return [b"OK"]


class Probe(BaseApplication):
    def load_config(self):
        for name, value in options.items():
            self.cfg.set(name, value)

    def load(self):
        return application


Probe().run()
""",
            ],
            stdout=output,
            stderr=subprocess.STDOUT,
            env=environment,
            text=True,
        )
        stalled = []
        try:
            deadline = time.monotonic() + 15
            while True:
                with closing(HTTPConnection("127.0.0.1", port, timeout=1)) as client:
                    try:
                        client.request("GET", "/ok")
                        response = client.getresponse()
                        if response.status == 200 and response.read() == b"OK":
                            break
                    except OSError:
                        pass
                if time.monotonic() > deadline:
                    self.fail("Gunicorn probe did not start")
                time.sleep(0.05)
            for _ in range(self.arguments.threads):
                client = socket.create_connection(("127.0.0.1", port), timeout=5)
                client.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
                client.sendall(
                    b"GET /large HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                    b"Connection: close\r\n\r\n"
                )
                stalled.append(client)
            # Wait until every stalled request actually entered the app so
            # the probe cannot pass while worker threads never engaged.
            deadline = time.monotonic() + 10
            while True:
                # pread leaves the shared file offset alone while the child
                # process is still writing its logs to the same file.
                log_so_far = os.pread(
                    output.fileno(), os.fstat(output.fileno()).st_size, 0
                )
                if log_so_far.count(b"LARGE-REQUEST-START") >= self.arguments.threads:
                    break
                if time.monotonic() > deadline:
                    self.fail("worker threads never started the /large responses")
                time.sleep(0.05)
            with closing(HTTPConnection("127.0.0.1", port, timeout=3)) as client:
                client.request("GET", "/ok", headers={"Connection": "close"})
                response = client.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.read(), b"OK")
        finally:
            for client in stalled:
                client.close()
            server.terminate()
            try:
                server.wait(timeout=40)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
            output.seek(0)
            server_log = output.read()
            output.close()
        self.assertEqual(
            server_log.count("LARGE-REQUEST-START"), self.arguments.threads, server_log
        )
        self.assertEqual(server_log.count("Booting worker with pid:"), 1, server_log)
        self.assertNotIn("WORKER TIMEOUT", server_log)


class SocketTimeoutThreadWorkerTests(SimpleTestCase):
    def setUp(self):
        # __new__ skips the Gunicorn worker __init__ that needs a live socket.
        self.worker = SocketTimeoutThreadWorker.__new__(SocketTimeoutThreadWorker)

    def test_inherits_gthread_worker_with_bounded_socket_timeout(self):
        self.assertTrue(issubclass(SocketTimeoutThreadWorker, ThreadWorker))
        self.assertEqual(SocketTimeoutThreadWorker.socket_timeout, 10)

    def test_socket_timeout_is_set_before_delegating_to_parent(self):
        connection = mock.Mock()
        request = mock.Mock()
        calls = mock.Mock()
        calls.attach_mock(connection.sock.settimeout, "settimeout")
        with mock.patch.object(ThreadWorker, "handle_request") as parent:
            calls.attach_mock(parent, "parent_handle_request")
            self.worker.handle_request(request, connection)
        calls.assert_has_calls(
            [
                mock.call.settimeout(10),
                mock.call.parent_handle_request(request, connection),
            ]
        )

    def test_parent_result_is_returned_and_connection_stays_open(self):
        connection = mock.Mock()
        request = mock.Mock()
        with mock.patch.object(
            ThreadWorker, "handle_request", return_value="keep-alive"
        ) as parent:
            result = self.worker.handle_request(request, connection)
        self.assertEqual(result, "keep-alive")
        parent.assert_called_once_with(request, connection)
        connection.close.assert_not_called()

    def test_timed_out_response_closes_connection_and_reraises(self):
        connection = mock.Mock()
        request = mock.Mock()
        error = TimeoutError("timed out")
        with mock.patch.object(ThreadWorker, "handle_request", side_effect=error):
            with self.assertRaises(TimeoutError) as raised:
                self.worker.handle_request(request, connection)
        self.assertIs(raised.exception, error)
        connection.close.assert_called_once_with()


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
