import time
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from rest_framework.authtoken.models import Token

from brit.middleware import AnonymousRateLimitMiddleware

LIMIT = 3
BURST = 2
BURST_SECONDS = 5


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

    def test_x_forwarded_for_uses_last_hop(self):
        """Heroku's router appends the observed peer IP on the right; it is
        the only XFF entry the client cannot control."""
        for _ in range(LIMIT):
            self.middleware(self.request(HTTP_X_FORWARDED_FOR="9.9.9.9, 10.0.0.1"))

        same_client = self.middleware(
            self.request(HTTP_X_FORWARDED_FOR="8.8.8.8, 10.0.0.1")
        )

        self.assertEqual(same_client.status_code, 429)

    def test_spoofed_xff_prefix_cannot_open_new_buckets(self):
        """A client sending a random XFF first hop per request must still be
        limited: every request lands in the rightmost-hop bucket."""
        responses = [
            self.middleware(self.request(HTTP_X_FORWARDED_FOR=f"10.1.2.{i}, 10.0.0.1"))
            for i in range(LIMIT + 3)
        ]

        statuses = [r.status_code for r in responses]
        self.assertEqual(statuses.count(200), LIMIT)
        self.assertEqual(statuses.count(429), 3)

    def test_cf_connecting_ip_used_when_cf_ray_present(self):
        """Cloudflare-fronted traffic carries the real client IP in
        CF-Connecting-IP; the rightmost XFF is the shared CF edge IP."""
        for _ in range(LIMIT):
            self.middleware(
                self.request(
                    HTTP_CF_CONNECTING_IP="1.2.3.4",
                    HTTP_CF_RAY="abc123-FRA",
                    HTTP_X_FORWARDED_FOR="1.2.3.4, 172.70.0.9",
                )
            )

        other_cf_client = self.middleware(
            self.request(
                HTTP_CF_CONNECTING_IP="5.6.7.8",
                HTTP_CF_RAY="abc123-FRA",
                HTTP_X_FORWARDED_FOR="5.6.7.8, 172.70.0.9",
            )
        )

        self.assertEqual(other_cf_client.status_code, 200)

    def test_cf_connecting_ip_ignored_without_cf_ray(self):
        """A direct-origin request may forge CF-Connecting-IP; without the
        accompanying CF-RAY it must fall back to the rightmost XFF."""
        for _ in range(LIMIT):
            self.middleware(self.request(HTTP_X_FORWARDED_FOR="10.0.0.1"))

        forged = self.middleware(
            self.request(
                HTTP_CF_CONNECTING_IP="1.2.3.4",
                HTTP_X_FORWARDED_FOR="10.0.0.1",
            )
        )

        self.assertEqual(forged.status_code, 429)

    @override_settings(
        ANONYMOUS_RATE_LIMIT_BURST=BURST,
        ANONYMOUS_RATE_LIMIT_BURST_SECONDS=BURST_SECONDS,
    )
    def test_burst_limit_throttles_before_minute_limit(self):
        """The short window prevents front-loading the whole minute budget;
        request BURST+1 in one window is rejected even with LIMIT far away."""
        for _ in range(BURST):
            response = self.middleware(self.request())
            self.assertEqual(response.status_code, 200)

        response = self.middleware(self.request())

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Retry-After"], str(BURST_SECONDS))

    @override_settings(
        ANONYMOUS_RATE_LIMIT_PER_MINUTE=60,
        ANONYMOUS_RATE_LIMIT_BURST=5,
        ANONYMOUS_RATE_LIMIT_BURST_SECONDS=5,
    )
    def test_production_default_caps_burst(self):
        """Under the production defaults, 60 rapid-fire requests cannot all
        pass: the burst window starts rejecting at request 6."""
        responses = [self.middleware(self.request()) for _ in range(60)]

        statuses = [r.status_code for r in responses]
        self.assertEqual(statuses.count(200), 5)
        self.assertEqual(statuses.count(429), 55)

    @override_settings(
        ANONYMOUS_RATE_LIMIT_PER_MINUTE=10,
        ANONYMOUS_RATE_LIMIT_BURST=BURST,
        ANONYMOUS_RATE_LIMIT_BURST_SECONDS=BURST_SECONDS,
    )
    def test_burst_window_recovers_after_rollover(self):
        for _ in range(BURST):
            self.middleware(self.request())
        self.assertEqual(self.middleware(self.request()).status_code, 429)

        now = time.time()
        with patch("brit.middleware.time.time", return_value=now + BURST_SECONDS + 1):
            response = self.middleware(self.request())

        self.assertEqual(response.status_code, 200)

    @override_settings(ANONYMOUS_RATE_LIMIT_BURST=0)
    def test_zero_burst_disables_burst_check(self):
        for _ in range(LIMIT):
            response = self.middleware(self.request())

            self.assertEqual(response.status_code, 200)

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


@override_settings(ANONYMOUS_RATE_LIMIT_PER_MINUTE=LIMIT)
class DrfTokenRateLimitTests(TestCase):
    """DRF TokenAuthentication runs inside the API view, after middleware;
    a valid token client must still count as authenticated here."""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = AnonymousRateLimitMiddleware(
            lambda request: HttpResponse("ok")
        )
        cache.clear()

    def test_valid_drf_token_is_not_limited(self):
        user = User.objects.create_user(username="api-client")
        token = Token.objects.create(user=user)

        for _ in range(LIMIT + 2):
            response = self.middleware(
                self.factory.get("/api/x/", HTTP_AUTHORIZATION=f"Token {token.key}")
            )

            self.assertEqual(response.status_code, 200)

    def test_invalid_token_is_limited_by_ip(self):
        """A forged Authorization header must not bypass the limit; the
        request stays in the IP bucket."""
        for _ in range(LIMIT):
            self.middleware(
                self.factory.get("/x/", HTTP_AUTHORIZATION="Token deadbeef")
            )

        response = self.middleware(
            self.factory.get("/x/", HTTP_AUTHORIZATION="Token deadbeef")
        )

        self.assertEqual(response.status_code, 429)
