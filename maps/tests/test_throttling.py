from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from ..throttling import UNKNOWN_IDENT, get_subnet_ident


class SubnetIdentTests(APITestCase):
    def test_ipv4_addresses_group_by_24_prefix(self):
        self.assertEqual(get_subnet_ident("202.46.62.65"), "202.46.62.0/24")
        self.assertEqual(
            get_subnet_ident("202.46.62.65"),
            get_subnet_ident("202.46.62.117"),
        )

    def test_ipv6_addresses_group_by_64_prefix(self):
        self.assertEqual(get_subnet_ident("2a01:4f8:1c1c::5"), "2a01:4f8:1c1c::/64")

    def test_comma_joined_forwarded_chain_uses_client_entry(self):
        # DRF's get_ident returns the joined X-Forwarded-For chain; the
        # left-most (client) IP must drive the bucket.
        self.assertEqual(get_subnet_ident("202.46.62.65,10.0.0.1"), "202.46.62.0/24")

    def test_unparseable_values_share_a_single_bucket(self):
        # A spoofed/garbage header must not mint unlimited buckets.
        self.assertEqual(get_subnet_ident("not-an-ip"), UNKNOWN_IDENT)
        self.assertEqual(get_subnet_ident(""), UNKNOWN_IDENT)
        self.assertEqual(get_subnet_ident(None), UNKNOWN_IDENT)
        self.assertEqual(get_subnet_ident("garbage-a"), get_subnet_ident("garbage-b"))

    @override_settings(GEOJSON_THROTTLE_IPV4_PREFIX=16)
    def test_ipv4_prefix_is_configurable(self):
        self.assertEqual(get_subnet_ident("202.46.62.65"), "202.46.0.0/16")


class GeoJSONThrottleTests(APITestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_distributed_subnet_shares_a_single_throttle_bucket(self):
        """Two IPs in one /24 are throttled together (the crawler scenario)."""
        url = reverse("api-region-geojson")
        with patch(
            "rest_framework.throttling.SimpleRateThrottle.THROTTLE_RATES",
            {"geojson_anon": "1/minute"},
        ):
            first = self.client.get(url, REMOTE_ADDR="202.46.62.65")
            second = self.client.get(url, REMOTE_ADDR="202.46.62.117")

        self.assertNotEqual(first.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(second.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_separate_subnets_are_not_throttled_together(self):
        url = reverse("api-region-geojson")
        with patch(
            "rest_framework.throttling.SimpleRateThrottle.THROTTLE_RATES",
            {"geojson_anon": "1/minute"},
        ):
            first = self.client.get(url, REMOTE_ADDR="202.46.62.65")
            second = self.client.get(url, REMOTE_ADDR="8.8.8.8")

        self.assertNotEqual(first.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertNotEqual(second.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_authenticated_users_bypass_the_throttle(self):
        url = reverse("api-region-geojson")
        user = User.objects.create_user(username="map-user")
        self.client.force_authenticate(user=user)
        with patch(
            "rest_framework.throttling.SimpleRateThrottle.THROTTLE_RATES",
            {"geojson_anon": "1/minute"},
        ):
            first = self.client.get(url, REMOTE_ADDR="202.46.62.65")
            second = self.client.get(url, REMOTE_ADDR="202.46.62.65")

        self.assertNotEqual(first.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertNotEqual(second.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
