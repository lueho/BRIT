import logging

from django.conf import settings
from django.http import Http404, HttpResponsePermanentRedirect

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
