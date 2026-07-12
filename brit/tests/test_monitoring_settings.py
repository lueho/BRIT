import os
import subprocess
import sys

from django.test import SimpleTestCase

FAKE_SENTRY_SETUP = """
import sys
import types

calls = []

class FakeDjangoIntegration:
    pass

class FakeCeleryIntegration:
    pass

sentry_sdk = types.ModuleType("sentry_sdk")
sentry_sdk.__path__ = []
sentry_sdk.init = lambda **kwargs: calls.append(kwargs)
integrations = types.ModuleType("sentry_sdk.integrations")
integrations.__path__ = []
django_integration = types.ModuleType("sentry_sdk.integrations.django")
django_integration.DjangoIntegration = FakeDjangoIntegration
celery_integration = types.ModuleType("sentry_sdk.integrations.celery")
celery_integration.CeleryIntegration = FakeCeleryIntegration
sys.modules["sentry_sdk"] = sentry_sdk
sys.modules["sentry_sdk.integrations"] = integrations
sys.modules["sentry_sdk.integrations.django"] = django_integration
sys.modules["sentry_sdk.integrations.celery"] = celery_integration
"""


class ProductionMonitoringSettingsTests(SimpleTestCase):
    def run_production_script(self, script, sentry_dsn=None):
        environment = os.environ.copy()
        environment["DJANGO_SETTINGS_MODULE"] = "brit.settings.heroku"
        environment["SECRET_KEY"] = "test-secret-key"
        if sentry_dsn is None:
            environment.pop("SENTRY_DSN", None)
        else:
            environment["SENTRY_DSN"] = sentry_dsn
        return subprocess.run(
            [sys.executable, "-c", FAKE_SENTRY_SETUP + script],
            capture_output=True,
            check=False,
            env=environment,
            text=True,
        )

    def test_sentry_initializes_django_and_celery_integrations(self):
        completed = self.run_production_script(
            """
import brit.settings.heroku

assert len(calls) == 1
options = calls[0]
assert options["dsn"] == "https://public@example.com/1"
assert options["send_default_pii"] is False
assert [type(integration).__name__ for integration in options["integrations"]] == [
    "FakeDjangoIntegration",
    "FakeCeleryIntegration",
]
""",
            sentry_dsn="https://public@example.com/1",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_sentry_stays_disabled_without_dsn(self):
        completed = self.run_production_script(
            """
import brit.settings.heroku

assert calls == []
"""
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
