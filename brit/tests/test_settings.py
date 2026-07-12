import os
import ssl
import subprocess
import sys
from importlib import import_module

from django.conf import settings
from django.test import SimpleTestCase

from brit.settings.settings import (
    _redis_connection_pool_kwargs,
    _redis_ssl_settings,
)


class EnvironmentSettingsTests(SimpleTestCase):
    def run_settings_assertions(self, environment, assertions):
        return subprocess.run(
            [
                sys.executable,
                "-c",
                f"import brit.settings.settings as s; {assertions}",
            ],
            capture_output=True,
            check=False,
            env=environment,
            text=True,
        )

    def test_false_email_ssl_and_missing_admins_are_typed_safely(self):
        environment = os.environ.copy()
        environment["EMAIL_USE_SSL"] = "false"
        environment.pop("ADMIN_NAME", None)
        environment.pop("ADMIN_EMAIL", None)
        completed = self.run_settings_assertions(
            environment,
            "assert s.EMAIL_USE_SSL is False; assert s.ADMINS == []",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_true_email_ssl_and_complete_admin_are_preserved(self):
        environment = os.environ.copy()
        environment["EMAIL_USE_SSL"] = "true"
        environment["ADMIN_NAME"] = "BRIT operations"
        environment["ADMIN_EMAIL"] = "operations@example.com"
        completed = self.run_settings_assertions(
            environment,
            (
                "assert s.EMAIL_USE_SSL is True; "
                "assert s.ADMINS == [('BRIT operations', 'operations@example.com')]"
            ),
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)


class RedisSettingsTests(SimpleTestCase):
    def test_importing_local_settings_does_not_mutate_testrunner_database_settings(
        self,
    ):
        local_settings = import_module("brit.settings.local")

        self.assertIsNot(settings.DATABASES, local_settings.DATABASES)
        self.assertFalse(settings.DATABASES["default"]["ATOMIC_REQUESTS"])

    def test_raw_testrunner_database_settings_include_atomic_requests_default(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import brit.settings.testrunner as t; "
                    "assert t.DATABASES['default']['ATOMIC_REQUESTS'] is False"
                ),
            ],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_plain_redis_url_does_not_use_ssl_options(self):
        self.assertEqual(_redis_connection_pool_kwargs("redis://localhost:6379/0"), {})
        self.assertIsNone(_redis_ssl_settings("redis://localhost:6379/0"))

    def test_tls_redis_url_uses_ssl_options(self):
        self.assertEqual(
            _redis_connection_pool_kwargs("rediss://localhost:6379/0"),
            {"ssl_cert_reqs": None},
        )
        self.assertEqual(
            _redis_ssl_settings("rediss://localhost:6379/0"),
            {"ssl_cert_reqs": ssl.CERT_NONE},
        )


class ProductionRedisSettingsTests(SimpleTestCase):
    def test_tls_redis_requires_certificate_verification(self):
        environment = os.environ.copy()
        environment["REDIS_URL"] = "rediss://localhost:6379/0"
        environment["SECRET_KEY"] = "test-secret-key"
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import ssl; import brit.settings.heroku as h; "
                    "expected = {'ssl_cert_reqs': ssl.CERT_REQUIRED}; "
                    "assert h.CELERY_BROKER_USE_SSL == expected; "
                    "assert h.CELERY_REDIS_BACKEND_USE_SSL == expected"
                ),
            ],
            capture_output=True,
            check=False,
            env=environment,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
