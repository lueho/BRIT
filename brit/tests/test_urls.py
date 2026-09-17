from django.test import SimpleTestCase, TestCase
from django.urls import Resolver404, resolve, reverse

from utils.models import Redirect


class SessionUrlRoutingTests(SimpleTestCase):
    def test_set_session_url_resolves(self):
        url = reverse("set_session")
        self.assertEqual(url, "/set_session/")

    def test_get_session_url_resolves(self):
        url = reverse("get_session")
        self.assertEqual(url, "/get_session/")


class RobotsTxtTests(SimpleTestCase):
    """robots.txt must keep crawlers out of unbounded/expensive URL spaces.

    Production logs showed bots crawling recursively nested ?back= URLs and
    deep load_features pagination of geodataset map/table views, saturating
    web workers with ~1-3s requests.
    """

    def get_robots(self):
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_disallows_return_path_params(self):
        content = self.get_robots()
        for param in ("back", "next", "return_to"):
            with self.subTest(param=param):
                self.assertIn(f"Disallow: /*?*{param}=", content)

    def test_disallows_expensive_state_params(self):
        content = self.get_robots()
        for param in ("load_features", "page", "scope"):
            with self.subTest(param=param):
                self.assertIn(f"Disallow: /*?*{param}=", content)

    def test_disallows_geodataset_interactive_views(self):
        content = self.get_robots()
        for path in (
            "/maps/geodatasets/*/map/",
            "/maps/geodatasets/*/table/",
            "/maps/geodatasets/*/features/",
        ):
            with self.subTest(path=path):
                self.assertIn(f"Disallow: {path}", content)


class DynamicRedirectRoutingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Redirect.objects.create(short_code="docs", full_path="/learning/")

    def test_short_code_redirects_with_or_without_trailing_slash(self):
        for path in ("/docs", "/docs/"):
            with self.subTest(path=path):
                response = self.client.get(path)

                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, "http://testserver/learning/")

    def test_unknown_root_path_without_trailing_slash_returns_404(self):
        response = self.client.get("/not-a-short-code")

        self.assertEqual(response.status_code, 404)

    def test_unknown_root_path_is_not_resolved_as_a_redirect(self):
        with self.assertRaises(Resolver404):
            resolve("/not-a-short-code/")

    def test_unknown_root_post_returns_404(self):
        response = self.client.post("/not-a-short-code/")

        self.assertEqual(response.status_code, 404)
