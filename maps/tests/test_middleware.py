from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from maps.middleware import CacheMonitoringMiddleware


class CacheMonitoringMiddlewareTestCase(SimpleTestCase):
    @override_settings(TESTING=True)
    def test_geojson_requests_do_not_emit_logs_during_tests(self):
        request = RequestFactory().get("/maps/api/region/geojson/")

        def get_response(_request):
            response = HttpResponse()
            response["X-Cache-Status"] = "MISS"
            return response

        middleware = CacheMonitoringMiddleware(get_response)

        with self.assertNoLogs("maps.middleware"):
            response = middleware(request)

        self.assertEqual(response["X-Cache-Status"], "MISS")
        self.assertIn("X-Cache-Time", response)
