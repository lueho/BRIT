import logging
import time

logger = logging.getLogger(__name__)


class CacheMonitoringMiddleware:
    """Middleware to monitor cache hit rates and performance for geojson paths."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()

        response = self.get_response(request)

        if 'geojson' in request.path:
            duration = time.time() - start_time

            cache_status = response.get('X-Cache-Status', 'UNKNOWN')
            response['X-Cache-Time'] = f"{duration:.4f}"

            log_level = logging.WARNING if duration > 1.0 else logging.INFO
            logger.log(
                log_level,
                f"GeoJSON Request: {request.method} {request.get_full_path()} | "
                f"Status: {response.status_code} | Duration: {duration:.4f}s | "
                f"Cache: {cache_status}"
            )

        return response
