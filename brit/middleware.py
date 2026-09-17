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
    can create per minute. Place after AuthenticationMiddleware so
    authenticated users are not limited.

    Controlled by ``ANONYMOUS_RATE_LIMIT_PER_MINUTE``: 0/unset disables
    limiting entirely, so development and tests are unaffected. ``/health/``
    is exempt. Cache failures fail open — a broken cache must not take the
    site down.
    """

    EXEMPT_PATHS = frozenset({"/health/"})
    WINDOW_SECONDS = 60

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        limit = getattr(settings, "ANONYMOUS_RATE_LIMIT_PER_MINUTE", 0)
        user = getattr(request, "user", None)
        if (
            not limit
            or request.path in self.EXEMPT_PATHS
            or (user is not None and user.is_authenticated)
        ):
            return self.get_response(request)

        window = int(time.time() // self.WINDOW_SECONDS)
        key = f"anon-rl:{self._client_ip(request)}:{window}"
        try:
            cache.add(key, 0, timeout=self.WINDOW_SECONDS * 2)
            count = cache.incr(key)
        except Exception:
            return self.get_response(request)
        if count and count > limit:
            return HttpResponse(
                "Too Many Requests",
                status=429,
                headers={"Retry-After": str(self.WINDOW_SECONDS)},
            )
        return self.get_response(request)

    @staticmethod
    def _client_ip(request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
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
