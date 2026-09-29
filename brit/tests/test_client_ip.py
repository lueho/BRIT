from django.test import RequestFactory, SimpleTestCase, override_settings

from brit.client_ip import get_client_ip

CF_EDGE = "172.70.0.9"  # inside Cloudflare's 172.64.0.0/13


class ClientIPTests(SimpleTestCase):
    def ip(self, **meta):
        return get_client_ip(RequestFactory().get("/", **meta))

    def test_cloudflare_client_ip_is_trusted_when_the_peer_is_a_cloudflare_edge(self):
        self.assertEqual(
            self.ip(
                HTTP_CF_CONNECTING_IP="1.2.3.4",
                HTTP_CF_RAY="abc-FRA",
                HTTP_X_FORWARDED_FOR=f"1.2.3.4, {CF_EDGE}",
            ),
            "1.2.3.4",
        )

    def test_forged_cloudflare_headers_from_a_direct_client_are_ignored(self):
        for forged in ("1.2.3.4", "5.6.7.8"):
            with self.subTest(forged=forged):
                self.assertEqual(
                    self.ip(
                        HTTP_CF_CONNECTING_IP=forged,
                        HTTP_CF_RAY="abc-FRA",
                        HTTP_X_FORWARDED_FOR=f"{forged}, 203.0.113.7",
                    ),
                    "203.0.113.7",
                )

    def test_forged_cloudflare_headers_without_forwarding_use_the_peer(self):
        self.assertEqual(
            self.ip(
                HTTP_CF_CONNECTING_IP="1.2.3.4",
                HTTP_CF_RAY="abc-FRA",
                REMOTE_ADDR="203.0.113.7",
            ),
            "203.0.113.7",
        )

    def test_ipv6_cloudflare_edges_are_recognised(self):
        self.assertEqual(
            self.ip(
                HTTP_CF_CONNECTING_IP="2001:db8::1",
                HTTP_CF_RAY="abc-FRA",
                HTTP_X_FORWARDED_FOR="2001:db8::1, 2606:4700::6810:84e5",
            ),
            "2001:db8::1",
        )

    @override_settings(CLOUDFLARE_TRUSTED_PROXY_RANGES=("203.0.113.0/24",))
    def test_trusted_ranges_are_configurable(self):
        self.assertEqual(
            self.ip(
                HTTP_CF_CONNECTING_IP="1.2.3.4",
                HTTP_CF_RAY="abc-FRA",
                HTTP_X_FORWARDED_FOR="1.2.3.4, 203.0.113.7",
            ),
            "1.2.3.4",
        )
