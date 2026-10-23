import ssl
from importlib import import_module

from django.conf import settings
from django.test import SimpleTestCase

from brit.settings.settings import (
    _redis_connection_pool_kwargs,
    _redis_ssl_settings,
)
from brit.tests.probes import run_settings_probe


class EnvironmentSettingsTests(SimpleTestCase):
    def run_settings_assertions(self, env, assertions):
        return run_settings_probe(
            f"import brit.settings.settings as s; {assertions}", env=env
        )

    def test_false_email_ssl_and_missing_admins_are_typed_safely(self):
        completed = self.run_settings_assertions(
            {"EMAIL_USE_SSL": "false", "ADMIN_NAME": None, "ADMIN_EMAIL": None},
            "assert s.EMAIL_USE_SSL is False; assert s.ADMINS == []",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_true_email_ssl_and_complete_admin_are_preserved(self):
        completed = self.run_settings_assertions(
            {
                "EMAIL_USE_SSL": "true",
                "ADMIN_NAME": "BRIT operations",
                "ADMIN_EMAIL": "operations@example.com",
            },
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
        completed = run_settings_probe(
            "import brit.settings.testrunner as t; "
            "assert t.DATABASES['default']['ATOMIC_REQUESTS'] is False"
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
    def test_tls_redis_accepts_self_signed_certificates(self):
        completed = run_settings_probe(
            "import ssl; import brit.settings.heroku as h; "
            "expected = {'ssl_cert_reqs': ssl.CERT_NONE}; "
            "assert h.CELERY_BROKER_USE_SSL == expected; "
            "assert h.CELERY_REDIS_BACKEND_USE_SSL == expected",
            env={
                "REDIS_URL": "rediss://localhost:6379/0",
                "SECRET_KEY": "test-secret-key",
            },
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)


class LocalSettingsTests(SimpleTestCase):
    def run_local_assertions(self, env, assertions):
        return run_settings_probe(
            f"import brit.settings.local as s; {assertions}", env=env
        )

    def test_local_uses_filesystem_media_storage(self):
        completed = self.run_local_assertions(
            {},
            (
                "assert s.STORAGES['default']['BACKEND'] == "
                "'django.core.files.storage.FileSystemStorage'; "
                "assert s.MEDIA_URL == '/media/'; "
                "assert s.MEDIA_ROOT"
            ),
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_local_uses_console_email_backend_without_smtp_host(self):
        completed = self.run_local_assertions(
            {"EMAIL_HOST": None},
            (
                "assert s.EMAIL_BACKEND == "
                "'django.core.mail.backends.console.EmailBackend'"
            ),
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_local_preserves_explicit_smtp_configuration(self):
        completed = self.run_local_assertions(
            {"EMAIL_HOST": "smtp.example.org"},
            (
                "assert s.EMAIL_BACKEND == "
                "'django.core.mail.backends.smtp.EmailBackend'; "
                "assert s.EMAIL_HOST == 'smtp.example.org'"
            ),
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
