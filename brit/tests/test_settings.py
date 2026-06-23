import ssl

from django.test import SimpleTestCase

from brit.settings.settings import (
    _redis_connection_pool_kwargs,
    _redis_ssl_settings,
)


class RedisSettingsTests(SimpleTestCase):
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
