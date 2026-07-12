import os
import subprocess
import sys

from django.test import SimpleTestCase


class ProductionCacheLoggingSettingsTests(SimpleTestCase):
    def run_production_script(self, script):
        environment = os.environ.copy()
        environment["DJANGO_SETTINGS_MODULE"] = "brit.settings.heroku"
        environment["REDIS_URL"] = "redis://localhost:6379/0"
        environment["SECRET_KEY"] = "test-secret-key"
        return subprocess.run(
            [
                sys.executable,
                "-c",
                script,
            ],
            capture_output=True,
            check=False,
            env=environment,
            text=True,
        )

    def test_ignored_redis_exceptions_are_logged(self):
        completed = self.run_production_script(
            "import brit.settings.heroku as h; "
            "assert all("
            "cache['OPTIONS']['IGNORE_EXCEPTIONS'] "
            "for cache in h.CACHES.values()"
            "); "
            "assert h.DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS is True; "
            "assert h.DJANGO_REDIS_LOGGER == 'django_redis'; "
            "assert h.LOGGING['loggers']['django_redis'] == {"
            "'handlers': ['console'], "
            "'level': 'ERROR', "
            "'propagate': False"
            "}"
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_ignored_connection_error_is_emitted_to_production_log(self):
        completed = self.run_production_script(
            """
import django
django.setup()
from django.core.cache import caches
from django_redis.exceptions import ConnectionInterrupted
from unittest.mock import Mock

cache = caches["default"]
client = Mock()
error = ConnectionInterrupted(None)
error.__cause__ = ConnectionError("redis unavailable")
client.get.side_effect = error
cache._client = client
assert cache.get("key") is None
"""
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Exception ignored", completed.stderr)
