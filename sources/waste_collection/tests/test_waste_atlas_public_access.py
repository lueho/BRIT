import json
import re
from uuid import uuid4

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from sources.waste_collection.models import Collection

API = "/waste_collection/waste-atlas/api/"
BAD_YEARS = ["0", "-5", "20000", "99999999999999999999", "abc", "2024.5", ""]


def _map_config(response):
    match = re.search(
        r'<script id="atlas-config" type="application/json">(.*?)</script>',
        response.content.decode(),
        re.S,
    )
    assert match, "no atlas-config JSON found in response"
    return json.loads(match.group(1))


class WasteAtlasApiInputTests(APITestCase):
    def test_unsupported_years_do_not_break_data_endpoints(self):
        for endpoint in ("collection-system/", "catchment/geojson/"):
            for year in BAD_YEARS:
                with self.subTest(endpoint=endpoint, year=year):
                    response = self.client.get(
                        f"{API}{endpoint}", {"country": "DE", "year": year}
                    )
                    self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_catchment_list_and_detail_routes_are_not_exposed(self):
        self.assertEqual(
            self.client.get(f"{API}catchment/").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.get(f"{API}catchment/1/").status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_api_root_is_public(self):
        response = self.client.get(API)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("collection-system", response.json())


class WasteAtlasConflictAccessTests(APITestCase):
    endpoint = f"{API}collection-conflicts/"

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("conflict-user")
        cls.staff = User.objects.create_user("conflict-staff", is_staff=True)
        cls.moderator = User.objects.create_user("conflict-moderator")
        cls.moderator.user_permissions.add(
            Permission.objects.get(
                content_type=ContentType.objects.get_for_model(Collection),
                codename="can_moderate_collection",
            )
        )

    def test_anonymous_and_ordinary_users_are_refused(self):
        self.assertIn(
            self.client.get(self.endpoint).status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.client.force_login(self.user)
        self.assertEqual(
            self.client.get(self.endpoint).status_code, status.HTTP_403_FORBIDDEN
        )

    def test_staff_and_moderators_may_read_conflicts(self):
        for user in (self.staff, self.moderator):
            self.client.force_login(user)
            self.assertEqual(
                self.client.get(self.endpoint).status_code, status.HTTP_200_OK
            )


class WasteAtlasThrottleIdentityTests(APITestCase):
    endpoint = f"{API}green-waste-collection-system-count/"

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_forged_forwarded_for_prefix_cannot_open_new_buckets(self):
        from unittest.mock import patch

        with patch(
            "rest_framework.throttling.ScopedRateThrottle.THROTTLE_RATES",
            {"waste_atlas": "1/minute"},
        ):
            peer = f"10.9.{uuid4().int % 250}.1"
            first = self.client.get(
                self.endpoint, HTTP_X_FORWARDED_FOR=f"1.1.1.1, {peer}"
            )
            second = self.client.get(
                self.endpoint, HTTP_X_FORWARDED_FOR=f"2.2.2.2, {peer}"
            )

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class WasteAtlasPublicPagesTests(TestCase):
    """The atlas is public; maintainer tools stay behind staff checks."""

    public_pages = (
        "waste-atlas-overview",
        "waste-atlas-change-map-overview",
        "waste-atlas-europe-data-coverage-map",
        "waste-atlas-europe-biowaste-collection-amount-map",
        "waste-atlas-germany-collection-system-map",
    )

    def test_anonymous_visitors_can_open_public_pages(self):
        for name in self.public_pages:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        change_map = reverse("waste-atlas-change-map", args=["DE", "collection_system"])
        self.assertEqual(self.client.get(change_map).status_code, 200)

    def test_maintainer_pages_still_require_staff(self):
        pages = (
            reverse("waste-atlas-data-conflicts-overview"),
            reverse("waste-atlas-map-configuration-list"),
        )
        for url in pages:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(User.objects.create_user("plain"))
        for url in pages:
            with self.subTest(url=url, user="plain"):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_anonymous_visitors_only_get_the_published_scope(self):
        url = reverse("waste-atlas-germany-collection-system-map")
        response = self.client.get(url, {"scope": "all"})
        self.assertEqual(_map_config(response)["scope"], "published")
        self.assertNotContains(response, 'value="mine"')
        self.assertNotContains(response, 'value="all"')
        self.assertNotContains(response, "Edit configuration")

    def test_conflict_overlay_is_only_offered_to_maintainers(self):
        url = reverse("waste-atlas-germany-collection-system-map")
        self.assertNotIn("conflictUrl", _map_config(self.client.get(url)))
        self.client.force_login(User.objects.create_user("plain-2"))
        self.assertNotIn("conflictUrl", _map_config(self.client.get(url)))
        self.client.force_login(User.objects.create_user("staff", is_staff=True))
        self.assertIn("conflictUrl", _map_config(self.client.get(url)))


class WasteAtlasPageInputTests(TestCase):
    def test_malformed_query_values_fall_back_to_page_defaults(self):
        map_url = reverse("waste-atlas-orga-level-map")
        for query in (
            {"year": "abc"},
            {"year": "20000"},
            {"nuts_level": "x"},
            {"nuts_level": "-1"},
        ):
            with self.subTest(query=query):
                self.assertEqual(self.client.get(map_url, query).status_code, 200)
        change_url = reverse("waste-atlas-change-map", args=["DE", "collection_system"])
        for query in ({"from_year": "abc"}, {"to_year": ""}, {"to_year": "99999"}):
            with self.subTest(query=query):
                self.assertEqual(self.client.get(change_url, query).status_code, 200)

    def test_region_codes_are_not_passed_through_unvalidated(self):
        response = self.client.get(
            reverse("waste-atlas-orga-level-map"),
            {"country": "DE&scope=all", "nuts_prefix": '"><script>'},
        )
        config = _map_config(response)
        self.assertEqual(config["country"], "DE")
        self.assertNotIn("nutsPrefix", config)


class WasteAtlasVendorScriptTests(TestCase):
    """Third-party scripts on public pages are pinned and integrity-checked."""

    def test_d3_is_pinned_with_subresource_integrity(self):
        pages = (
            reverse("waste-atlas-germany-collection-system-map"),
            reverse("waste-atlas-europe-data-coverage-map"),
            reverse("waste-atlas-europe-biowaste-collection-amount-map"),
            reverse("waste-atlas-europe-data-coverage-map-iframe"),
        )
        for url in pages:
            with self.subTest(url=url):
                content = self.client.get(url).content.decode()
                tag = re.search(
                    r"<script[^>]*cdn\.jsdelivr\.net/npm/d3@[^>]*>", content
                )
                self.assertIsNotNone(tag)
                self.assertRegex(tag.group(0), r"d3@\d+\.\d+\.\d+/")
                self.assertIn('integrity="sha384-', tag.group(0))
                self.assertIn('crossorigin="anonymous"', tag.group(0))


class WasteAtlasDiscoverabilityTests(TestCase):
    def test_overview_is_listed_in_the_sitemap(self):
        from brit.sitemap_items import SITEMAP_ITEMS

        self.assertIn(reverse("waste-atlas-overview"), SITEMAP_ITEMS)
        self.assertNotIn(reverse("waste-atlas-data-conflicts-overview"), SITEMAP_ITEMS)

    def test_sitemap_entry_is_publicly_reachable(self):
        self.assertEqual(
            self.client.get(reverse("waste-atlas-overview")).status_code, 200
        )

    def test_anonymous_navigation_links_to_the_atlas(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, f'href="{reverse("waste-atlas-overview")}"')

    def test_crawlers_are_kept_off_permalinks_and_the_data_api(self):
        content = self.client.get("/robots.txt").content.decode()

        self.assertIn("Disallow: /*/waste-atlas/p/", content)
        self.assertIn("Disallow: /*/api/", content)


class WasteAtlasNutsPrefixInputTests(APITestCase):
    def test_malformed_or_oversized_prefix_lists_are_rejected(self):
        oversized = ",".join(f"DE{i}" for i in range(17))
        for prefix in (oversized, "DE1;DROP", "X" * 9, "DE1,,DE2", '"><x>'):
            with self.subTest(prefix=prefix[:20]):
                response = self.client.get(
                    f"{API}collection-system/",
                    {"country": "DE", "year": 2024, "nuts_prefix": prefix},
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_prefix_lists_are_accepted(self):
        response = self.client.get(
            f"{API}collection-system/",
            {"country": "BE", "year": 2024, "nuts_prefix": "BE1,BE2"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
