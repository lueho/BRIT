"""Atlas supporting-evidence authorization.

CPV/ACPV values and CatchmentRevision geometry are independently
reviewable models: collection moderation or ownership never leaks into
them, and public historical evidence remains available on readable
collections so version-chain metrics still resolve.
"""

import io
from datetime import date

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APITestCase

from maps.models import CatchmentRevision, GeoPolygon, Region
from sources.waste_collection.models import (
    AggregatedCollectionPropertyValue,
    Collection,
    CollectionCatchment,
    CollectionPropertyValue,
    CollectionSystem,
    WasteCategory,
)
from sources.waste_collection.waste_atlas.viewsets import (
    _effective_scope,
    _supporting_queryset,
)
from utils.object_management.models import (
    ObjectEditorGrant,
)
from utils.properties.models import Property, Unit
from utils.tests.testcases import ensure_test_default_owner


class SupportingEvidenceFixture:
    """Selected collection, predecessor chain and evidence fixtures."""

    CONNECTION_RATE_ENDPOINT = "/waste_collection/waste-atlas/api/connection-rate/"
    CHANGE_GEOJSON_ENDPOINT = (
        "/waste_collection/waste-atlas/api/catchment/collection-change-geojson/"
    )

    @classmethod
    def _region_with_borders(cls, name):
        borders = GeoPolygon.objects.create(
            geom="MULTIPOLYGON(((0 0, 0 1, 1 1, 1 0, 0 0)))"
        )
        return Region.objects.create(name=name, country="DE", borders=borders)

    @classmethod
    def _collection(cls, key, owner, status_name, year, catchment):
        return Collection.objects.create(
            name=key,
            owner=owner,
            catchment=catchment,
            waste_category=cls.category,
            collection_system=cls.system,
            valid_from=date(year, 1, 1),
            participation_policy="MANDATORY",
            publication_status=status_name,
        )

    @classmethod
    def setUpTestData(cls):
        ensure_test_default_owner()
        cls._role_output = io.StringIO()
        call_command("sync_roles", "--apply", stdout=cls._role_output)

        cls.owner = User.objects.create_user("sup-owner")
        cls.stranger = User.objects.create_user("sup-stranger")
        cls.grantee = User.objects.create_user("sup-grantee")
        cls.collection_moderator = User.objects.create_user("sup-mod")
        cls.collection_moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_collection",
                content_type=ContentType.objects.get_for_model(Collection),
            )
        )
        cls.inactive = User.objects.create_user("sup-inactive", is_active=False)

        cls.system = CollectionSystem.objects.create(
            name="Door to door", publication_status="published"
        )
        cls.category = WasteCategory.objects.create(
            name="Biowaste", publication_status="published"
        )
        cls.region = cls._region_with_borders("sup-region")
        cls.catchment = CollectionCatchment.objects.create(
            name="sup-catchment",
            region=cls.region,
            publication_status="published",
        )

        cls.prop, _ = Property.objects.get_or_create(
            id=4, defaults={"name": "Connection rate"}
        )
        cls.unit, _ = Unit.objects.get_or_create(
            name="%", defaults={"dimensionless": True}
        )
        cls.prop.allowed_units.add(cls.unit)

        cls.selected = cls._collection(
            "selected pub", cls.owner, "published", 2024, cls.catchment
        )
        cls.archived_pred = cls._collection(
            "archived pred", cls.stranger, "archived", 2020, cls.catchment
        )
        cls.private_pred = cls._collection(
            "private pred", cls.stranger, "private", 2019, cls.catchment
        )
        cls.selected.predecessors.add(cls.archived_pred, cls.private_pred)


def _cpv(collection, prop, unit, owner, status_name, year, average):
    return CollectionPropertyValue.objects.create(
        collection=collection,
        property=prop,
        unit=unit,
        year=year,
        average=average,
        owner=owner,
        publication_status=status_name,
    )


class SupportingCpvScopeTests(SupportingEvidenceFixture, APITestCase):
    """The CPV supporting queryset is independently authorized: public
    historical evidence stays available under valid collection scopes and
    non-public rows require the evidence model's own rights."""

    def _rate(self, user=None, **params):
        if user is not None:
            self.client.force_login(user)
        query = {"country": "DE", "year": 2024, **params}
        response = self.client.get(self.CONNECTION_RATE_ENDPOINT, query)
        if user is not None:
            self.client.logout()
        self.assertEqual(response.status_code, 200)
        rows = {row["catchment_id"]: row for row in response.data}
        return rows.get(self.catchment.pk)

    def test_public_cpv_on_selected_collection_feeds_metric(self):
        _cpv(
            self.selected,
            self.prop,
            self.unit,
            self.owner,
            "published",
            2023,
            80,
        )
        row = self._rate()
        self.assertIsNotNone(row)
        self.assertAlmostEqual(row["connection_rate"], 0.8)
        self.assertEqual(row["reporting_year"], 2023)

    def test_foreign_private_cpv_never_feeds_metric(self):
        _cpv(
            self.selected,
            self.prop,
            self.unit,
            self.owner,
            "published",
            2020,
            50,
        )
        _cpv(
            self.selected,
            self.prop,
            self.unit,
            self.stranger,
            "private",
            2023,
            99,
        )
        row = self._rate()
        self.assertEqual(row["reporting_year"], 2020)

    def test_foreign_review_cpv_needs_cpv_moderation_not_collection_mod(
        self,
    ):
        review_selected = self._collection(
            "review sel", self.stranger, "review", 2024, self.catchment
        )
        _cpv(
            review_selected,
            self.prop,
            self.unit,
            self.stranger,
            "review",
            2023,
            99,
        )
        # Collection moderation alone must not expose foreign review CPV:
        # the collection is admitted by scope, the CPV is not.
        row = self._rate(self.collection_moderator, scope="review")
        self.assertIsNotNone(row)
        self.assertIsNone(row["connection_rate"])

    def test_cpv_moderation_exposes_review_cpv(self):
        review_selected = self._collection(
            "review sel", self.stranger, "review", 2024, self.catchment
        )
        _cpv(
            review_selected,
            self.prop,
            self.unit,
            self.stranger,
            "review",
            2023,
            99,
        )
        self.collection_moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_collectionpropertyvalue",
                content_type=ContentType.objects.get_for_model(CollectionPropertyValue),
            )
        )
        row = self._rate(self.collection_moderator, scope="review")
        self.assertIsNotNone(row)
        self.assertEqual(row["reporting_year"], 2023)

    def test_owner_workspace_sees_own_private_cpv(self):
        _cpv(
            self.selected,
            self.prop,
            self.unit,
            self.owner,
            "private",
            2023,
            77,
        )
        row = self._rate(self.owner, scope="private")
        self.assertIsNotNone(row)
        self.assertAlmostEqual(row["connection_rate"], 0.77)

    def test_grant_on_cpv_exposes_private_evidence_and_revocation_hides(
        self,
    ):
        cpv = _cpv(
            self.selected,
            self.prop,
            self.unit,
            self.stranger,
            "private",
            2023,
            66,
        )
        ct = ContentType.objects.get_for_model(Collection)
        grant_collection = ObjectEditorGrant.objects.create(
            content_type=ct,
            object_id=self.selected.pk,
            editor=self.grantee,
            granted_by=self.stranger,
        )
        # Collection grant alone must not expose the CPV.
        row = self._rate(self.grantee, scope="private")
        self.assertIsNotNone(row)
        self.assertIsNone(row["connection_rate"])

        cpv_grant = ObjectEditorGrant.objects.create(
            content_type=ContentType.objects.get_for_model(CollectionPropertyValue),
            object_id=cpv.pk,
            editor=self.grantee,
            granted_by=self.stranger,
        )
        row = self._rate(self.grantee, scope="private")
        self.assertIsNotNone(row)
        self.assertAlmostEqual(row["connection_rate"], 0.66)

        cpv_grant.delete()
        row = self._rate(self.grantee, scope="private")
        self.assertIsNotNone(row)
        self.assertIsNone(row["connection_rate"])
        grant_collection.delete()

    def test_public_cpv_on_unreadable_private_sibling_never_leaks(self):
        # A private predecessor's public CPV must not enter chain metrics:
        # the collection itself is not readable.
        _cpv(
            self.private_pred,
            self.prop,
            self.unit,
            self.stranger,
            "published",
            2023,
            99,
        )
        row = self._rate()
        self.assertIsNotNone(row)
        self.assertIsNone(row["connection_rate"])

    def test_public_cpv_on_readable_archived_sibling_feeds_metric(self):
        _cpv(
            self.archived_pred,
            self.prop,
            self.unit,
            self.stranger,
            "published",
            2020,
            44,
        )
        row = self._rate()
        self.assertIsNotNone(row)
        self.assertAlmostEqual(row["connection_rate"], 0.44)
        self.assertEqual(row["reporting_year"], 2020)


class SupportingRevisionScopeTests(SupportingEvidenceFixture, APITestCase):
    """CatchmentRevision access is independently authorized; a private
    revision never leaks through collection rights, and grant revocation
    falls back to public snapshots on the next request."""

    PUBLIC_GEOM = "MULTIPOLYGON(((0 0, 0 1, 1 1, 1 0, 0 0)))"
    PRIVATE_GEOM = "MULTIPOLYGON(((2 2, 2 3, 3 3, 3 2, 2 2)))"

    def _revision(self, owner, status_name, geom, effective_from=None):
        return CatchmentRevision.objects.create(
            catchment=self.catchment,
            owner=owner,
            geom=geom,
            effective_from=effective_from or date(2000, 1, 1),
            publication_status=status_name,
            change_reason="initial",
        )

    def _feature_geoms(self, user=None, **params):
        if user is not None:
            self.client.force_login(user)
        query = {"country": "DE", "year": 2024, **params}
        response = self.client.get(
            "/waste_collection/waste-atlas/api/catchment/geojson/", query
        )
        if user is not None:
            self.client.logout()
        self.assertEqual(response.status_code, 200)
        return {
            feature["properties"]["catchment_id"]: feature["geometry"]
            for feature in response.data["features"]
        }

    def _revision_q_ids(self, user):
        return set(
            _supporting_queryset(CatchmentRevision, user).values_list("pk", flat=True)
        )

    def test_public_revision_available_to_everyone(self):
        revision = self._revision(self.stranger, "published", self.PUBLIC_GEOM)
        self.assertIn(revision.pk, self._revision_q_ids(None))
        self.assertIn(revision.pk, self._revision_q_ids(self.stranger))

    def test_private_revision_visible_only_to_its_actor(self):
        revision = self._revision(self.owner, "private", self.PRIVATE_GEOM)
        self.assertNotIn(revision.pk, self._revision_q_ids(None))
        self.assertNotIn(revision.pk, self._revision_q_ids(self.stranger))

    def test_workspace_scope_includes_own_private_revision(self):
        revision = self._revision(self.owner, "private", self.PRIVATE_GEOM)
        ids = self._revision_q_scope(self.owner, "private")
        self.assertIn(revision.pk, ids)

    def _revision_q_scope(self, user, scope):
        normalized, _ = _effective_scope(user, scope)
        return set(
            _supporting_queryset(CatchmentRevision, user, normalized).values_list(
                "pk", flat=True
            )
        )

    def test_collection_moderator_cannot_see_foreign_review_revision(self):
        revision = self._revision(self.stranger, "review", self.PUBLIC_GEOM)
        ids = self._revision_q_scope(self.collection_moderator, "review")
        self.assertNotIn(revision.pk, ids)

    def test_revision_moderation_exposes_review_revision(self):
        revision = self._revision(self.stranger, "review", self.PUBLIC_GEOM)
        self.collection_moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_catchmentrevision",
                content_type=ContentType.objects.get_for_model(CatchmentRevision),
            )
        )
        ids = self._revision_q_scope(self.collection_moderator, "review")
        self.assertIn(revision.pk, ids)

    def test_private_revision_never_exposed_by_collection_rights(self):
        revision = self._revision(self.stranger, "private", self.PRIVATE_GEOM)
        self.collection_moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_catchmentrevision",
                content_type=ContentType.objects.get_for_model(CatchmentRevision),
            )
        )
        ids = self._revision_q_scope(self.collection_moderator, "all")
        # Collection-level privileges never open another model's private
        # rows; only genuine admin rights on the evidence model would.
        self.assertNotIn(revision.pk, ids)

    def test_private_revision_grant_then_revoke_in_workspace(self):
        revision = self._revision(self.stranger, "private", self.PRIVATE_GEOM)
        self._revision(self.owner, "published", self.PUBLIC_GEOM)
        grant = ObjectEditorGrant.objects.create(
            content_type=ContentType.objects.get_for_model(CatchmentRevision),
            object_id=revision.pk,
            editor=self.grantee,
            granted_by=self.stranger,
        )
        ids = self._revision_q_scope(self.grantee, "private")
        self.assertIn(revision.pk, ids)
        grant.delete()
        ids = self._revision_q_scope(self.grantee, "private")
        self.assertNotIn(revision.pk, ids)


class SupportingAggregatedValueTests(SupportingEvidenceFixture, TestCase):
    """Aggregated values follow the same independent rules; Q membership
    assertions are sufficient for this evidence model."""

    def test_public_acpv_available_to_anonymous(self):
        acpv = AggregatedCollectionPropertyValue.objects.create(
            property=self.prop,
            unit=self.unit,
            year=2024,
            average=55,
            publication_status="published",
        )
        acpv.collections.add(self.selected)
        ids = set(
            _supporting_queryset(AggregatedCollectionPropertyValue, None).values_list(
                "pk", flat=True
            )
        )
        self.assertIn(acpv.pk, ids)

    def test_private_acpv_requires_own_rights(self):
        acpv = AggregatedCollectionPropertyValue.objects.create(
            property=self.prop,
            unit=self.unit,
            year=2024,
            average=55,
            owner=self.stranger,
            publication_status="private",
        )
        acpv.collections.add(self.selected)
        ids = set(
            _supporting_queryset(
                AggregatedCollectionPropertyValue, self.owner
            ).values_list("pk", flat=True)
        )
        self.assertNotIn(acpv.pk, ids)

    def _acpv_scope_ids(self, user, scope):
        normalized, _ = _effective_scope(user, scope)
        return set(
            _supporting_queryset(
                AggregatedCollectionPropertyValue, user, normalized
            ).values_list("pk", flat=True)
        )

    def test_collection_moderation_alone_hides_foreign_review_acpv(self):
        acpv = AggregatedCollectionPropertyValue.objects.create(
            property=self.prop,
            unit=self.unit,
            year=2024,
            average=55,
            owner=self.stranger,
            publication_status="review",
        )
        acpv.collections.add(self.selected)
        self.assertNotIn(
            acpv.pk,
            self._acpv_scope_ids(self.collection_moderator, "review"),
        )

    def test_matching_model_moderation_exposes_review_acpv(self):
        acpv = AggregatedCollectionPropertyValue.objects.create(
            property=self.prop,
            unit=self.unit,
            year=2024,
            average=55,
            owner=self.stranger,
            publication_status="review",
        )
        acpv.collections.add(self.selected)
        self.collection_moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_aggregatedcollectionpropertyvalue",
                content_type=ContentType.objects.get_for_model(
                    AggregatedCollectionPropertyValue
                ),
            )
        )
        self.assertIn(
            acpv.pk,
            self._acpv_scope_ids(self.collection_moderator, "review"),
        )

    def test_workspace_acpv_grant_then_revocation(self):
        acpv = AggregatedCollectionPropertyValue.objects.create(
            property=self.prop,
            unit=self.unit,
            year=2024,
            average=55,
            owner=self.stranger,
            publication_status="private",
        )
        acpv.collections.add(self.selected)
        grant = ObjectEditorGrant.objects.create(
            content_type=ContentType.objects.get_for_model(
                AggregatedCollectionPropertyValue
            ),
            object_id=acpv.pk,
            editor=self.grantee,
            granted_by=self.stranger,
        )
        self.assertIn(acpv.pk, self._acpv_scope_ids(self.grantee, "private"))
        grant.delete()
        self.assertNotIn(acpv.pk, self._acpv_scope_ids(self.grantee, "private"))
