import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.http import Http404, HttpResponse, HttpResponsePermanentRedirect

logger = logging.getLogger(__name__)


class CanonicalHostRedirectMiddleware:
    """308-redirect requests on non-canonical hosts to ``CANONICAL_HOST``.

    Uses ``preserve_request=True`` (308 Permanent Redirect) so non-GET
    requests keep method and body — a 301 could silently downgrade a POST
    to GET. No-ops when ``CANONICAL_HOST`` is unset, so development and
    tests are unaffected. ``/health/`` is exempt so load-balancer and
    container health checks keep working on any host.
    """

    EXEMPT_PATHS = frozenset({"/health/"})

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        canonical = getattr(settings, "CANONICAL_HOST", "").strip()
        if (
            canonical
            and request.path not in self.EXEMPT_PATHS
            and request.get_host().split(":")[0].lower() != canonical.lower()
        ):
            return HttpResponsePermanentRedirect(
                f"https://{canonical}{request.get_full_path()}",
                preserve_request=True,
            )
        return self.get_response(request)


class AnonymousRateLimitMiddleware:
    """Fixed-window per-IP rate limit for anonymous requests.

    Scraper traffic saturates the single web dyno and queues requests past
    the router timeout; the limit caps how much work one anonymous client IP
    can create. Two windows apply: a per-minute cap
    (``ANONYMOUS_RATE_LIMIT_PER_MINUTE``) and a short burst cap
    (``ANONYMOUS_RATE_LIMIT_BURST`` per
    ``ANONYMOUS_RATE_LIMIT_BURST_SECONDS``) so a client cannot front-load
    the whole minute budget into one worker-saturating burst. With the
    production defaults (60/min, 5/5s) the sustained rate is identical —
    the burst window only flattens the shape. Place after
    AuthenticationMiddleware so session users are not limited; requests
    carrying a valid DRF token are exempt too, because DRF authenticates
    only inside the view.

    ``ANONYMOUS_RATE_LIMIT_PER_MINUTE`` 0/unset disables limiting entirely,
    so development and tests are unaffected. ``/health/`` is exempt. Cache
    failures fail open — a broken cache must not take the site down.
    """

    EXEMPT_PATHS = frozenset({"/health/"})
    WINDOW_SECONDS = 60

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        limit = getattr(settings, "ANONYMOUS_RATE_LIMIT_PER_MINUTE", 0)
        if (
            not limit
            or request.path in self.EXEMPT_PATHS
            or self._is_authenticated(request)
        ):
            return self.get_response(request)

        client_ip = self._client_ip(request)
        retry_after = self._limited(client_ip, "min", self.WINDOW_SECONDS, limit)
        burst = getattr(settings, "ANONYMOUS_RATE_LIMIT_BURST", 0)
        if not retry_after and burst:
            burst_seconds = getattr(settings, "ANONYMOUS_RATE_LIMIT_BURST_SECONDS", 5)
            retry_after = self._limited(client_ip, "burst", burst_seconds, burst)
        if retry_after:
            return HttpResponse(
                "Too Many Requests",
                status=429,
                headers={"Retry-After": str(retry_after)},
            )
        return self.get_response(request)

    @staticmethod
    def _limited(client_ip, namespace, window_seconds, limit):
        """Increment this window's counter; return the window length as
        Retry-After when ``limit`` is exceeded, else 0. Fails open on
        cache errors."""
        window = int(time.time() // window_seconds)
        key = f"anon-rl:{namespace}:{client_ip}:{window}"
        try:
            cache.add(key, 0, timeout=window_seconds * 2)
            count = cache.incr(key)
        except Exception:
            return 0
        return window_seconds if count and count > limit else 0

    @staticmethod
    def _is_authenticated(request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            return True
        if "HTTP_AUTHORIZATION" not in request.META:
            return False
        # DRF resolves TokenAuthentication inside the API view, after this
        # middleware runs. Check the header here so valid API clients are
        # exempt; invalid tokens stay anonymous and IP-limited.
        try:
            from rest_framework.authentication import TokenAuthentication

            return TokenAuthentication().authenticate(request) is not None
        except Exception:
            return False

    @staticmethod
    def _client_ip(request):
        """Client identity for rate limiting.

        Cloudflare-fronted traffic: Cloudflare overwrites any
        client-supplied ``CF-Connecting-IP`` with the real client IP, so it
        is trusted when ``CF-RAY`` is also present — required anyway, since
        the rightmost XFF entry on that path is a shared CF edge IP.
        Direct traffic: Heroku's router appends the observed peer IP on the
        right of ``X-Forwarded-For``, so the LAST entry is the only one the
        client cannot control; earlier entries can be forged per request.
        """
        cf_ip = request.META.get("HTTP_CF_CONNECTING_IP", "")
        if cf_ip and request.META.get("HTTP_CF_RAY"):
            return cf_ip.strip()
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[-1].strip()
        return request.META.get("REMOTE_ADDR", "")


class ExceptionLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if isinstance(exception, Http404):
            return None
        logger.exception("Unhandled exception:", exc_info=exception)
        return None
