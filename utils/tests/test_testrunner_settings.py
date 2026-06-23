from django.conf import settings
from django.test import SimpleTestCase


class TestRunnerSettingsTests(SimpleTestCase):
    def test_caches_use_local_memory_backend(self):
        self.assertEqual(
            settings.CACHES["default"]["BACKEND"],
            "django.core.cache.backends.locmem.LocMemCache",
        )
        self.assertEqual(
            settings.CACHES["geojson"]["BACKEND"],
            "django.core.cache.backends.locmem.LocMemCache",
        )
