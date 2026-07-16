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
