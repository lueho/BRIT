from django.test import SimpleTestCase
from django.urls import reverse


class SessionUrlRoutingTests(SimpleTestCase):
    def test_set_session_url_resolves(self):
        url = reverse("set_session")
        self.assertEqual(url, "/set_session/")

    def test_get_session_url_resolves(self):
        url = reverse("get_session")
        self.assertEqual(url, "/get_session/")
