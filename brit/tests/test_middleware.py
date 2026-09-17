from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from brit.middleware import CanonicalHostRedirectMiddleware

CANONICAL = "brit.bioresource-tools.net"
HOSTS = [CANONICAL, "bri-tool.herokuapp.com", "localhost", "testserver"]


@override_settings(CANONICAL_HOST=CANONICAL, ALLOWED_HOSTS=HOSTS)
class CanonicalHostRedirectMiddlewareTests(SimpleTestCase):
    """Requests on non-canonical hosts are 308-redirected to CANONICAL_HOST.

    Bots hammering the herokuapp.com domain bypass the Cloudflare layer in
    front of the canonical domain; the redirect moves them onto it. 308
    (preserve_request=True) keeps method and body so a POST is not silently
    downgraded to GET.
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = CanonicalHostRedirectMiddleware(
            lambda request: HttpResponse("ok")
        )

    def test_redirects_heroku_host_to_canonical(self):
        request = self.factory.get(
            "/maps/geodatasets/3/table/?id=1&page=2",
            HTTP_HOST="bri-tool.herokuapp.com",
        )
        response = self.middleware(request)

        self.assertEqual(response.status_code, 308)
        self.assertEqual(
            response["Location"],
            f"https://{CANONICAL}/maps/geodatasets/3/table/?id=1&page=2",
        )

    def test_post_redirect_preserves_method_and_body(self):
        request = self.factory.post(
            "/api/materials/samples/",
            data={"name": "x"},
            HTTP_HOST="bri-tool.herokuapp.com",
        )
        response = self.middleware(request)

        self.assertEqual(response.status_code, 308)
        self.assertEqual(
            response["Location"],
            f"https://{CANONICAL}/api/materials/samples/",
        )

    def test_canonical_host_passes_through(self):
        request = self.factory.get("/materials/samples/", HTTP_HOST=CANONICAL)
        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)

    def test_host_comparison_ignores_port_and_case(self):
        request = self.factory.get("/x/", HTTP_HOST=f"{CANONICAL}:443")
        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)

    def test_health_check_is_exempt_on_any_host(self):
        request = self.factory.get("/health/", HTTP_HOST="localhost")
        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)

    @override_settings(CANONICAL_HOST="")
    def test_noop_when_canonical_host_unset(self):
        request = self.factory.get("/x/", HTTP_HOST="localhost")
        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
