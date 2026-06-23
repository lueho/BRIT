import ssl
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase

from brit.settings.settings import (
    _redis_connection_pool_kwargs,
    _redis_ssl_settings,
)


class RedisSettingsTests(SimpleTestCase):
    def test_configured_test_database_settings_include_atomic_requests_default(self):
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
