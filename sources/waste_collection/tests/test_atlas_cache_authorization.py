"""Atlas change-overlay cache authorization.

Authenticated requests never read or write the overlay cache (access is
re-evaluated per request so grants and revocations take effect
immediately); anonymous requests use a dedicated ``authz-v1:`` namespace
that can never consume legacy unprefixed keys.
"""

import io
from datetime import date
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import caches
from django.core.management import call_command
from rest_framework.test import APITestCase

from maps.models import CatchmentRevision, GeoPolygon, Region
from maps.utils import AUTHZ_GEOJSON_CACHE_PREFIX, get_or_set_cache
from sources.waste_collection.models import (
    Collection,
    CollectionCatchment,
    CollectionSystem,
    WasteCategory,
)
from sources.waste_collection.waste_atlas.viewsets import (
    _change_overlay_cache_key,
)
from utils.object_management.models import (
    ObjectEditorGrant,
    ObjectGroupEditorGrant,
)
from utils.tests.testcases import ensure_test_default_owner


class AtlasOverlayCacheTests(APITestCase):
    """Same root catchment IDs and years across actors: any geometry
    difference comes from authorization, never from a different request."""

    ENDPOINT = "/waste_collection/waste-atlas/api/catchment/collection-change-geojson/"
    PUBLIC_GEOM = "MULTIPOLYGON(((0 0, 0 1, 1 1, 1 0, 0 0)))"
    PUBLIC_NEW_GEOM = "MULTIPOLYGON(((4 4, 4 5, 5 5, 5 4, 4 4)))"
    PRIVATE_GEOM = "MULTIPOLYGON(((2 2, 2 3, 3 3, 3 2, 2 2)))"
    PARAMS = {"country": "DE", "from_year": 2022, "to_year": 2024}

    @classmethod
    def setUpTestData(cls):
        ensure_test_default_owner()
        cls._role_output = io.StringIO()
        call_command("sync_roles", "--apply", stdout=cls._role_output)

        cls.owner = User.objects.create_user("cache-owner")
        cls.stranger = User.objects.create_user("cache-stranger")
        cls.grantee = User.objects.create_user("cache-grantee")
        cls.group = Group.objects.create(name="cache-group")
        cls.group.user_set.add(cls.grantee)

        cls.system = CollectionSystem.objects.create(
            name="cache system", publication_status="published"
        )
        cls.category = WasteCategory.objects.create(
            name="cache category", publication_status="published"
        )
        cls.region = Region.objects.create(
            name="cache region",
            country="DE",
            borders=GeoPolygon.objects.create(
                geom="MULTIPOLYGON(((9 9, 9 10, 10 10, 10 9, 9 9)))"
            ),
        )
        cls.catchment = CollectionCatchment.objects.create(
            name="cache catchment",
            region=cls.region,
            publication_status="published",
        )
        cls.private_collections = {}
        for year in (2022, 2024):
            cls.private_collections[year] = Collection.objects.create(
                name=f"cache collection {year}",
                owner=cls.owner,
                catchment=cls.catchment,
                waste_category=cls.category,
                collection_system=cls.system,
                valid_from=date(year, 1, 1),
                publication_status="private",
            )
        # Private collection variants for public-scope tests.
        for year in (2022, 2024):
            Collection.objects.create(
                name=f"pub collection {year}",
                owner=cls.stranger,
                catchment=cls.catchment,
                waste_category=cls.category,
                collection_system=cls.system,
                valid_from=date(year, 1, 1),
                publication_status="published",
            )
        # The old public revision is valid for 2022; the new public
        # revision and the private revision are both valid for 2024.  The
        # private revision is created last so its later primary key wins
        # the same effective_from ordering for actors allowed to see it.
        cls.public_revision_old = CatchmentRevision.objects.create(
            catchment=cls.catchment,
            owner=cls.stranger,
            geom=cls.PUBLIC_GEOM,
            effective_from=date(2000, 1, 1),
            effective_to=date(2023, 1, 1),
            publication_status="published",
            change_reason="initial",
        )
        cls.public_revision_new = CatchmentRevision.objects.create(
            catchment=cls.catchment,
            owner=cls.stranger,
            geom=cls.PUBLIC_NEW_GEOM,
            effective_from=date(2023, 1, 1),
            publication_status="published",
            change_reason="boundary update",
        )
        cls.private_revision = CatchmentRevision.objects.create(
            catchment=cls.catchment,
            owner=cls.stranger,
            geom=cls.PRIVATE_GEOM,
            effective_from=date(2023, 6, 1),
            publication_status="private",
            change_reason="administrative",
        )

    def setUp(self):
        caches[getattr(settings, "GEOJSON_CACHE", "default")].clear()

    def _features(self, user=None, **params):
        if user is not None:
            self.client.force_login(user)
        response = self.client.get(self.ENDPOINT, {**self.PARAMS, **params})
        if user is not None:
            self.client.logout()
        self.assertEqual(response.status_code, 200)
        return response.data["features"]

    @staticmethod
    def _coords(feature):
        return feature["geometry"]["coordinates"]

    @classmethod
    def _x_values(cls, features):
        """Flatten every x ordinate of every feature coordinate ring."""
        values = []

        def walk(node):
            if isinstance(node, (list, tuple)):
                if node and all(isinstance(value, (int, float)) for value in node):
                    values.append(node[0])
                    return
                for item in node:
                    walk(item)

        for feature in features:
            walk(cls._coords(feature))
        return values

    def _private_x_present(self, features):
        return any(1.5 < x < 3.5 for x in self._x_values(features))

    def test_authenticated_requests_never_touch_overlay_cache(self):
        with patch(
            "sources.waste_collection.waste_atlas.viewsets.get_or_set_cache"
        ) as cache_spy:
            self._features(self.owner, scope="private")
        cache_spy.assert_not_called()

    def test_authenticated_public_scope_also_bypasses_cache(self):
        with patch(
            "sources.waste_collection.waste_atlas.viewsets.get_or_set_cache"
        ) as cache_spy:
            self._features(self.owner, scope="published")
        cache_spy.assert_not_called()

    def test_private_revision_grant_changes_then_revocation_restores(self):
        grant = ObjectEditorGrant.objects.create(
            content_type=ContentType.objects.get_for_model(CatchmentRevision),
            object_id=self.private_revision.pk,
            editor=self.grantee,
            granted_by=self.stranger,
        )
        # Grant the selected collections so the catchment is in the
        # grantee's workspace; the revision grant controls geometry.
        ct_collection = ContentType.objects.get_for_model(Collection)
        for collection in self.private_collections.values():
            ObjectEditorGrant.objects.create(
                content_type=ct_collection,
                object_id=collection.pk,
                editor=self.grantee,
                granted_by=self.owner,
            )

        granted = self._features(self.grantee, scope="private")
        self.assertTrue(
            self._private_x_present(granted),
            "granted private revision geometry missing",
        )
        grant.delete()
        revoked = self._features(self.grantee, scope="private")
        self.assertFalse(
            self._private_x_present(revoked),
            "private revision geometry leaked after revocation",
        )

    def test_group_membership_removal_restores_public_boundary(self):
        ct_collection = ContentType.objects.get_for_model(Collection)
        for collection in self.private_collections.values():
            ObjectEditorGrant.objects.create(
                content_type=ct_collection,
                object_id=collection.pk,
                editor=self.grantee,
                granted_by=self.owner,
            )
        ObjectGroupEditorGrant.objects.create(
            content_type=ContentType.objects.get_for_model(CatchmentRevision),
            object_id=self.private_revision.pk,
            group=self.group,
            granted_by=self.stranger,
        )
        granted = self._features(self.grantee, scope="private")
        self.assertTrue(self._private_x_present(granted))
        self.group.user_set.remove(self.grantee)
        removed = self._features(self.grantee, scope="private")
        self.assertFalse(self._private_x_present(removed))

    def test_two_actors_different_grants_get_different_boundary(self):
        ct_collection = ContentType.objects.get_for_model(Collection)
        for collection in self.private_collections.values():
            for editor in (self.owner, self.grantee):
                ObjectEditorGrant.objects.get_or_create(
                    content_type=ct_collection,
                    object_id=collection.pk,
                    editor=editor,
                    defaults={"granted_by": self.stranger},
                )
        ObjectEditorGrant.objects.create(
            content_type=ContentType.objects.get_for_model(CatchmentRevision),
            object_id=self.private_revision.pk,
            editor=self.grantee,
            granted_by=self.stranger,
        )
        owner_features = self._features(self.owner, scope="private")
        grantee_features = self._features(self.grantee, scope="private")
        self.assertEqual(
            {feature["properties"]["catchment_id"] for feature in owner_features},
            {feature["properties"]["catchment_id"] for feature in grantee_features},
            "same request must not change the catchment set",
        )
        self.assertFalse(self._private_x_present(owner_features))
        self.assertTrue(self._private_x_present(grantee_features))

    def test_anonymous_uses_prefixed_key_and_ignores_legacy_payload(self):
        cache = caches[getattr(settings, "GEOJSON_CACHE", "default")]
        sentinel = [{"type": "Feature", "properties": {"leak": "private"}}]
        # The exact key the anonymous request would have used before the
        # authorization namespace existed - built with the same helper so
        # the seed cannot silently miss the real lookup shape.
        legacy_key = _change_overlay_cache_key(
            [self.catchment.pk], 2022, [self.catchment.pk], 2024, None
        )
        self.assertFalse(legacy_key.startswith(AUTHZ_GEOJSON_CACHE_PREFIX))
        cache.set(legacy_key, sentinel)

        used_keys = []
        original = get_or_set_cache

        def spy(key, generator, timeout=None):
            used_keys.append(key)
            return original(key, generator, timeout)

        with patch(
            "sources.waste_collection.waste_atlas.viewsets.get_or_set_cache",
            side_effect=spy,
        ):
            response = self.client.get(self.ENDPOINT, self.PARAMS)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(used_keys, "anonymous overlay never hit the cache")
        self.assertTrue(
            all(str(key).startswith(AUTHZ_GEOJSON_CACHE_PREFIX) for key in used_keys),
            f"anonymous overlay used a non-prefixed key: {used_keys}",
        )
        features = response.data["features"]
        self.assertTrue(features, "anonymous overlay returned no features")
        self.assertNotEqual(features, sentinel)
        # Public overlay geometry only: old/new public boundaries, never
        # the private revision band.
        self.assertFalse(self._private_x_present(features))

        # The second identical anonymous request must be a real cache hit:
        # the geometry builder runs exactly once across both requests.
        with patch(
            "sources.waste_collection.waste_atlas.viewsets._build_change_geometry",
            wraps=__import__(
                "sources.waste_collection.waste_atlas.viewsets",
                fromlist=["_build_change_geometry"],
            )._build_change_geometry,
        ) as builder_spy:
            second = self.client.get(self.ENDPOINT, self.PARAMS)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data, response.data)
        builder_spy.assert_not_called()

    def test_anonymous_public_overlay_contains_no_private_geometry(self):
        response = self.client.get(self.ENDPOINT, self.PARAMS)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self._private_x_present(response.data["features"]))
