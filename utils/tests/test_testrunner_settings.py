from django.conf import settings
from django.core.cache import caches
from django.test import SimpleTestCase


class TestRunnerSettingsTests(SimpleTestCase):
    def test_default_cache_uses_local_memory_backend(self):
        self.assertEqual(
            settings.CACHES["default"]["BACKEND"],
            "django.core.cache.backends.locmem.LocMemCache",
        )

    def test_database_settings_include_django_connection_defaults(self):
        self.assertFalse(settings.DATABASES["default"]["ATOMIC_REQUESTS"])
        self.assertTrue(settings.DATABASES["default"]["AUTOCOMMIT"])
        self.assertEqual(settings.DATABASES["default"]["CONN_MAX_AGE"], 0)
        self.assertFalse(settings.DATABASES["default"]["CONN_HEALTH_CHECKS"])
        self.assertEqual(settings.DATABASES["default"]["OPTIONS"], {})
        self.assertIsNone(settings.DATABASES["default"]["TIME_ZONE"])

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
        self.assertFalse(cache_config["OPTIONS"]["IGNORE_EXCEPTIONS"])
        self.assertTrue(callable(getattr(caches["geojson"], "delete_pattern", None)))
