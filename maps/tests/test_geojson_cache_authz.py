"""Cache-audience regression tests for the GeoJSON endpoints.

Registered policy models (Region, Catchment) must never serve or seed an
actor-independent cache entry: authenticated requests bypass all cache
paths so revocation takes effect immediately, and anonymous requests share
an isolated ``authz-v1:`` namespace that can only contain the
published-visible rows.
"""

from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.cache import caches
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from rest_framework.test import APIRequestFactory

from maps.models import Catchment, GeoPolygon, Location, NutsRegion, NutsVintage, Region
from maps.utils import (
    AUTHZ_GEOJSON_CACHE_PREFIX,
    get_catchment_cache_key,
    get_region_cache_key,
)
from maps.viewsets import RegionViewSet
from utils.object_management.models import ReviewAction

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


class GeoJsonCacheKeyScopeCollisionTests(TestCase):
    """Id-scoped requests must not collide across differing filters.

    ``?id=PUBLIC`` warms the anonymous ``authz-v1:`` entry; the identical id
    combined with a scope or any other filter must compute a different key
    and therefore an independently resolved, scoped payload.
    """

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="ck-owner")
        cls.public_region = Region.objects.create(
            name="CK Public",
            country="DE",
            owner=cls.owner,
            publication_status="published",
            borders=GeoPolygon.objects.create(
                geom=MultiPolygon(Polygon(((0, 0), (0, 1), (1, 1), (1, 0), (0, 0))))
            ),
        )
        cls.archived_region = Region.objects.create(
            name="CK Archived",
            country="DE",
            owner=cls.owner,
            publication_status="archived",
            borders=GeoPolygon.objects.create(
                geom=MultiPolygon(Polygon(((2, 2), (2, 3), (3, 3), (3, 2), (2, 2))))
            ),
        )

    @override_settings(CACHES=_GEOJSON_CACHE_SETTINGS)
    def setUp(self):
        self.geojson_cache = caches["geojson"]
        self.geojson_cache.clear()
        self.url = reverse("api-region-geojson")

    def tearDown(self):
        self.geojson_cache.clear()

    def test_scoped_id_request_does_not_hit_unscoped_public_payload(self):
        warm = self.client.get(f"{self.url}?id={self.public_region.pk}")
        self.assertEqual(warm.status_code, 200)
        self.assertEqual(len(warm.json()["features"]), 1)

        for params in ("scope=private", "scope=owned", "scope=shared"):
            with self.subTest(params=params):
                response = self.client.get(
                    f"{self.url}?id={self.public_region.pk}&{params}"
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["features"], [])
        # an invalid scope is rejected outright — never a cache hit
        response = self.client.get(f"{self.url}?id={self.public_region.pk}&scope=bogus")
        self.assertEqual(response.status_code, 400)

    def test_scoped_id_head_reports_scoped_count(self):
        self.client.get(f"{self.url}?id={self.public_region.pk}")
        response = self.client.head(
            f"{self.url}?id={self.public_region.pk}&scope=private"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Total-Count"), "0")

    def test_archived_id_with_published_scope_is_empty(self):
        warm = self.client.get(f"{self.url}?id={self.archived_region.pk}")
        self.assertEqual(warm.status_code, 200)
        self.assertEqual(len(warm.json()["features"]), 1)
        response = self.client.get(
            f"{self.url}?id={self.archived_region.pk}&scope=published"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["features"], [])


class GeoJsonCacheKeyFactoryTests(TestCase):
    """Direct factory parity: id-only keys stay stable, extra filters split."""

    def test_id_only_key_retained_when_filters_are_empty_or_id_only(self):
        base = get_region_cache_key(7)
        self.assertEqual(base, "region_geojson:id:7")
        self.assertEqual(get_region_cache_key(7, {}), base)
        self.assertEqual(get_region_cache_key(7, {"id": "7"}), base)
        self.assertEqual(get_catchment_cache_key(9), "catchment_geojson:id:9")
        self.assertEqual(
            get_catchment_cache_key(9, {"id": "9"}), "catchment_geojson:id:9"
        )

    def test_extra_filters_produce_distinct_deterministic_keys(self):
        scoped = get_region_cache_key(7, {"id": "7", "scope": "private"})
        self.assertNotEqual(scoped, "region_geojson:id:7")
        self.assertTrue(scoped.startswith("region_geojson:id:7"))
        self.assertEqual(
            scoped,
            get_region_cache_key(7, {"scope": "private", "id": "7"}),
        )
        other = get_region_cache_key(7, {"id": "7", "scope": "published"})
        self.assertNotEqual(scoped, other)
        catch = get_catchment_cache_key(9, {"id": "9", "scope": "private"})
        self.assertTrue(catch.startswith("catchment_geojson:id:9"))
        self.assertNotEqual(catch, "catchment_geojson:id:9")


class MapOrdinaryApiAuthzTests(TestCase):
    """Ordinary (non-geojson) map viewsets follow the shared UCO read/write
    policy: private rows are invisible to strangers and anonymous actors,
    readable to owners and grantees, and writes stay governed."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="map-owner")
        cls.stranger = User.objects.create_user(username="map-stranger")
        cls.staff = User.objects.create_user(username="map-staff", is_staff=True)
        cls.public_region = Region.objects.create(
            name="Public",
            country="DE",
            owner=cls.owner,
            publication_status="published",
            borders=_polygon(0),
        )
        cls.private_region = Region.objects.create(
            name="Private",
            country="DE",
            owner=cls.owner,
            publication_status="private",
            borders=_polygon(10),
        )
        cls.public_catchment = Catchment.objects.create(
            name="Public catchment",
            owner=cls.owner,
            publication_status="published",
        )
        cls.private_catchment = Catchment.objects.create(
            name="Private catchment",
            owner=cls.owner,
            publication_status="private",
        )
        cls.public_location = Location.objects.create(
            name="Public loc", owner=cls.owner, publication_status="published"
        )
        cls.private_location = Location.objects.create(
            name="Private loc", owner=cls.owner, publication_status="private"
        )
        cls.vintage = NutsVintage.default()
        cls.public_nuts = NutsRegion.objects.create(
            name="DE public",
            nuts_id="DEPU",
            levl_code=1,
            cntr_code="DE",
            version=cls.vintage,
            owner=cls.owner,
            publication_status="published",
        )
        cls.private_nuts = NutsRegion.objects.create(
            name="DE private",
            nuts_id="DEPR",
            levl_code=1,
            cntr_code="DE",
            version=cls.vintage,
            owner=cls.owner,
            publication_status="private",
        )

    def _grant(self, obj, user):
        obj.add_editor(user, granted_by=self.owner)

    def test_region_list_scopes_to_readable_rows(self):
        url = reverse("api-region-list")
        anonymous = self.client.get(url)
        self.assertEqual(anonymous.status_code, 200)
        ids = {row["id"] for row in anonymous.json()}
        self.assertIn(self.public_region.pk, ids)
        self.assertNotIn(self.private_region.pk, ids)

        self.client.force_login(self.stranger)
        ids = {row["id"] for row in self.client.get(url).json()}
        self.assertNotIn(self.private_region.pk, ids)

        self._grant(self.private_region, self.stranger)
        ids = {row["id"] for row in self.client.get(url).json()}
        self.assertIn(self.private_region.pk, ids)

        self.private_region.remove_editor(self.stranger)
        ids = {row["id"] for row in self.client.get(url).json()}
        self.assertNotIn(self.private_region.pk, ids)

        self.client.force_login(self.owner)
        ids = {row["id"] for row in self.client.get(url).json()}
        self.assertIn(self.private_region.pk, ids)

    def test_region_detail_private_404_for_stranger_200_for_owner(self):
        url = reverse("api-region-detail", args=[self.private_region.pk])
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_unknown_scope_is_rejected(self):
        """RegionFilterSet's ChoiceFilter rejects unknown scope values."""
        self.client.force_login(self.owner)
        response = self.client.get(reverse("api-region-list") + "?scope=bogus")
        self.assertEqual(response.status_code, 400)
        self.assertIn("scope", response.json())

    def test_location_catchment_nuts_lists_scoped(self):
        cases = (
            ("api-location-list", self.public_location, self.private_location),
            ("api-catchment-list", self.public_catchment, self.private_catchment),
            ("api-nuts-region-list", self.public_nuts, self.private_nuts),
        )
        for url_name, public_obj, private_obj in cases:
            with self.subTest(endpoint=url_name):
                url = reverse(url_name)

                anonymous = self.client.get(url)
                self.assertEqual(anonymous.status_code, 200)
                ids = {row["id"] for row in anonymous.json()}
                self.assertIn(public_obj.pk, ids)
                self.assertNotIn(private_obj.pk, ids)

                self.client.force_login(self.stranger)
                ids = {row["id"] for row in self.client.get(url).json()}
                self.assertNotIn(private_obj.pk, ids)

                private_obj.add_editor(self.stranger, granted_by=self.owner)
                ids = {row["id"] for row in self.client.get(url).json()}
                self.assertIn(private_obj.pk, ids)

                private_obj.remove_editor(self.stranger)
                ids = {row["id"] for row in self.client.get(url).json()}
                self.assertNotIn(private_obj.pk, ids)

                self.client.force_login(self.owner)
                ids = {row["id"] for row in self.client.get(url).json()}
                self.assertIn(private_obj.pk, ids)
                self.client.logout()

    def test_region_patch_owner_change_capable(self):
        self.owner.user_permissions.add(
            Permission.objects.get(
                codename="change_region", content_type__app_label="maps"
            )
        )
        before = self.private_region.content_revision
        self.client.force_login(self.owner)
        response = self.client.patch(
            reverse("api-region-detail", args=[self.private_region.pk]),
            {"name": "Renamed"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.private_region.refresh_from_db()
        self.assertEqual(self.private_region.name, "Renamed")
        self.assertEqual(self.private_region.content_revision, before + 1)
        self.assertEqual(
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(Region),
                object_id=self.private_region.pk,
                action="edited",
            ).count(),
            1,
        )

    def test_region_patch_owner_without_change_capability_denied(self):
        self.owner.groups.clear()
        self.owner.user_permissions.clear()
        owner = User.objects.get(pk=self.owner.pk)
        self.assertFalse(owner.has_perm("maps.change_region"))
        before = self.private_region.content_revision
        self.client.force_login(self.owner)
        response = self.client.patch(
            reverse("api-region-detail", args=[self.private_region.pk]),
            {"name": "Forged"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.private_region.refresh_from_db()
        self.assertEqual(self.private_region.name, "Private")
        self.assertEqual(self.private_region.content_revision, before)
        self.assertEqual(
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(Region),
                object_id=self.private_region.pk,
                action="edited",
            ).count(),
            0,
        )

    def test_region_patch_denied_without_capability_and_on_published(self):
        # stranger with no capability -> 404 (invisible row)
        self.client.force_login(self.stranger)
        response = self.client.patch(
            reverse("api-region-detail", args=[self.private_region.pk]),
            {"name": "Forged"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        # staff-only without edit grant/capability -> denied
        self.client.force_login(self.staff)
        response = self.client.patch(
            reverse("api-region-detail", args=[self.private_region.pk]),
            {"name": "Forged"},
            content_type="application/json",
        )
        self.assertIn(response.status_code, (403, 404))
        # published rows are frozen even for a capable owner
        self.owner.user_permissions.add(
            Permission.objects.get(
                codename="change_region", content_type__app_label="maps"
            )
        )
        self.client.force_login(self.owner)
        response = self.client.patch(
            reverse("api-region-detail", args=[self.public_region.pk]),
            {"name": "Forged"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.public_region.refresh_from_db()
        self.assertEqual(self.public_region.name, "Public")

    def test_catchment_patch_rejects_inaccessible_region(self):
        self.owner.user_permissions.add(
            Permission.objects.get(
                codename="change_catchment", content_type__app_label="maps"
            )
        )
        hidden_region = Region.objects.create(
            name="Stranger's",
            owner=self.stranger,
            publication_status="private",
        )
        before = self.private_catchment.content_revision
        self.client.force_login(self.owner)
        response = self.client.patch(
            reverse("api-catchment-detail", args=[self.private_catchment.pk]),
            {"name": "Renamed", "region": hidden_region.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.private_catchment.refresh_from_db()
        self.assertEqual(self.private_catchment.name, "Private catchment")
        self.assertIsNone(self.private_catchment.region)
        self.assertEqual(self.private_catchment.content_revision, before)
        self.assertEqual(
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(Catchment),
                object_id=self.private_catchment.pk,
                action="edited",
            ).count(),
            0,
        )

    def test_catchment_patch_accepts_readable_region(self):
        self.owner.user_permissions.add(
            Permission.objects.get(
                codename="change_catchment", content_type__app_label="maps"
            )
        )
        before = self.private_catchment.content_revision
        self.client.force_login(self.owner)
        response = self.client.patch(
            reverse("api-catchment-detail", args=[self.private_catchment.pk]),
            {"name": "Renamed", "region": self.public_region.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.private_catchment.refresh_from_db()
        self.assertEqual(self.private_catchment.name, "Renamed")
        self.assertEqual(self.private_catchment.region_id, self.public_region.pk)
        self.assertEqual(self.private_catchment.content_revision, before + 1)
        self.assertEqual(
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(Catchment),
                object_id=self.private_catchment.pk,
                action="edited",
            ).count(),
            1,
        )
