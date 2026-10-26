"""Atlas scoped-read authorization through the shared policy core.

Every assertion here hard-codes the expected catchment IDs; no expected
result is computed through ``scope_queryset``/``decide`` (the code under
test).  The atlas-specific ``historical`` scope is the authorized union of
published and archived records; explicit ``published`` stays active-only.
"""

import io
from datetime import date

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APITestCase

from maps.models import GeoPolygon, Region
from sources.waste_collection.models import (
    Collection,
    CollectionCatchment,
    CollectionSystem,
    Collector,
    WasteCategory,
)
from sources.waste_collection.waste_atlas.models import (
    WasteAtlasMapConfiguration,
)
from sources.waste_collection.waste_atlas.viewsets import _atlas_queryset
from utils.object_management.models import (
    ObjectEditorGrant,
    ObjectGroupEditorGrant,
)
from utils.tests.testcases import ensure_test_default_owner


class AtlasScopeFixture:
    """Shared actors, statuses and request helpers for atlas scope tests."""

    ENDPOINTS = {
        "collection_system": ("/waste_collection/waste-atlas/api/collection-system/"),
        "catchment_geojson": ("/waste_collection/waste-atlas/api/catchment/geojson/"),
        "collector_orga": ("/waste_collection/waste-atlas/api/collector-orga-level/"),
    }

    @classmethod
    def _region_with_borders(cls, name):
        borders = GeoPolygon.objects.create(
            geom="MULTIPOLYGON(((0 0, 0 1, 1 1, 1 0, 0 0)))"
        )
        return Region.objects.create(
            name=name,
            country="DE",
            borders=borders,
            publication_status="published",
        )

    @classmethod
    def setUpTestData(cls):
        ensure_test_default_owner()
        # Provision supported baseline roles before creating plain users;
        # signals then assign the role bundles.
        cls._role_output = io.StringIO()
        call_command("sync_roles", "--apply", stdout=cls._role_output)

        cls.owner = User.objects.create_user("atlas-owner")
        cls.stranger = User.objects.create_user("atlas-stranger")
        cls.direct_grantee = User.objects.create_user("atlas-direct")
        cls.group_grantee = User.objects.create_user("atlas-group")
        cls.grant_group = Group.objects.create(name="atlas-grant-group")
        cls.grant_group.user_set.add(cls.group_grantee)

        cls.moderator = User.objects.create_user("atlas-moderator")
        cls.moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_collection",
                content_type=ContentType.objects.get_for_model(Collection),
            )
        )
        # Non-staff administrator: explicit administer_objects only.
        cls.admin = User.objects.create_user("atlas-admin")
        cls.admin.user_permissions.add(
            Permission.objects.get(codename="administer_objects")
        )
        cls.staff_only = User.objects.create_user("atlas-staff", is_staff=True)
        cls.inactive = User.objects.create_user("atlas-inactive", is_active=False)

        cls.system = CollectionSystem.objects.create(
            name="Atlas System", publication_status="published"
        )
        cls.category = WasteCategory.objects.create(
            name="Biowaste", publication_status="published"
        )
        cls.collector = Collector.objects.create(
            name="Atlas Collector", publication_status="published"
        )

        cls.collections = {}
        cls.catchments = {}
        for status_name in (
            "published",
            "archived",
            "private",
            "review",
            "declined",
        ):
            for year in (2024, 2022):
                key = f"{status_name}_{year}"
                catchment = CollectionCatchment.objects.create(
                    name=f"{key} catchment",
                    region=cls._region_with_borders(key),
                    publication_status="published",
                )
                cls.catchments[key] = catchment
                collector = Collector.objects.create(
                    name=f"{key} collector",
                    catchment=catchment,
                    publication_status="published",
                )
                cls.collections[key] = Collection.objects.create(
                    name=key,
                    owner=cls.owner,
                    catchment=catchment,
                    waste_category=cls.category,
                    collection_system=cls.system,
                    collector=collector,
                    valid_from=date(year, 1, 1),
                    publication_status=status_name,
                )
        # A stranger-owned private row the fixture owner cannot see.
        cls.foreign_private_catchment = CollectionCatchment.objects.create(
            name="foreign private catchment",
            region=cls._region_with_borders("foreign private"),
            publication_status="published",
        )
        cls.catchments["foreign_private_2024"] = cls.foreign_private_catchment
        foreign_private_collector = Collector.objects.create(
            name="foreign private collector",
            catchment=cls.foreign_private_catchment,
            publication_status="published",
        )
        cls.collections["foreign_private_2024"] = Collection.objects.create(
            name="foreign private 2024",
            owner=cls.stranger,
            catchment=cls.foreign_private_catchment,
            waste_category=cls.category,
            collection_system=cls.system,
            collector=foreign_private_collector,
            valid_from=date(2024, 1, 1),
            publication_status="private",
        )
        cls.foreign_review_catchment = CollectionCatchment.objects.create(
            name="foreign review catchment",
            region=cls._region_with_borders("foreign review"),
            publication_status="published",
        )
        cls.catchments["foreign_review_2024"] = cls.foreign_review_catchment
        foreign_review_collector = Collector.objects.create(
            name="foreign review collector",
            catchment=cls.foreign_review_catchment,
            publication_status="published",
        )
        cls.collections["foreign_review_2024"] = Collection.objects.create(
            name="foreign review 2024",
            owner=cls.stranger,
            catchment=cls.foreign_review_catchment,
            waste_category=cls.category,
            collection_system=cls.system,
            collector=foreign_review_collector,
            valid_from=date(2024, 1, 1),
            publication_status="review",
        )
        cls.foreign_archived_2024 = cls._collection(
            "foreign_archived_2024", cls.stranger, "archived", 2022
        )
        cls.col_id = {key: collection.pk for key, collection in cls.collections.items()}
        cls.cat_id = {key: catchment.pk for key, catchment in cls.catchments.items()}

    @classmethod
    def _collection(cls, key, owner, status_name, year):
        catchment = CollectionCatchment.objects.create(
            name=f"{key} catchment",
            region=cls._region_with_borders(key),
            publication_status="published",
        )
        cls.catchments[key] = catchment
        collection = Collection.objects.create(
            name=key,
            owner=owner,
            catchment=catchment,
            waste_category=cls.category,
            collection_system=cls.system,
            collector=cls.collector,
            valid_from=date(year, 1, 1),
            publication_status=status_name,
        )
        cls.collections[key] = collection
        return collection

    def _get(self, endpoint_key="catchment_geojson", year=2024, **params):
        query = {"country": "DE", "year": year, **params}
        response = self.client.get(self.ENDPOINTS[endpoint_key], query)
        self.assertEqual(response.status_code, 200)
        return response

    def _catchment_ids(self, response):
        if isinstance(response.data, dict) and "features" in response.data:
            return {
                feature["properties"]["catchment_id"]
                for feature in response.data["features"]
            }
        return {row["catchment_id"] for row in response.data}


class AtlasHistoricalScopeTests(AtlasScopeFixture, APITestCase):
    """Every actor - including admin, staff and anonymous - defaults to the
    authorized public-historical union; explicit scopes are literal."""

    PUBLIC_HISTORICAL = ("published_2024", "archived_2024")

    def _ids(self, **params):
        return self._catchment_ids(self._get("catchment_geojson", **params))

    def test_anonymous_defaults_to_public_historical(self):
        ids = self._ids()
        self.assertEqual(
            ids,
            {self.cat_id[key] for key in self.PUBLIC_HISTORICAL},
        )

    def test_owner_defaults_to_public_historical_not_workspace(self):
        self.client.force_login(self.owner)
        self.assertEqual(
            self._ids(),
            {self.cat_id[key] for key in self.PUBLIC_HISTORICAL},
        )

    def test_admin_defaults_to_public_historical(self):
        self.client.force_login(self.admin)
        self.assertEqual(
            self._ids(),
            {self.cat_id[key] for key in self.PUBLIC_HISTORICAL},
        )

    def test_staff_only_defaults_to_public_historical(self):
        self.client.force_login(self.staff_only)
        self.assertEqual(
            self._ids(),
            {self.cat_id[key] for key in self.PUBLIC_HISTORICAL},
        )

    def test_inactive_actor_defaults_to_public_historical(self):
        self.client.force_login(self.owner)
        User.objects.filter(pk=self.owner.pk).update(is_active=False)
        self.assertEqual(
            self._ids(),
            {self.cat_id[key] for key in self.PUBLIC_HISTORICAL},
        )
        self.client.logout()

    def test_explicit_historical_scope_matches_default(self):
        self.assertEqual(
            self._ids(scope="historical"),
            {self.cat_id[key] for key in self.PUBLIC_HISTORICAL},
        )

    def test_published_scope_excludes_archived(self):
        ids = self._ids(scope="published")
        self.assertEqual(ids, {self.cat_id["published_2024"]})

    def test_archived_scope_is_literal_archived_only(self):
        ids = self._ids(scope="archived")
        self.assertEqual(ids, {self.cat_id["archived_2024"]})

    def test_historical_defaults_apply_across_theme_and_collector(self):
        for endpoint in ("collection_system", "collector_orga"):
            with self.subTest(endpoint=endpoint):
                ids = self._catchment_ids(self._get(endpoint))
                self.assertEqual(
                    ids,
                    {self.cat_id[key] for key in self.PUBLIC_HISTORICAL},
                )

    OWNER_WORKSPACE = {
        "published_2024",
        "archived_2024",
        "private_2024",
        "review_2024",
        "declined_2024",
    }


class AtlasWorkspaceScopeTests(AtlasScopeFixture, APITestCase):
    """Workspace (``private``/legacy ``mine``), ``owned`` and ``shared``
    scopes resolve through the shared policy, never through staff flags."""

    def _ids(self, scope, user):
        self.client.force_login(user)
        ids = self._catchment_ids(self._get("catchment_geojson", scope=scope))
        self.client.logout()
        return ids

    def test_owner_workspace_contains_all_own_statuses(self):
        ids = self._ids("private", self.owner)
        self.assertEqual(
            ids,
            {self.cat_id[key] for key in AtlasHistoricalScopeTests.OWNER_WORKSPACE},
        )

    def test_legacy_mine_alias_normalizes_to_workspace(self):
        self.assertEqual(
            self._ids("mine", self.owner),
            self._ids("private", self.owner),
        )

    def test_workspace_excludes_unrelated_public_records(self):
        self.assertNotIn(
            self.cat_id["published_2024"],
            self._ids("private", self.stranger),
        )

    def test_owned_scope_contains_only_owned_rows(self):
        self.assertEqual(
            self._ids("owned", self.owner),
            self._ids("private", self.owner),
        )

    def test_stranger_workspace_excludes_owner_rows(self):
        ids = self._ids("private", self.stranger)
        self.assertNotIn(self.cat_id["private_2024"], ids)
        self.assertNotIn(self.cat_id["review_2024"], ids)

    def test_direct_grant_adds_record_to_shared_scope(self):
        collection = self.collections["private_2024"]
        ObjectEditorGrant.objects.create(
            content_type=ContentType.objects.get_for_model(Collection),
            object_id=collection.pk,
            editor=self.direct_grantee,
            granted_by=self.owner,
        )
        ids = self._ids("shared", self.direct_grantee)
        self.assertIn(self.cat_id["private_2024"], ids)
        # Shared scope carries no owned and no unrelated public rows.
        self.assertNotIn(self.cat_id["published_2024"], ids)

    def test_direct_grant_removable_on_next_request(self):
        collection = self.collections["private_2024"]
        grant = ObjectEditorGrant.objects.create(
            content_type=ContentType.objects.get_for_model(Collection),
            object_id=collection.pk,
            editor=self.direct_grantee,
            granted_by=self.owner,
        )
        self.assertIn(
            self.cat_id["private_2024"],
            self._ids("shared", self.direct_grantee),
        )
        grant.delete()
        self.assertNotIn(
            self.cat_id["private_2024"],
            self._ids("shared", self.direct_grantee),
        )

    def test_group_grant_persists_after_direct_removed(self):
        collection = self.collections["private_2024"]
        ct = ContentType.objects.get_for_model(Collection)
        direct = ObjectEditorGrant.objects.create(
            content_type=ct,
            object_id=collection.pk,
            editor=self.group_grantee,
            granted_by=self.owner,
        )
        ObjectGroupEditorGrant.objects.create(
            content_type=ct,
            object_id=collection.pk,
            group=self.grant_group,
            granted_by=self.owner,
        )
        direct.delete()
        self.assertIn(
            self.cat_id["private_2024"],
            self._ids("shared", self.group_grantee),
        )

    def test_group_membership_removal_drops_group_granted_rows(self):
        collection = self.collections["private_2024"]
        ObjectGroupEditorGrant.objects.create(
            content_type=ContentType.objects.get_for_model(Collection),
            object_id=collection.pk,
            group=self.grant_group,
            granted_by=self.owner,
        )
        self.grant_group.user_set.remove(self.group_grantee)
        self.assertNotIn(
            self.cat_id["private_2024"],
            self._ids("shared", self.group_grantee),
        )


class AtlasModeratedScopeTests(AtlasScopeFixture, APITestCase):
    """Literal ``review``/``declined`` scopes follow the shared visibility
    rules: owner/editor see their own, moderators see all matching rows,
    staff-only and strangers see none."""

    def _ids(self, scope, user=None):
        if user is not None:
            self.client.force_login(user)
        ids = self._catchment_ids(self._get("catchment_geojson", scope=scope))
        if user is not None:
            self.client.logout()
        return ids

    def test_owner_review_scope_shows_own_review_only(self):
        self.assertEqual(
            self._ids("review", self.owner),
            {self.cat_id["review_2024"]},
        )

    def test_moderator_review_scope_shows_all_review_rows(self):
        self.assertEqual(
            self._ids("review", self.moderator),
            {
                self.cat_id["review_2024"],
                self.cat_id["foreign_review_2024"],
            },
        )

    def test_admin_review_scope_shows_all_review_rows(self):
        self.assertEqual(
            self._ids("review", self.admin),
            {
                self.cat_id["review_2024"],
                self.cat_id["foreign_review_2024"],
            },
        )

    def test_staff_only_review_scope_is_empty(self):
        self.assertEqual(self._ids("review", self.staff_only), set())

    def test_stranger_review_scope_shows_only_own_review(self):
        # ``self.stranger`` owns the foreign review row, so the literal
        # review scope returns exactly that row and nothing else.
        self.assertEqual(
            self._ids("review", self.stranger),
            {self.cat_id["foreign_review_2024"]},
        )

    def test_actor_without_review_rows_gets_empty_review_scope(self):
        self.assertEqual(self._ids("review", self.direct_grantee), set())

    def test_owner_declined_scope_shows_own_declined(self):
        self.assertEqual(
            self._ids("declined", self.owner),
            {self.cat_id["declined_2024"]},
        )

    def test_moderator_declined_scope_shows_all_declined(self):
        self.assertEqual(
            self._ids("declined", self.moderator),
            {self.cat_id["declined_2024"]},
        )

    def test_staff_only_declined_scope_is_empty(self):
        self.assertEqual(self._ids("declined", self.staff_only), set())


class AtlasAllAndUnknownScopeTests(AtlasScopeFixture, APITestCase):
    """``all`` is an explicit administrator scope; unknown, blank and the
    legacy ``staff`` value always yield an empty result - never a
    silent public fallback."""

    def _ids(self, scope, user=None):
        if user is not None:
            self.client.force_login(user)
        response = self.client.get(
            self.ENDPOINTS["catchment_geojson"],
            {"country": "DE", "year": 2024, "scope": scope},
        )
        if user is not None:
            self.client.logout()
        self.assertEqual(response.status_code, 200)
        return self._catchment_ids(response)

    def test_admin_all_scope_covers_every_status(self):
        ids = self._ids("all", self.admin)
        self.assertEqual(
            ids,
            {
                self.cat_id["published_2024"],
                self.cat_id["archived_2024"],
                self.cat_id["private_2024"],
                self.cat_id["review_2024"],
                self.cat_id["declined_2024"],
                self.cat_id["foreign_private_2024"],
                self.cat_id["foreign_review_2024"],
            },
        )

    def test_nonadmin_owner_all_scope_is_empty(self):
        self.assertEqual(self._ids("all", self.owner), set())

    def test_staff_only_all_scope_is_empty(self):
        self.assertEqual(self._ids("all", self.staff_only), set())

    def test_moderator_all_scope_is_empty(self):
        self.assertEqual(self._ids("all", self.moderator), set())

    def test_unknown_scope_is_empty_even_for_admin(self):
        self.assertEqual(self._ids("does-not-exist", self.admin), set())

    def test_blank_scope_is_empty_for_admin(self):
        self.assertEqual(self._ids("", self.admin), set())

    def test_admin_all_scope_excludes_unknown_status_roots(self):
        unknown_catchment = CollectionCatchment.objects.create(
            name="unknown state catchment",
            region=self._region_with_borders("unknown state"),
            publication_status="published",
        )
        Collection.objects.create(
            name="unknown state collection",
            owner=self.owner,
            catchment=unknown_catchment,
            waste_category=self.category,
            collection_system=self.system,
            valid_from=date(2024, 1, 1),
            publication_status="weird",
        )
        ids = self._ids("all", self.admin)
        self.assertNotIn(unknown_catchment.pk, ids)

    def test_legacy_staff_scope_is_empty_for_admin(self):
        self.assertEqual(self._ids("staff", self.admin), set())

    def test_legacy_staff_scope_is_empty_for_staff(self):
        self.assertEqual(self._ids("staff", self.staff_only), set())


class AtlasModelFailClosedTests(TestCase):
    """Unregistered models and unknown scopes fail closed regardless of
    who asks, instead of leaking rows through the adapter."""

    def test_unknown_model_fails_closed_for_every_scope(self):
        admin = self._admin()
        for scope in (None, "historical", "published", "all", "bogus"):
            with self.subTest(scope=scope):
                self.assertFalse(
                    _atlas_queryset(WasteAtlasMapConfiguration, admin, scope).exists()
                )

    @staticmethod
    def _admin():
        admin = User.objects.create_user("model-admin")
        admin.user_permissions.add(
            Permission.objects.get(codename="administer_objects")
        )
        return admin


class AtlasAnonymousAndInactiveScopeTests(AtlasScopeFixture, APITestCase):
    """Anonymous and inactive actors keep only the public scopes."""

    def _ids(self, scope=None):
        params = {"country": "DE", "year": 2024}
        if scope is not None:
            params["scope"] = scope
        response = self.client.get(self.ENDPOINTS["catchment_geojson"], params)
        self.assertEqual(response.status_code, 200)
        return self._catchment_ids(response)

    def test_anonymous_private_scope_is_empty(self):
        self.assertEqual(self._ids("private"), set())

    def test_anonymous_mine_scope_is_empty(self):
        self.assertEqual(self._ids("mine"), set())

    def test_anonymous_review_scope_is_empty(self):
        self.assertEqual(self._ids("review"), set())

    def test_anonymous_all_scope_is_empty(self):
        self.assertEqual(self._ids("all"), set())

    def test_anonymous_unknown_scope_is_empty(self):
        self.assertEqual(self._ids("bogus"), set())

    def test_inactive_actor_has_public_scopes_but_no_grants(self):
        self.client.force_login(self.direct_grantee)
        User.objects.filter(pk=self.direct_grantee.pk).update(is_active=False)
        collection = self.collections["private_2024"]
        ObjectEditorGrant.objects.create(
            content_type=ContentType.objects.get_for_model(Collection),
            object_id=collection.pk,
            editor=self.direct_grantee,
            granted_by=self.owner,
        )
        self.assertEqual(
            self._catchment_ids(self._get("catchment_geojson", scope="shared")),
            set(),
        )
        self.assertEqual(
            self._catchment_ids(self._get("catchment_geojson")),
            {
                self.cat_id["published_2024"],
                self.cat_id["archived_2024"],
            },
        )
        self.client.logout()
