"""Cache-audience regression tests for the GeoJSON endpoints.

Registered policy models (Region, Catchment) must never serve or seed an
actor-independent cache entry: authenticated requests bypass all cache
paths so revocation takes effect immediately, and anonymous requests share
an isolated ``authz-v1:`` namespace that can only contain the
published-visible rows.
"""

from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.cache import caches
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from rest_framework.test import APIRequestFactory

from maps.models import GeoPolygon, Region
from maps.utils import AUTHZ_GEOJSON_CACHE_PREFIX, get_region_cache_key
from maps.viewsets import RegionViewSet

User = get_user_model()

_GEOJSON_CACHE_SETTINGS = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "brit-test-default",
    },
    "geojson": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "brit-test-geojson-authz",
        "TIMEOUT": 86400,
        "KEY_PREFIX": "geojson",
    },
}


def _polygon(x):
    return GeoPolygon.objects.create(
        geom=MultiPolygon(Polygon(((x, 0), (x, 1), (x + 1, 1), (x + 1, 0), (x, 0))))
    )


@override_settings(CACHES=_GEOJSON_CACHE_SETTINGS)
class GeoJsonCacheAudienceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner")
        cls.stranger = User.objects.create_user(username="stranger")
        cls.grantee = User.objects.create_user(username="grantee")
        cls.group = Group.objects.create(name="map-editors")
        cls.group.user_set.add(cls.grantee)
        cls.public_region = Region.objects.create(
            name="Public Region",
            country="DE",
            owner=cls.owner,
            publication_status="published",
            borders=_polygon(0),
        )
        cls.private_region = Region.objects.create(
            name="Owner Private",
            country="DE",
            owner=cls.owner,
            publication_status="private",
            borders=_polygon(10),
        )

    def setUp(self):
        self.geojson_cache = caches["geojson"]
        self.geojson_cache.clear()
        self.url = reverse("api-region-geojson")

    def tearDown(self):
        self.geojson_cache.clear()

    def _feature_ids(self, response):
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        return [feature["properties"]["id"] for feature in payload["features"]]

    def _get_geojson(self, region):
        return self.client.get(f"{self.url}?id={region.pk}")

    def test_owner_request_does_not_seed_private_feature_for_anonymous(self):
        self.client.force_login(self.owner)
        response = self._get_geojson(self.private_region)
        self.assertIn(self.private_region.pk, self._feature_ids(response))

        legacy_key = get_region_cache_key(self.private_region.pk)
        self.assertIsNone(self.geojson_cache.get(legacy_key))
        self.assertIsNone(
            self.geojson_cache.get(f"{AUTHZ_GEOJSON_CACHE_PREFIX}{legacy_key}")
        )

        self.client.force_login(self.stranger)
        response = self._get_geojson(self.private_region)
        self.assertEqual(self._feature_ids(response), [])

        self.client.force_login(self.owner)
        self.client.logout()
        response = self._get_geojson(self.private_region)
        self.assertEqual(self._feature_ids(response), [])

    def test_anonymous_cache_hit_serves_only_published_rows(self):
        response = self._get_geojson(self.public_region)
        self.assertIn(self.public_region.pk, self._feature_ids(response))

        authz_key = (
            f"{AUTHZ_GEOJSON_CACHE_PREFIX}{get_region_cache_key(self.public_region.pk)}"
        )
        self.assertIsNotNone(self.geojson_cache.get(authz_key))
        self.assertIsNone(
            self.geojson_cache.get(get_region_cache_key(self.public_region.pk))
        )

        response = self._get_geojson(self.public_region)
        self.assertEqual(response.headers.get("X-Cache-Status"), "HIT")
        self.assertIn(self.public_region.pk, self._feature_ids(response))

    def test_revoked_group_grant_is_absent_on_next_request(self):
        self.private_region.add_editor_group(self.group, granted_by=self.owner)

        self.client.force_login(self.grantee)
        response = self._get_geojson(self.private_region)
        self.assertIn(self.private_region.pk, self._feature_ids(response))

        self.private_region.remove_editor_group(self.group)
        response = self._get_geojson(self.private_region)
        self.assertEqual(self._feature_ids(response), [])

    def test_head_and_count_mirror_scoped_payload(self):
        response = self._get_geojson(self.public_region)
        self.assertEqual(response.status_code, 200)

        response = self.client.head(f"{self.url}?id={self.public_region.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Cache-Status"), "HIT")
        self.assertEqual(response.headers.get("X-Total-Count"), "1")

        response = self._get_geojson(self.private_region)
        self.assertEqual(response.status_code, 200)
        response = self.client.head(f"{self.url}?id={self.private_region.pk}")
        self.assertEqual(response.headers.get("X-Total-Count"), "0")

    def test_two_actors_private_sets_do_not_cross(self):
        other = User.objects.create_user(username="other")
        other_region = Region.objects.create(
            name="Other Private",
            country="DE",
            owner=other,
            publication_status="private",
            borders=_polygon(20),
        )

        self.client.force_login(self.owner)
        self.assertIn(
            self.private_region.pk,
            self._feature_ids(self._get_geojson(self.private_region)),
        )
        self.assertEqual(self._feature_ids(self._get_geojson(other_region)), [])

        self.client.force_login(other)
        self.assertIn(
            other_region.pk, self._feature_ids(self._get_geojson(other_region))
        )
        self.assertEqual(self._feature_ids(self._get_geojson(self.private_region)), [])

        for region in (self.private_region, other_region):
            legacy_key = get_region_cache_key(region.pk)
            self.assertIsNone(self.geojson_cache.get(legacy_key))
            self.assertIsNone(
                self.geojson_cache.get(f"{AUTHZ_GEOJSON_CACHE_PREFIX}{legacy_key}")
            )

    def test_queryset_resolution_failure_disables_cache(self):
        legacy_key = get_region_cache_key(self.public_region.pk)
        self.geojson_cache.set(
            legacy_key,
            {"type": "FeatureCollection", "features": [{"properties": {"id": 9999}}]},
        )

        view = RegionViewSet()
        view.get_queryset = Mock(side_effect=RuntimeError("cannot resolve"))
        request = APIRequestFactory().get(self.url)
        request.user = AnonymousUser()

        self.assertIsNone(view._audience_cache_key(request, legacy_key))
