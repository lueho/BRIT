"""Governed programmatic collection update authorization.

The in-place update route must resolve actor, capability, object access
and lifecycle through the shared ``content_mutation`` boundary: identity
guards are conflict checks, not authorization; a meaningful compound edit
records exactly one root revision and audit; reference and flyer writes
are independently authorized and rolled back atomically.
"""

import io
from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from bibliography.models import Source
from maps.models import GeoPolygon, Region
from materials.models import Material
from sources.waste_collection.models import (
    BinConfiguration,
    Collection,
    CollectionCatchment,
    CollectionFrequency,
    CollectionSystem,
    Collector,
    FeeSystem,
    WasteCategory,
    WasteFlyer,
)
from sources.waste_collection.services import resolve_flyer
from utils.object_management.models import (
    ObjectEditorGrant,
    ObjectGroupEditorGrant,
    ReviewAction,
)
from utils.object_management.services import _record_event
from utils.tests.testcases import ensure_test_default_owner


class CollectionUpdateFixture:
    """Collections, references and actor fixtures for update tests."""

    UPDATE_URL = "api-waste-collection-update"
    LEGACY_URL = "api-waste-collection-update-collection"

    @classmethod
    def _region_with_borders(cls, name):
        return Region.objects.create(
            name=name,
            country="DE",
            borders=GeoPolygon.objects.create(
                geom="MULTIPOLYGON(((0 0, 0 1, 1 1, 1 0, 0 0)))"
            ),
        )

    @classmethod
    def _collection(cls, name, owner, status_name, year=2024):
        return Collection.objects.create(
            name=name,
            owner=owner,
            catchment=cls.catchment,
            collector=cls.collector,
            collection_system=cls.system,
            waste_category=cls.category,
            frequency=cls.frequency,
            fee_system=cls.fee_system,
            bin_configuration=cls.bin_configuration,
            valid_from=date(year, 1, 1),
            description="original description",
            publication_status=status_name,
        )

    @classmethod
    def setUpTestData(cls):
        ensure_test_default_owner()
        cls._role_output = io.StringIO()
        call_command("sync_roles", "--apply", stdout=cls._role_output)

        cls.owner = User.objects.create_user("update-owner")
        cls.stranger = User.objects.create_user("update-stranger")
        cls.grantee = User.objects.create_user("update-grantee")
        cls.group_grantee = User.objects.create_user("update-group")
        cls.admin = User.objects.create_user("update-admin")
        cls.staff_only = User.objects.create_user("update-staff", is_staff=True)
        cls.moderator = User.objects.create_user("update-moderator")
        cls.inactive = User.objects.create_user("update-inactive", is_active=False)

        admin_perm = Permission.objects.get(codename="administer_objects")
        cls.admin.user_permissions.add(admin_perm)
        cls.moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_collection",
                content_type=ContentType.objects.get_for_model(Collection),
            )
        )
        cls.change_collection_perm = Permission.objects.get(
            codename="change_collection",
            content_type=ContentType.objects.get_for_model(Collection),
        )

        # The provisioned baseline role supplies change_collection for all
        # normal users; only intentional negative fixtures are stripped.
        cls.no_cap = User.objects.create_user("update-no-cap")
        cls.no_cap.groups.clear()
        cls.no_cap.user_permissions.clear()
        cls.update_only = User.objects.create_user("update-only")
        cls.update_only.groups.clear()
        cls.update_only.user_permissions.clear()
        cls.update_only.user_permissions.add(cls.change_collection_perm)
        cls.staff_only.groups.clear()
        cls.staff_only.user_permissions.clear()

        cls.group = Group.objects.create(name="update-group-actors")
        cls.group.user_set.add(cls.group_grantee)

        cls.system = CollectionSystem.objects.create(
            name="update system", publication_status="published"
        )
        cls.category = WasteCategory.objects.create(
            name="update category", publication_status="published"
        )
        cls.catchment = CollectionCatchment.objects.create(
            name="update catchment",
            region=cls._region_with_borders("update region"),
            publication_status="published",
        )
        cls.collector = Collector.objects.create(
            name="update collector", publication_status="published"
        )
        cls.frequency = CollectionFrequency.objects.create(
            name="update frequency", publication_status="published"
        )
        cls.fee_system = FeeSystem.objects.create(
            name="update fee", publication_status="published"
        )
        cls.bin_configuration = BinConfiguration.objects.create(
            name="update bin", publication_status="published"
        )

        cls.private_col = cls._collection("private col", cls.owner, "private")
        cls.review_col = cls._collection("review col", cls.owner, "review")
        cls.declined_col = cls._collection("declined col", cls.owner, "declined")
        cls.published_col = cls._collection("published col", cls.owner, "published")
        cls.archived_col = cls._collection("archived col", cls.owner, "archived")
        cls.foreign_private = cls._collection(
            "foreign private", cls.stranger, "private"
        )
        cls.staff_col = cls._collection("staff col", cls.staff_only, "private")
        cls.no_cap_col = cls._collection("no cap col", cls.no_cap, "private")
        cls.update_only_col = cls._collection(
            "update only col", cls.update_only, "private"
        )

        cls.private_collector = Collector.objects.create(
            name="private collector",
            owner=cls.stranger,
            publication_status="private",
        )
        cls.private_source = Source.objects.create(
            owner=cls.stranger,
            title="Private source",
            abbreviation="private-src",
            publication_status="private",
        )
        cls.public_source = Source.objects.create(
            owner=cls.stranger,
            title="Public source",
            abbreviation="public-src",
            publication_status="published",
        )
        cls.public_material = Material.objects.create(
            name="public material",
            owner=cls.stranger,
            publication_status="published",
        )
        cls.private_material = Material.objects.create(
            name="private material",
            owner=cls.stranger,
            publication_status="private",
        )
        cls.private_frequency = CollectionFrequency.objects.create(
            name="private frequency",
            owner=cls.stranger,
            publication_status="private",
        )
        cls.private_fee = FeeSystem.objects.create(
            name="private fee",
            owner=cls.stranger,
            publication_status="private",
        )
        cls.private_bin = BinConfiguration.objects.create(
            name="private bin",
            owner=cls.stranger,
            publication_status="private",
        )
        cls.hidden_flyer = WasteFlyer.objects.create(
            owner=cls.stranger,
            title="Hidden flyer",
            url="https://example.com/hidden",
            publication_status="private",
        )
        cls.public_flyer = WasteFlyer.objects.create(
            owner=cls.stranger,
            title="Public flyer",
            url="https://example.com/public",
            publication_status="published",
        )

    def _url(self, collection, name=None):
        return reverse(name or self.UPDATE_URL, kwargs={"pk": collection.pk})

    def _payload(self, collection, **overrides):
        payload = {
            "expected_catchment_id": collection.catchment_id,
            "expected_waste_category_id": collection.waste_category_id,
            "expected_collection_system_id": collection.collection_system_id,
            "expected_publication_status": collection.publication_status,
            "expected_valid_from": collection.valid_from.isoformat(),
        }
        payload.update(overrides)
        return payload

    def _post(self, user, collection, name=None, **payload):
        self.client.force_login(user)
        return self.client.post(
            self._url(collection, name=name),
            self._payload(collection, **payload),
            format="json",
        )

    def _edited_events(self, collection):
        return ReviewAction.objects.filter(
            content_type__model="collection",
            object_id=collection.pk,
            action=ReviewAction.ACTION_EDITED,
        )


class CollectionUpdateAccessTests(CollectionUpdateFixture, APITestCase):
    def test_owner_updates_private_collection(self):
        response = self._post(
            self.owner,
            self.private_col,
            description="updated",
            access_control_bp=True,
            access_control_pap=False,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.private_col.refresh_from_db()
        self.assertEqual(self.private_col.description, "updated")
        self.assertEqual(self.private_col.access_control_bp, True)
        self.assertEqual(self.private_col.access_control_pap, False)

    def test_owner_edit_emits_single_root_audit(self):
        before = self.private_col.content_revision
        response = self._post(self.owner, self.private_col, description="audit me")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.private_col.refresh_from_db()
        self.assertEqual(self.private_col.content_revision, before + 1)
        events = self._edited_events(self.private_col)
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.first().user_id, self.owner.pk)
        self.assertEqual(
            events.first().content_revision,
            self.private_col.content_revision,
        )

    def test_direct_grantee_updates_collection_via_legacy_alias(self):
        ct = ContentType.objects.get_for_model(Collection)
        ObjectEditorGrant.objects.create(
            content_type=ct,
            object_id=self.private_col.pk,
            editor=self.grantee,
            granted_by=self.owner,
        )
        response = self._post(
            self.grantee,
            self.private_col,
            name=self.LEGACY_URL,
            description="legacy granted",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.private_col.refresh_from_db()
        self.assertEqual(self.private_col.description, "legacy granted")

    def test_direct_grantee_updates_review_collection(self):
        ct = ContentType.objects.get_for_model(Collection)
        ObjectEditorGrant.objects.create(
            content_type=ct,
            object_id=self.review_col.pk,
            editor=self.grantee,
            granted_by=self.owner,
        )
        response = self._post(self.grantee, self.review_col, description="review edit")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.review_col.refresh_from_db()
        self.assertEqual(self.review_col.publication_status, "review")

    def test_group_grantee_updates_declined_collection(self):
        ct = ContentType.objects.get_for_model(Collection)
        ObjectGroupEditorGrant.objects.create(
            content_type=ct,
            object_id=self.declined_col.pk,
            group=self.group,
            granted_by=self.owner,
        )
        response = self._post(
            self.group_grantee, self.declined_col, description="declined edit"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.declined_col.refresh_from_db()
        self.assertEqual(self.declined_col.publication_status, "declined")

    def test_prior_review_history_and_comments_are_retained(self):
        ct = ContentType.objects.get_for_model(self.review_col)
        ReviewAction.objects.create(
            content_type=ct,
            object_id=self.review_col.pk,
            user=self.owner,
            action=ReviewAction.ACTION_SUBMITTED,
            comment="prior submission",
            content_revision=self.review_col.content_revision,
        )
        ReviewAction.objects.create(
            content_type=ct,
            object_id=self.review_col.pk,
            user=self.moderator,
            action=ReviewAction.ACTION_COMMENT,
            comment="prior moderator note",
            content_revision=self.review_col.content_revision,
        )
        response = self._post(
            self.owner, self.review_col, description="edited after notes"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        comments = set(
            ReviewAction.objects.filter(
                content_type=ct, object_id=self.review_col.pk
            ).values_list("comment", flat=True)
        )
        self.assertIn("prior submission", comments)
        self.assertIn("prior moderator note", comments)
        self.review_col.refresh_from_db()
        self.assertEqual(self.review_col.publication_status, "review")

    def test_revoked_group_membership_is_404_on_next_request(self):
        ct = ContentType.objects.get_for_model(Collection)
        ObjectGroupEditorGrant.objects.create(
            content_type=ct,
            object_id=self.private_col.pk,
            group=self.group,
            granted_by=self.owner,
        )
        response = self._post(
            self.group_grantee, self.private_col, description="grouped"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.group.user_set.remove(self.group_grantee)
        response = self._post(
            self.group_grantee, self.private_col, description="revoked"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_direct_grantee_updates_collection(self):
        ct = ContentType.objects.get_for_model(Collection)
        ObjectEditorGrant.objects.create(
            content_type=ct,
            object_id=self.private_col.pk,
            editor=self.grantee,
            granted_by=self.owner,
        )
        response = self._post(self.grantee, self.private_col, description="granted")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.private_col.refresh_from_db()
        self.assertEqual(self.private_col.description, "granted")

    def test_group_grantee_updates_collection(self):
        ct = ContentType.objects.get_for_model(Collection)
        ObjectGroupEditorGrant.objects.create(
            content_type=ct,
            object_id=self.private_col.pk,
            group=self.group,
            granted_by=self.owner,
        )
        response = self._post(
            self.group_grantee, self.private_col, description="grouped"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.private_col.refresh_from_db()
        self.assertEqual(self.private_col.description, "grouped")

    def test_admin_updates_foreign_collection(self):
        response = self._post(self.admin, self.private_col, description="admin edit")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.private_col.refresh_from_db()
        self.assertEqual(self.private_col.description, "admin edit")

    def test_staff_flag_alone_is_denied(self):
        response = self._post(self.staff_only, self.staff_col, description="staff")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.staff_col.refresh_from_db()
        self.assertEqual(self.staff_col.description, "original description")

    def test_moderation_alone_is_denied(self):
        response = self._post(self.moderator, self.review_col, description="mod")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.review_col.refresh_from_db()
        self.assertEqual(self.review_col.description, "original description")

    def test_owner_without_capability_is_denied(self):
        response = self._post(self.no_cap, self.no_cap_col, description="no cap")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.no_cap_col.refresh_from_db()
        self.assertEqual(self.no_cap_col.description, "original description")
        self.assertEqual(self._edited_events(self.no_cap_col).count(), 0)

    def test_stranger_foreign_private_is_404(self):
        response = self._post(self.stranger, self.private_col, description="stranger")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_is_denied(self):
        response = self.client.post(
            self._url(self.private_col),
            self._payload(self.private_col, description="anon"),
            format="json",
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_inactive_actor_is_denied(self):
        collection = self._collection("inactive col", self.inactive, "private")
        response = self._post(self.inactive, collection, description="inactive")
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_revoked_direct_grant_is_404_on_next_request(self):
        ct = ContentType.objects.get_for_model(Collection)
        grant = ObjectEditorGrant.objects.create(
            content_type=ct,
            object_id=self.private_col.pk,
            editor=self.grantee,
            granted_by=self.owner,
        )
        response = self._post(self.grantee, self.private_col, description="granted")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        grant.delete()
        response = self._post(self.grantee, self.private_col, description="revoked")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_published_cannot_be_edited_even_by_admin(self):
        response = self._post(
            self.admin,
            self.published_col,
            expected_publication_status="private",
            description="no",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_archived_cannot_be_edited(self):
        response = self._post(
            self.owner,
            self.archived_col,
            expected_publication_status="private",
            description="no",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_review_collection_edit_retains_review_state(self):
        response = self._post(self.owner, self.review_col, description="still review")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.review_col.refresh_from_db()
        self.assertEqual(self.review_col.publication_status, "review")
        self.assertEqual(self.review_col.description, "still review")

    def test_declined_collection_is_editable(self):
        response = self._post(
            self.owner, self.declined_col, description="declined edit"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.declined_col.refresh_from_db()
        self.assertEqual(self.declined_col.publication_status, "declined")


class CollectionUpdateGuardTests(CollectionUpdateFixture, APITestCase):
    def test_identity_mismatch_is_409_without_changes(self):
        payload = self._payload(
            self.private_col,
            expected_catchment="Wrong Catchment",
            description="mismatch",
        )
        payload.pop("expected_catchment_id", None)
        self.client.force_login(self.owner)
        response = self.client.post(self._url(self.private_col), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("mismatches", response.data)
        self.private_col.refresh_from_db()
        self.assertEqual(self.private_col.description, "original description")
        self.assertEqual(self._edited_events(self.private_col).count(), 0)

    def test_noop_update_is_200_without_revision_or_event(self):
        before = self.private_col.content_revision
        response = self._post(
            self.owner,
            self.private_col,
            description="original description",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.private_col.refresh_from_db()
        self.assertEqual(self.private_col.content_revision, before)
        self.assertEqual(self._edited_events(self.private_col).count(), 0)

    def test_compound_edit_single_audit_with_m2m_fields(self):
        before = self.private_col.content_revision
        response = self._post(
            self.owner,
            self.private_col,
            description="compound",
            allowed_materials=[self.public_material.pk],
            sources=[self.public_source.pk],
            flyer_urls=[self.public_flyer.url],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.private_col.refresh_from_db()
        self.assertEqual(self.private_col.content_revision, before + 1)
        events = self._edited_events(self.private_col)
        self.assertEqual(events.count(), 1)
        changed = set(events.first().changed_fields)
        self.assertIn("description", changed)
        self.assertIn("m2m.allowed_materials", changed)
        self.assertIn("m2m.sources", changed)
        self.assertIn("m2m.flyers", changed)
        self.assertEqual(
            list(self.private_col.allowed_materials.values_list("pk", flat=True)),
            [self.public_material.pk],
        )
        self.assertEqual(
            list(self.private_col.sources.values_list("pk", flat=True)),
            [self.public_source.pk],
        )
        self.assertEqual(
            list(self.private_col.flyers.values_list("pk", flat=True)),
            [self.public_flyer.pk],
        )

    def test_metadata_fields_cannot_be_overridden(self):
        before = self.private_col.content_revision
        pk_before = self.private_col.pk
        response = self._post(
            self.owner,
            self.private_col,
            description="meta",
            owner=self.stranger.pk,
            publication_status="published",
            content_revision=99,
            id=self.published_col.pk,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.private_col.refresh_from_db()
        self.assertEqual(self.private_col.owner_id, self.owner.pk)
        self.assertEqual(self.private_col.publication_status, "private")
        self.assertEqual(self.private_col.content_revision, before + 1)
        self.assertEqual(self.private_col.pk, pk_before)

    def test_unreadable_private_references_are_rejected_without_partial(self):
        cases = {
            "collector": {"collector": self.private_collector.pk},
            "frequency": {"frequency": self.private_frequency.pk},
            "fee_system": {"fee_system": self.private_fee.pk},
            "bin_configuration": {"bin_configuration": self.private_bin.pk},
            "allowed_materials": {"allowed_materials": [self.private_material.pk]},
            "forbidden_materials": {"forbidden_materials": [self.private_material.pk]},
            "sources": {"sources": [self.private_source.pk]},
        }
        for field_name, reference in cases.items():
            with self.subTest(reference=field_name):
                before_rev = self.private_col.content_revision
                response = self._post(
                    self.owner,
                    self.private_col,
                    description="tampered",
                    **reference,
                )
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
                self.private_col.refresh_from_db()
                self.assertEqual(self.private_col.description, "original description")
                self.assertEqual(self.private_col.content_revision, before_rev)
                self.assertEqual(self._edited_events(self.private_col).count(), 0)

    def test_hidden_flyer_url_is_denied(self):
        response = self._post(
            self.owner,
            self.private_col,
            flyer_urls=[self.hidden_flyer.url],
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.private_col.refresh_from_db()
        self.assertEqual(self.private_col.flyers.count(), 0)


class CollectionUpdateFlyerTests(CollectionUpdateFixture, APITestCase):
    def test_new_flyer_requires_add_capability(self):
        fresh = User.objects.get(pk=self.update_only.pk)
        self.assertFalse(fresh.has_perm("waste_collection.add_wasteflyer"))
        response = self._post(
            self.update_only,
            self.update_only_col,
            flyer_urls=["https://example.com/new"],
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_new_flyer_owned_by_actor_with_audit(self):
        response = self._post(
            self.owner,
            self.private_col,
            flyer_urls=["https://example.com/new"],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        flyer = WasteFlyer.objects.get(url="https://example.com/new")
        self.assertEqual(flyer.owner_id, self.owner.pk)
        self.assertEqual(flyer.publication_status, "private")
        flyer_ct = ContentType.objects.get_for_model(WasteFlyer)
        events = ReviewAction.objects.filter(
            content_type=flyer_ct,
            object_id=flyer.pk,
            action=ReviewAction.ACTION_CREATED,
        )
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.first().user_id, self.owner.pk)

    def test_grantee_flyer_is_owned_by_grantee_not_collection_owner(self):
        ct = ContentType.objects.get_for_model(Collection)
        ObjectEditorGrant.objects.create(
            content_type=ct,
            object_id=self.private_col.pk,
            editor=self.grantee,
            granted_by=self.owner,
        )
        response = self._post(
            self.grantee,
            self.private_col,
            flyer_urls=["https://example.com/grantee-flyer"],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        flyer = WasteFlyer.objects.get(url="https://example.com/grantee-flyer")
        self.assertEqual(flyer.owner_id, self.grantee.pk)
        flyer_ct = ContentType.objects.get_for_model(WasteFlyer)
        self.assertEqual(
            ReviewAction.objects.get(
                content_type=flyer_ct,
                object_id=flyer.pk,
                action=ReviewAction.ACTION_CREATED,
            ).user_id,
            self.grantee.pk,
        )
        self.private_col.refresh_from_db()
        self.assertEqual(self.private_col.owner_id, self.owner.pk)

    def test_existing_readable_flyer_reuse_without_add_capability(self):
        self.assertFalse(
            User.objects.get(pk=self.update_only.pk).has_perm(
                "waste_collection.add_wasteflyer"
            )
        )
        flyer_revision = self.public_flyer.content_revision
        response = self._post(
            self.update_only,
            self.update_only_col,
            flyer_urls=[self.public_flyer.url],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.update_only_col.refresh_from_db()
        self.assertIn(self.public_flyer, self.update_only_col.flyers.all())
        flyer_ct = ContentType.objects.get_for_model(WasteFlyer)
        self.assertEqual(
            ReviewAction.objects.filter(
                content_type=flyer_ct, object_id=self.public_flyer.pk
            ).count(),
            0,
        )
        self.public_flyer.refresh_from_db()
        self.assertEqual(self.public_flyer.content_revision, flyer_revision)


class CollectionUpdateRollbackTests(CollectionUpdateFixture, APITestCase):
    def test_audit_failure_rolls_back_all_writes_and_flyer(self):
        collection_ct = ContentType.objects.get_for_model(Collection)
        flyer_ct = ContentType.objects.get_for_model(WasteFlyer)
        original_revision = self.private_col.content_revision
        prior = ReviewAction.objects.create(
            content_type=collection_ct,
            object_id=self.private_col.pk,
            user=self.owner,
            action=ReviewAction.ACTION_SUBMITTED,
            comment="prior comment",
            content_revision=self.private_col.content_revision,
        )
        reached_writes = {}

        original = _record_event

        def fail_on_edit(obj, actor, action, **kwargs):
            if action == ReviewAction.ACTION_EDITED:
                reached_writes["description"] = Collection.objects.get(
                    pk=self.private_col.pk
                ).description
                reached_writes["materials"] = list(
                    Collection.objects.get(
                        pk=self.private_col.pk
                    ).allowed_materials.values_list("pk", flat=True)
                )
                reached_writes["sources"] = list(
                    obj.sources.values_list("pk", flat=True)
                )
                reached_writes["flyer_row"] = WasteFlyer.objects.filter(
                    url="https://example.com/rollback"
                ).exists()
                reached_writes["flyer_attached"] = Collection.objects.get(
                    pk=self.private_col.pk
                ).flyers.exists()
                reached_writes["flyer_audit"] = ReviewAction.objects.filter(
                    content_type=flyer_ct,
                    object_id=WasteFlyer.objects.get(
                        url="https://example.com/rollback"
                    ).pk,
                    action=ReviewAction.ACTION_CREATED,
                    user=self.owner,
                ).exists()
                raise RuntimeError("simulated audit failure")
            return original(obj, actor, action, **kwargs)

        with patch(
            "utils.object_management.services._record_event",
            side_effect=fail_on_edit,
        ):
            with self.assertLogs("django.request", level="ERROR") as logs:
                with self.assertRaises(RuntimeError):
                    self._post(
                        self.owner,
                        self.private_col,
                        description="must roll back",
                        allowed_materials=[self.public_material.pk],
                        sources=[self.public_source.pk],
                        flyer_urls=["https://example.com/rollback"],
                    )
        self.assertIn(self._url(self.private_col), logs.output[0])
        self.assertEqual(reached_writes["description"], "must roll back")
        self.assertEqual(reached_writes["materials"], [self.public_material.pk])
        self.assertEqual(reached_writes["sources"], [self.public_source.pk])
        self.assertTrue(reached_writes["flyer_row"])
        self.assertTrue(reached_writes["flyer_attached"])
        self.assertTrue(reached_writes["flyer_audit"])

        self.private_col.refresh_from_db()
        self.assertEqual(self.private_col.description, "original description")
        self.assertEqual(self.private_col.flyers.count(), 0)
        self.assertEqual(self.private_col.allowed_materials.count(), 0)
        self.assertEqual(self.private_col.sources.count(), 0)
        self.assertEqual(self.private_col.content_revision, original_revision)
        self.assertFalse(ReviewAction.objects.filter(content_type=flyer_ct).exists())
        self.assertFalse(
            WasteFlyer.objects.filter(url="https://example.com/rollback").exists()
        )
        self.assertTrue(
            ReviewAction.objects.filter(pk=prior.pk, comment="prior comment").exists()
        )
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type=collection_ct,
                object_id=self.private_col.pk,
                action=ReviewAction.ACTION_EDITED,
            ).exists()
        )


class ResolveFlyerTests(CollectionUpdateFixture, APITestCase):
    def test_missing_add_does_not_attempt_creation(self):
        with patch.object(
            WasteFlyer.objects,
            "get_or_create_by_url",
            wraps=WasteFlyer.objects.get_or_create_by_url,
        ) as resolve:
            with self.assertRaises(PermissionDenied):
                resolve_flyer(self.update_only, "https://example.com/denied")
        resolve.assert_not_called()

    def test_reuse_is_denied_for_deactivated_actor(self):
        User.objects.filter(pk=self.owner.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            resolve_flyer(self.owner, self.public_flyer.url)

    def test_creation_audit_failure_leaves_no_row(self):
        with patch(
            "sources.waste_collection.services.record_creation",
            side_effect=RuntimeError("audit failure"),
        ):
            with self.assertRaises(RuntimeError):
                resolve_flyer(self.owner, "https://example.com/orphan")
        self.assertFalse(
            WasteFlyer.objects.filter(url="https://example.com/orphan").exists()
        )

    def test_lost_race_private_flyer_is_denied(self):
        with patch.object(
            WasteFlyer.objects,
            "get_or_create_by_url",
            return_value=(self.hidden_flyer, False),
        ):
            with self.assertRaises(PermissionDenied):
                resolve_flyer(self.owner, "https://example.com/raced")
