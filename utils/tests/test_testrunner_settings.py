from django.conf import settings
from django.core.cache import caches
from django.test import SimpleTestCase


class TestRunnerSettingsTests(SimpleTestCase):
    def test_default_cache_uses_local_memory_backend(self):
        self.assertEqual(
            settings.CACHES["default"]["BACKEND"],
            "django.core.cache.backends.locmem.LocMemCache",
        )

    def test_geojson_cache_uses_plain_test_redis_backend(self):
        cache_config = settings.CACHES["geojson"]
        self.assertEqual(
            cache_config["BACKEND"],
            "django_redis.cache.RedisCache",
        )
        self.assertIn(
            cache_config["LOCATION"].split(":", maxsplit=1)[0],
            {"redis", "rediss"},
        )
        self.assertNotIn(
            "CONNECTION_POOL_KWARGS",
            cache_config.get("OPTIONS", {}),
        )
        self.assertTrue(callable(getattr(caches["geojson"], "delete_pattern", None)))
