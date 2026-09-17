from types import SimpleNamespace
from unittest.mock import patch

from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from brit.middleware import AnonymousRateLimitMiddleware

LIMIT = 3


@override_settings(ANONYMOUS_RATE_LIMIT_PER_MINUTE=LIMIT)
class AnonymousRateLimitMiddlewareTests(SimpleTestCase):
    """Per-IP fixed-window throttle for anonymous requests.

    Scraper traffic of ~10+ req/s against one web dyno queued requests past
    the 30s router timeout (H12 "critical incidents"); the limit caps how
    much work one anonymous IP can create per minute.
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = AnonymousRateLimitMiddleware(
            lambda request: HttpResponse("ok")
        )
        cache.clear()

    def request(self, path="/x/", **kwargs):
        return self.factory.get(path, **kwargs)

    def test_requests_up_to_limit_pass(self):
        for _ in range(LIMIT):
            response = self.middleware(self.request())

            self.assertEqual(response.status_code, 200)

    def test_request_over_limit_gets_429_with_retry_after(self):
        for _ in range(LIMIT):
            self.middleware(self.request())

        response = self.middleware(self.request())

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Retry-After"], "60")

    def test_different_ips_have_separate_buckets(self):
        for _ in range(LIMIT):
            self.middleware(self.request(HTTP_X_FORWARDED_FOR="1.2.3.4"))

        other = self.middleware(self.request(HTTP_X_FORWARDED_FOR="5.6.7.8"))

        self.assertEqual(other.status_code, 200)

    def test_x_forwarded_for_uses_first_hop(self):
        for _ in range(LIMIT):
            self.middleware(self.request(HTTP_X_FORWARDED_FOR="9.9.9.9, 10.0.0.1"))

        same_client = self.middleware(
            self.request(HTTP_X_FORWARDED_FOR="9.9.9.9, 172.16.0.5")
        )

        self.assertEqual(same_client.status_code, 429)

    def test_authenticated_users_are_not_limited(self):
        request = self.request()
        request.user = SimpleNamespace(is_authenticated=True)
        for _ in range(LIMIT + 2):
            response = self.middleware(request)

            self.assertEqual(response.status_code, 200)

    def test_health_check_is_exempt(self):
        for _ in range(LIMIT + 2):
            response = self.middleware(self.request("/health/"))

            self.assertEqual(response.status_code, 200)

    @override_settings(ANONYMOUS_RATE_LIMIT_PER_MINUTE=0)
    def test_noop_when_limit_is_zero(self):
        for _ in range(10):
            response = self.middleware(self.request())

            self.assertEqual(response.status_code, 200)

    def test_cache_failure_fails_open(self):
        with patch("brit.middleware.cache.add", side_effect=ConnectionError):
            for _ in range(LIMIT + 2):
                response = self.middleware(self.request())

                self.assertEqual(response.status_code, 200)
