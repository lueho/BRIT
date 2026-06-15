import ssl

from django.test import SimpleTestCase

from brit.settings.settings import _build_redis_cache_options


class RedisCacheOptionsTests(SimpleTestCase):
    def test_plain_redis_url_does_not_receive_ssl_connection_kwargs(self):
        options = _build_redis_cache_options("redis://redis:6379/0")

        self.assertNotIn("CONNECTION_POOL_KWARGS", options)

    def test_rediss_url_receives_ssl_connection_kwargs(self):
        options = _build_redis_cache_options("rediss://redis:6379/0")

        self.assertEqual(
            options["CONNECTION_POOL_KWARGS"],
            {"ssl_cert_reqs": ssl.CERT_NONE},
        )
