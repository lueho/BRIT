"""Policy contract tests for the programmatic CPV/ACPV mutation endpoints.

These cover the public create-or-reuse API surface that delegates to
``sources.waste_collection.services``: actor locking, anchor resolution,
reference preflight, readable-record reuse, content_mutation-mediated
relation changes, lifecycle-gated submission, and generated-projection
isolation. The trusted workbook importer is not part of these endpoints.
"""

import threading
from datetime import date
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.db import connection, connections
from django.db.models.query import QuerySet
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from bibliography.models import Source
from sources.waste_collection import services
from sources.waste_collection.models import (
    AggregatedCollectionPropertyValue,
    Collection,
    CollectionCatchment,
    CollectionPropertyValue,
    CollectionSystem,
    WasteCategory,
    WasteFlyer,
)
from utils.object_management.models import (
    ObjectEditorGrant,
    ObjectGroupEditorGrant,
    ReviewAction,
)
from utils.object_management.policy import Decision
from utils.object_management.services import content_mutation
from utils.properties.models import Property, Unit

CPV_URL_NAME = "api-waste-collection-property-value-create"
ACPV_URL_NAME = "api-waste-collection-aggregated-property-value-create"


def _perm(model, codename):
    permission, _ = Permission.objects.get_or_create(
        codename=codename,
        content_type=ContentType.objects.get_for_model(model, for_concrete_model=False),
        defaults={"name": f"Can {codename.replace('_', ' ')}"},
    )
    return permission


def _grant(obj, editor):
    return ObjectEditorGrant.objects.create(
        content_type=ContentType.objects.get_for_model(obj.__class__),
        object_id=obj.pk,
        editor=editor,
        granted_by=obj.owner,
    )


class EvidenceMutationApiTests(APITestCase):
    """End-to-end contract tests for the CPV/ACPV create-or-reuse endpoints."""

    @classmethod
    def setUpTestData(cls):
        call_command("sync_roles", "--apply", stdout=StringIO())

        cls.owner = User.objects.create_user(username="evidence-owner")
        cls.registered = User.objects.create_user(username="evidence-registered")
        cls.registered.groups.add(Group.objects.get(name="registered"))
        cls.editor = User.objects.create_user(username="evidence-editor")
        cls.editor.groups.clear()
        cls.no_capability = User.objects.create_user(username="evidence-no-cap")
        # ``create_user`` auto-joins the provisioned ``registered`` group via
        # a post_save signal; negative-capability fixtures must leave it.
        cls.no_capability.groups.clear()
        cls.staff = User.objects.create_user(username="evidence-staff", is_staff=True)
        cls.staff.groups.clear()
        cls.inactive = User.objects.create_user(
            username="evidence-inactive", is_active=False
        )
        cls.stranger = User.objects.create_user(username="evidence-stranger")
        # Narrow intentional fixture: add capability only, no change.
        cls.adder = User.objects.create_user(username="evidence-adder")
        cls.adder.groups.clear()
        cls.adder.user_permissions.add(
            _perm(CollectionPropertyValue, "add_collectionpropertyvalue"),
            _perm(
                AggregatedCollectionPropertyValue,
                "add_aggregatedcollectionpropertyvalue",
            ),
        )

        cls.catchment = CollectionCatchment.objects.create(
            name="Evidence Catchment", publication_status="published"
        )
        cls.system = CollectionSystem.objects.create(
            name="Evidence System", publication_status="published"
        )
        cls.category = WasteCategory.objects.create(
            name="Evidence Category", publication_status="published"
        )
        cls.property = Property.objects.create(
            name="Evidence Property", publication_status="published"
        )
        cls.unit = Unit.objects.create(
            name="Evidence Unit", publication_status="published"
        )

        cls.published_collection = cls._collection("Evidence published", "published")
        cls.second_published = cls._collection("Evidence second published", "published")
        cls.private_own = cls._collection("Evidence own private", "private")
        cls.foreign_private = cls._collection(
            "Evidence foreign private", "private", owner=cls.stranger
        )
        cls.archived_anchor = cls._collection("Evidence archived anchor", "archived")
        cls.published_successor = cls._collection(
            "Evidence published successor", "published"
        )
        cls.published_successor.predecessors.add(cls.archived_anchor)
        cls.private_anchor = cls._collection("Evidence private anchor", "private")
        cls.successor_on_private_anchor = cls._collection(
            "Evidence successor private anchor", "published"
        )
        cls.successor_on_private_anchor.predecessors.add(cls.private_anchor)

        cls.published_source = Source.objects.create(
            owner=cls.stranger,
            title="Evidence public source",
            abbreviation="EvPubSrc",
            url="https://example.com/public-source",
            publication_status="published",
        )
        cls.private_foreign_source = Source.objects.create(
            owner=cls.stranger,
            title="Evidence foreign source",
            abbreviation="EvForeignSrc",
            url="https://example.com/private-source",
            publication_status="private",
        )
        cls.published_flyer = WasteFlyer.objects.create(
            owner=cls.stranger,
            title="Evidence public flyer",
            url="https://example.com/public-flyer",
            publication_status="published",
        )
        cls.private_foreign_flyer = WasteFlyer.objects.create(
            owner=cls.stranger,
            title="Evidence private flyer",
            url="https://example.com/private-flyer",
            publication_status="private",
        )

    @classmethod
    def _collection(cls, name, publication_status, owner=None):
        return Collection.objects.create(
            name=name,
            owner=owner or cls.owner,
            catchment=cls.catchment,
            collection_system=cls.system,
            waste_category=cls.category,
            valid_from=date(2020, 1, 1),
            publication_status=publication_status,
        )

    def _cpv_payload(self, collection=None, **overrides):
        payload = {
            "collection": (collection or self.published_collection).pk,
            "property_id": self.property.pk,
            "unit_name": self.unit.name,
            "year": 2024,
            "average": 12.5,
            "submit_for_review": False,
        }
        payload.update(overrides)
        return payload

    def _acpv_payload(self, collections=None, **overrides):
        payload = {
            "collections": [c.pk for c in (collections or [self.published_collection])],
            "property_id": self.property.pk,
            "unit_name": self.unit.name,
            "year": 2024,
            "average": 12.5,
            "submit_for_review": False,
        }
        payload.update(overrides)
        return payload

    def _post_cpv(self, payload=None):
        return self.client.post(
            reverse(CPV_URL_NAME), payload or self._cpv_payload(), format="json"
        )

    def _post_acpv(self, payload=None, **overrides):
        return self.client.post(
            reverse(ACPV_URL_NAME),
            payload or self._acpv_payload(**overrides),
            format="json",
        )

    @staticmethod
    def _events(obj, action=None):
        # Match ``_record_event``: events are keyed on the concrete content
        # type, which matters for proxy models such as WasteFlyer.
        qs = ReviewAction.objects.filter(
            content_type=ContentType.objects.get_for_model(obj.__class__),
            object_id=obj.pk,
        )
        if action is not None:
            qs = qs.filter(action=action)
        return qs

    # -- 1. Provisioned registered role, supported workflows ---------------

    def test_registered_role_creates_private_cpv(self):
        collection_revision = self.published_collection.content_revision
        self.client.force_login(self.registered)

        response = self._post_cpv()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["cpv_created"], 1)
        self.assertEqual(response.data["cpv_unchanged"], 0)
        self.assertFalse(response.data["is_derived"])
        cpv = CollectionPropertyValue.objects.get(pk=response.data["id"])
        self.assertEqual(cpv.owner, self.registered)
        self.assertEqual(cpv.collection, self.published_collection)
        self.assertEqual(cpv.publication_status, "private")
        self.assertFalse(cpv.is_derived)
        event = self._events(cpv, ReviewAction.ACTION_CREATED).get()
        self.assertEqual(event.user, self.registered)
        self.assertEqual(event.content_revision, cpv.content_revision)
        self.published_collection.refresh_from_db()
        self.assertEqual(
            self.published_collection.content_revision, collection_revision
        )
        self.assertFalse(self._events(self.published_collection).exists())

    def test_registered_role_creates_private_acpv(self):
        self.client.force_login(self.registered)

        response = self._post_acpv(
            collections=[self.published_collection, self.second_published]
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["created"])
        acpv = AggregatedCollectionPropertyValue.objects.get(pk=response.data["id"])
        self.assertEqual(acpv.owner, self.registered)
        self.assertEqual(acpv.publication_status, "private")
        self.assertEqual(
            sorted(acpv.collections.values_list("pk", flat=True)),
            sorted([self.published_collection.pk, self.second_published.pk]),
        )
        self.assertEqual(self._events(acpv, ReviewAction.ACTION_CREATED).count(), 1)

    def test_cpv_submission_when_requested(self):
        self.client.force_login(self.registered)

        response = self._post_cpv(self._cpv_payload(submit_for_review=True))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["submitted"])
        cpv = CollectionPropertyValue.objects.get(pk=response.data["id"])
        self.assertEqual(cpv.publication_status, "review")
        event = self._events(cpv, ReviewAction.ACTION_SUBMITTED).get()
        self.assertEqual(event.user, self.registered)
        self.assertEqual(event.content_revision, cpv.content_revision)

    # -- 2. Denials ---------------------------------------------------------

    def test_missing_add_capability_denied(self):
        self.client.force_login(self.no_capability)

        response = self._post_cpv()

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            CollectionPropertyValue.objects.filter(
                collection=self.published_collection
            ).exists()
        )

    def test_inactive_actor_denied(self):
        self.client.force_login(self.inactive)

        response = self._post_cpv()

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_staff_only_denied(self):
        self.client.force_login(self.staff)

        response = self._post_cpv()

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            CollectionPropertyValue.objects.filter(
                collection=self.published_collection
            ).exists()
        )

    def test_private_foreign_anchor_denied_via_readable_successor(self):
        self.client.force_login(self.registered)

        response = self._post_cpv(
            self._cpv_payload(collection=self.successor_on_private_anchor)
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            CollectionPropertyValue.objects.filter(
                collection__in=[
                    self.private_anchor,
                    self.successor_on_private_anchor,
                ]
            ).exists()
        )

    def test_acpv_mixed_parent_set_denies_all(self):
        self.client.force_login(self.registered)

        response = self._post_acpv(
            collections=[self.published_collection, self.foreign_private]
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            AggregatedCollectionPropertyValue.objects.filter(
                property=self.property
            ).exists()
        )

    # -- 3. Reuse semantics --------------------------------------------------

    def test_no_delta_reuse_without_change_permission(self):
        """Readable own record with no relation delta is returned as a pure
        read reuse even though the actor lacks ``change`` capability."""
        existing = CollectionPropertyValue.objects.create(
            name="Adder raw",
            owner=self.adder,
            publication_status="private",
            collection=self.published_collection,
            property=self.property,
            unit=self.unit,
            year=2024,
            average=42.0,
        )
        revision_before = existing.content_revision
        self.client.force_login(self.adder)

        response = self._post_cpv(self._cpv_payload(average=99.0))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["id"], existing.pk)
        self.assertEqual(response.data["cpv_unchanged"], 1)
        existing.refresh_from_db()
        self.assertEqual(existing.average, 42.0)
        self.assertEqual(existing.owner, self.adder)
        self.assertEqual(existing.content_revision, revision_before)
        self.assertFalse(self._events(existing, ReviewAction.ACTION_EDITED).exists())
        self.assertEqual(
            CollectionPropertyValue.objects.filter(
                collection=self.published_collection, year=2024
            ).count(),
            1,
        )

    def test_generated_row_is_never_reused(self):
        """A generated projection sharing the data key must not satisfy the
        raw dedup query; a new independent raw record is created instead."""
        raw_source = CollectionPropertyValue.objects.create(
            name="Raw source row",
            owner=self.owner,
            publication_status="published",
            collection=self.published_collection,
            property=self.property,
            unit=self.unit,
            year=2023,
            average=10.0,
        )
        generated = CollectionPropertyValue.objects.create(
            name="Generated row",
            owner=self.owner,
            publication_status="published",
            collection=self.published_collection,
            property=self.property,
            unit=self.unit,
            year=2024,
            average=5.0,
            is_derived=True,
            derived_from=raw_source,
        )
        self.client.force_login(self.registered)

        response = self._post_cpv()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["cpv_created"], 1)
        self.assertNotEqual(response.data["id"], generated.pk)
        self.assertFalse(response.data["is_derived"])
        generated.refresh_from_db()
        self.assertTrue(generated.is_derived)
        self.assertEqual(
            CollectionPropertyValue.objects.filter(
                collection=self.published_collection,
                property=self.property,
                unit=self.unit,
                year=2024,
                is_derived=False,
            ).count(),
            1,
        )

    def test_foreign_private_record_not_reused_or_disclosed(self):
        hidden = CollectionPropertyValue.objects.create(
            name="Hidden raw",
            owner=self.stranger,
            publication_status="private",
            collection=self.published_collection,
            property=self.property,
            unit=self.unit,
            year=2024,
            average=7.0,
        )
        self.client.force_login(self.registered)

        response = self._post_cpv()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["cpv_created"], 1)
        self.assertNotEqual(response.data["id"], hidden.pk)
        cpv = CollectionPropertyValue.objects.get(pk=response.data["id"])
        self.assertEqual(cpv.owner, self.registered)
        hidden.refresh_from_db()
        self.assertFalse(self._events(hidden, ReviewAction.ACTION_EDITED).exists())

    def test_readable_public_record_reused_without_mutation(self):
        existing = CollectionPropertyValue.objects.create(
            name="Public raw",
            owner=self.stranger,
            publication_status="published",
            collection=self.published_collection,
            property=self.property,
            unit=self.unit,
            year=2024,
            average=7.0,
        )
        revision_before = existing.content_revision
        self.client.force_login(self.registered)

        response = self._post_cpv()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["id"], existing.pk)
        self.assertEqual(response.data["cpv_unchanged"], 1)
        existing.refresh_from_db()
        self.assertEqual(existing.owner, self.stranger)
        self.assertEqual(existing.average, 7.0)
        self.assertEqual(existing.content_revision, revision_before)
        self.assertFalse(self._events(existing).exists())

    # -- 4. Relation deltas through content_mutation ------------------------

    def test_relation_add_on_editable_record_revises_once(self):
        existing = CollectionPropertyValue.objects.create(
            name="Own review raw",
            owner=self.registered,
            publication_status="review",
            collection=self.published_collection,
            property=self.property,
            unit=self.unit,
            year=2024,
            average=7.0,
        )
        revision_before = existing.content_revision
        self.client.force_login(self.registered)

        response = self._post_cpv(self._cpv_payload(sources=[self.published_source.pk]))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        existing.refresh_from_db()
        self.assertEqual(existing.owner, self.registered)
        self.assertEqual(existing.publication_status, "review")
        self.assertEqual(existing.content_revision, revision_before + 1)
        self.assertEqual(self._events(existing, ReviewAction.ACTION_EDITED).count(), 1)
        self.assertTrue(existing.sources.filter(pk=self.published_source.pk).exists())

    def test_relation_add_on_shared_record_via_grant(self):
        existing = CollectionPropertyValue.objects.create(
            name="Shared private raw",
            owner=self.stranger,
            publication_status="private",
            collection=self.published_collection,
            property=self.property,
            unit=self.unit,
            year=2024,
            average=7.0,
        )
        _grant(existing, self.editor)
        self.editor.user_permissions.add(
            _perm(CollectionPropertyValue, "add_collectionpropertyvalue"),
            _perm(CollectionPropertyValue, "change_collectionpropertyvalue"),
        )
        revision_before = existing.content_revision
        self.client.force_login(self.editor)

        response = self._post_cpv(self._cpv_payload(sources=[self.published_source.pk]))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        existing.refresh_from_db()
        self.assertEqual(existing.owner, self.stranger)
        self.assertEqual(existing.content_revision, revision_before + 1)
        self.assertTrue(existing.sources.filter(pk=self.published_source.pk).exists())

    def test_relation_add_denied_without_access_despite_change_perm(self):
        """Model change capability alone cannot mutate a foreign private or
        published record reached by read reuse."""
        existing = CollectionPropertyValue.objects.create(
            name="Foreign published raw",
            owner=self.stranger,
            publication_status="published",
            collection=self.published_collection,
            property=self.property,
            unit=self.unit,
            year=2024,
            average=7.0,
        )
        self.registered.user_permissions.add(
            _perm(CollectionPropertyValue, "change_collectionpropertyvalue")
        )
        revision_before = existing.content_revision
        self.client.force_login(self.registered)

        response = self._post_cpv(self._cpv_payload(sources=[self.published_source.pk]))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        existing.refresh_from_db()
        self.assertEqual(existing.content_revision, revision_before)
        self.assertFalse(existing.sources.filter(pk=self.published_source.pk).exists())
        self.assertFalse(self._events(existing).exists())

    def test_frozen_record_rejects_relation_delta_even_for_admin(self):
        existing = CollectionPropertyValue.objects.create(
            name="Frozen raw",
            owner=self.stranger,
            publication_status="published",
            collection=self.published_collection,
            property=self.property,
            unit=self.unit,
            year=2024,
            average=7.0,
        )
        admin = User.objects.create_superuser(username="evidence-admin")
        revision_before = existing.content_revision
        self.client.force_login(admin)

        response = self._post_cpv(self._cpv_payload(sources=[self.published_source.pk]))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        existing.refresh_from_db()
        self.assertEqual(existing.content_revision, revision_before)
        self.assertFalse(existing.sources.filter(pk=self.published_source.pk).exists())

    def test_frozen_record_accepts_already_linked_relations(self):
        """Idempotent reuse on a frozen record never opens a write boundary."""
        existing = CollectionPropertyValue.objects.create(
            name="Frozen linked raw",
            owner=self.stranger,
            publication_status="published",
            collection=self.published_collection,
            property=self.property,
            unit=self.unit,
            year=2024,
            average=7.0,
        )
        existing.sources.add(self.published_source)
        admin = User.objects.create_superuser(username="evidence-admin2")
        revision_before = existing.content_revision
        self.client.force_login(admin)

        response = self._post_cpv(self._cpv_payload(sources=[self.published_source.pk]))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["id"], existing.pk)
        existing.refresh_from_db()
        self.assertEqual(existing.content_revision, revision_before)
        self.assertFalse(self._events(existing).exists())

    # -- 5. References -------------------------------------------------------

    def test_new_flyer_requires_add_capability(self):
        adder_only = User.objects.create_user(username="evidence-adder-only")
        adder_only.groups.clear()
        adder_only.user_permissions.add(
            _perm(CollectionPropertyValue, "add_collectionpropertyvalue")
        )
        url = "https://example.com/brand-new-flyer"
        self.client.force_login(adder_only)

        response = self._post_cpv(self._cpv_payload(flyer_urls=[url]))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(WasteFlyer.objects.filter(url=url).exists())
        self.assertFalse(
            CollectionPropertyValue.objects.filter(
                collection=self.published_collection
            ).exists()
        )

    def test_new_flyer_created_and_audited(self):
        url = "https://example.com/registered-flyer"
        self.client.force_login(self.registered)

        response = self._post_cpv(self._cpv_payload(flyer_urls=[url]))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["flyers_created"], 1)
        flyer = WasteFlyer.objects.get(url=url)
        self.assertEqual(flyer.owner, self.registered)
        self.assertEqual(flyer.publication_status, "private")
        self.assertEqual(self._events(flyer, ReviewAction.ACTION_CREATED).count(), 1)
        cpv = CollectionPropertyValue.objects.get(pk=response.data["id"])
        self.assertTrue(cpv.sources.filter(pk=flyer.pk).exists())

    def test_existing_accessible_flyer_usable_without_add(self):
        adder_only = User.objects.create_user(username="evidence-adder-only2")
        adder_only.groups.clear()
        adder_only.user_permissions.add(
            _perm(CollectionPropertyValue, "add_collectionpropertyvalue")
        )
        self.client.force_login(adder_only)

        response = self._post_cpv(
            self._cpv_payload(flyer_urls=[self.published_flyer.url])
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["flyers_created"], 0)
        cpv = CollectionPropertyValue.objects.get(pk=response.data["id"])
        self.assertTrue(cpv.sources.filter(pk=self.published_flyer.pk).exists())

    def test_private_foreign_flyer_denied(self):
        self.client.force_login(self.registered)

        response = self._post_cpv(
            self._cpv_payload(flyer_urls=[self.private_foreign_flyer.url])
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            CollectionPropertyValue.objects.filter(
                collection=self.published_collection
            ).exists()
        )

    def test_private_foreign_source_denied(self):
        self.client.force_login(self.registered)

        response = self._post_cpv(
            self._cpv_payload(sources=[self.private_foreign_source.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            CollectionPropertyValue.objects.filter(
                collection=self.published_collection
            ).exists()
        )

    # -- 6. Submission semantics ---------------------------------------------

    def test_reused_private_record_submit_by_owner(self):
        existing = CollectionPropertyValue.objects.create(
            name="Own private raw",
            owner=self.registered,
            publication_status="private",
            collection=self.published_collection,
            property=self.property,
            unit=self.unit,
            year=2024,
            average=7.0,
        )
        self.client.force_login(self.registered)

        response = self._post_cpv(self._cpv_payload(submit_for_review=True))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["submitted"])
        existing.refresh_from_db()
        self.assertEqual(existing.publication_status, "review")
        event = self._events(existing, ReviewAction.ACTION_SUBMITTED).get()
        self.assertEqual(event.user, self.registered)
        self.assertEqual(event.content_revision, existing.content_revision)

        # Repeating on the review record emits no second submission event.
        response = self._post_cpv(self._cpv_payload(submit_for_review=True))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data["submitted"])
        self.assertEqual(
            self._events(existing, ReviewAction.ACTION_SUBMITTED).count(), 1
        )

    def test_editor_cannot_submit_foreign_private_draft(self):
        existing = CollectionPropertyValue.objects.create(
            name="Foreign shared draft",
            owner=self.stranger,
            publication_status="private",
            collection=self.published_collection,
            property=self.property,
            unit=self.unit,
            year=2024,
            average=7.0,
        )
        _grant(existing, self.editor)
        self.editor.user_permissions.add(
            _perm(CollectionPropertyValue, "add_collectionpropertyvalue")
        )
        self.client.force_login(self.editor)

        response = self._post_cpv(self._cpv_payload(submit_for_review=True))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        existing.refresh_from_db()
        self.assertEqual(existing.publication_status, "private")
        self.assertFalse(self._events(existing, ReviewAction.ACTION_SUBMITTED).exists())

    # -- 7. Actor lock / concurrency contract --------------------------------

    def test_cpv_locks_actor_row_before_candidate_lookup(self):
        self.client.force_login(self.registered)
        cpv_table = CollectionPropertyValue._meta.db_table
        user_table = User._meta.db_table

        with CaptureQueriesContext(connection) as captured:
            response = self._post_cpv()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        sqls = [query["sql"] for query in captured.captured_queries]
        lock_index = next(
            (
                index
                for index, sql in enumerate(sqls)
                if f'FROM "{user_table}"' in sql and "FOR NO KEY UPDATE" in sql
            ),
            None,
        )
        lookup_index = next(
            (
                index
                for index, sql in enumerate(sqls)
                if sql.startswith("SELECT") and f'FROM "{cpv_table}"' in sql
            ),
            None,
        )
        self.assertIsNotNone(lock_index)
        self.assertIsNotNone(lookup_index)
        self.assertLess(lock_index, lookup_index)

    def test_acpv_locks_actor_row_before_candidate_lookup(self):
        self.client.force_login(self.registered)
        acpv_table = AggregatedCollectionPropertyValue._meta.db_table
        user_table = User._meta.db_table

        with CaptureQueriesContext(connection) as captured:
            response = self._post_acpv()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        sqls = [query["sql"] for query in captured.captured_queries]
        lock_index = next(
            (
                index
                for index, sql in enumerate(sqls)
                if f'FROM "{user_table}"' in sql and "FOR NO KEY UPDATE" in sql
            ),
            None,
        )
        lookup_index = next(
            (
                index
                for index, sql in enumerate(sqls)
                if sql.startswith("SELECT") and f'FROM "{acpv_table}"' in sql
            ),
            None,
        )
        self.assertIsNotNone(lock_index)
        self.assertIsNotNone(lookup_index)
        self.assertLess(lock_index, lookup_index)

    # -- 8. Audit-failure rollback ---------------------------------------------

    def test_audit_failure_rolls_back_create(self):
        url = "https://example.com/rolled-back-flyer"
        self.client.force_login(self.registered)

        with (
            self.assertLogs("django.request", level="ERROR"),
            self.assertRaises(RuntimeError),
            patch.object(
                ReviewAction.objects,
                "create",
                side_effect=RuntimeError("audit insertion failure"),
            ),
        ):
            self._post_cpv(
                self._cpv_payload(sources=[self.published_source.pk], flyer_urls=[url])
            )

        self.assertFalse(
            CollectionPropertyValue.objects.filter(
                collection=self.published_collection
            ).exists()
        )
        self.assertFalse(WasteFlyer.objects.filter(url=url).exists())

    def test_audit_failure_rolls_back_reuse_relation_delta(self):
        """An audit insertion failure on the edit path undoes the relation
        delta, the revision bump, and any newly created flyer."""
        existing = CollectionPropertyValue.objects.create(
            name="Reuse audit raw",
            owner=self.registered,
            publication_status="private",
            collection=self.published_collection,
            property=self.property,
            unit=self.unit,
            year=2024,
            average=7.0,
        )
        revision_before = existing.content_revision
        url = "https://example.com/rolled-back-reuse-flyer"
        self.client.force_login(self.registered)

        with (
            self.assertLogs("django.request", level="ERROR"),
            self.assertRaises(RuntimeError),
            patch.object(
                ReviewAction.objects,
                "create",
                side_effect=RuntimeError("audit insertion failure"),
            ),
        ):
            self._post_cpv(
                self._cpv_payload(sources=[self.published_source.pk], flyer_urls=[url])
            )

        existing.refresh_from_db()
        self.assertEqual(existing.content_revision, revision_before)
        self.assertFalse(existing.sources.filter(pk=self.published_source.pk).exists())
        self.assertFalse(WasteFlyer.objects.filter(url=url).exists())
        self.assertFalse(self._events(existing).exists())

    def test_generated_artifact_not_deleted_by_raw_creation(self):
        """A linked generated row survives a raw create on the same key —
        the API never touches derived records."""
        raw_source = CollectionPropertyValue.objects.create(
            name="Generator source",
            owner=self.owner,
            publication_status="published",
            collection=self.published_collection,
            property=self.property,
            unit=self.unit,
            year=2023,
            average=10.0,
        )
        generated = CollectionPropertyValue.objects.create(
            name="Linked generated",
            owner=self.owner,
            publication_status="published",
            collection=self.published_collection,
            property=self.property,
            unit=self.unit,
            year=2024,
            average=5.0,
            is_derived=True,
            derived_from=raw_source,
        )
        self.client.force_login(self.registered)

        response = self._post_cpv()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        generated.refresh_from_db()
        self.assertTrue(generated.is_derived)
        self.assertEqual(generated.derived_from_id, raw_source.pk)

    # -- 9. Reference resolution ----------------------------------------------

    def test_private_property_rejected(self):
        private_property = Property.objects.create(
            name="Evidence private property",
            owner=self.stranger,
            publication_status="private",
        )
        self.client.force_login(self.registered)

        response = self._post_cpv(self._cpv_payload(property_id=private_property.pk))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_property_id_returns_400(self):
        self.client.force_login(self.registered)

        response = self._post_cpv(self._cpv_payload(property_id=999999))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("property_id", response.data)

    def test_unknown_unit_returns_400(self):
        self.client.force_login(self.registered)

        response = self._post_cpv(self._cpv_payload(unit_name="Nonexistent"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("unit_name", response.data)

    def test_private_shadow_unit_does_not_hide_accessible_unit(self):
        Unit.objects.create(
            name=self.unit.name,
            owner=self.stranger,
            publication_status="private",
        )
        self.client.force_login(self.registered)

        response = self._post_cpv()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cpv = CollectionPropertyValue.objects.get(pk=response.data["id"])
        self.assertEqual(cpv.unit_id, self.unit.pk)

    def test_ambiguous_accessible_units_return_400(self):
        Unit.objects.create(
            name=self.unit.name,
            owner=self.stranger,
            publication_status="published",
        )
        self.client.force_login(self.registered)

        response = self._post_cpv()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("unit_name", response.data)

    # -- 10. Protected fields --------------------------------------------------

    def test_protected_payload_fields_cannot_forge_generated_row(self):
        self.client.force_login(self.registered)

        response = self._post_cpv(
            self._cpv_payload(
                is_derived=True,
                derived_from=9999,
                owner=self.stranger.pk,
                publication_status="published",
                content_revision=99,
            )
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cpv = CollectionPropertyValue.objects.get(pk=response.data["id"])
        self.assertFalse(cpv.is_derived)
        self.assertIsNone(cpv.derived_from_id)
        self.assertEqual(cpv.owner, self.registered)
        self.assertEqual(cpv.publication_status, "private")

    # -- 11. Group-grant collaboration -----------------------------------------

    def test_relation_add_via_group_editor_grant(self):
        """A group-level editor grant admits relation edits like a direct grant."""
        sharing_group = Group.objects.create(name="evidence-sharing")
        sharing_group.user_set.add(self.editor)
        existing = CollectionPropertyValue.objects.create(
            name="Group-shared raw",
            owner=self.stranger,
            publication_status="private",
            collection=self.published_collection,
            property=self.property,
            unit=self.unit,
            year=2024,
            average=7.0,
        )
        ObjectGroupEditorGrant.objects.create(
            content_type=ContentType.objects.get_for_model(CollectionPropertyValue),
            object_id=existing.pk,
            group=sharing_group,
            granted_by=self.stranger,
        )
        self.editor.user_permissions.add(
            _perm(CollectionPropertyValue, "add_collectionpropertyvalue"),
            _perm(CollectionPropertyValue, "change_collectionpropertyvalue"),
        )
        revision_before = existing.content_revision
        self.client.force_login(self.editor)

        response = self._post_cpv(self._cpv_payload(sources=[self.published_source.pk]))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        existing.refresh_from_db()
        self.assertEqual(existing.owner, self.stranger)
        self.assertEqual(existing.content_revision, revision_before + 1)
        self.assertTrue(existing.sources.filter(pk=self.published_source.pk).exists())

    # -- 12. Lock-seam stale reads ----------------------------------------------

    def _mutate_before_collection_lock(self, mutation):
        """Patch the Collection row-lock seam so ``mutation`` runs after the
        membership read but before the locked rows are reloaded."""
        real_select_for_update = Collection.objects.select_for_update

        def mutate_then_lock(*args, **kwargs):
            mutation()
            return real_select_for_update(*args, **kwargs)

        return patch.object(
            Collection.objects,
            "select_for_update",
            side_effect=mutate_then_lock,
        )

    def test_target_removed_before_lock_denies(self):
        self.client.force_login(self.registered)
        with self._mutate_before_collection_lock(
            lambda: Collection.objects.filter(pk=self.published_collection.pk).delete()
        ):
            response = self._post_cpv()

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            CollectionPropertyValue.objects.filter(property=self.property).exists()
        )

    def test_target_turned_private_foreign_before_lock_denies(self):
        self.client.force_login(self.registered)
        with self._mutate_before_collection_lock(
            lambda: Collection.objects.filter(pk=self.published_collection.pk).update(
                owner=self.stranger, publication_status="private"
            )
        ):
            response = self._post_cpv()

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            CollectionPropertyValue.objects.filter(property=self.property).exists()
        )

    def test_reparented_anchor_before_lock_denies(self):
        self.client.force_login(self.registered)

        def reparent():
            # ``version_anchor`` is derived from the predecessors M2M, so a
            # new predecessor changes the resolved anchor under the lock.
            Collection.objects.get(pk=self.published_collection.pk).predecessors.add(
                self.archived_anchor
            )

        with self._mutate_before_collection_lock(reparent):
            response = self._post_cpv()

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            CollectionPropertyValue.objects.filter(property=self.property).exists()
        )

    # -- 13. Flyer preflight ------------------------------------------------------

    def test_unauthorized_new_flyer_never_reaches_lookup(self):
        adder_only = User.objects.create_user(username="evidence-adder-only3")
        adder_only.groups.clear()
        adder_only.user_permissions.add(
            _perm(CollectionPropertyValue, "add_collectionpropertyvalue")
        )
        url = "https://example.com/unauthorized-flyer"
        self.client.force_login(adder_only)

        with patch.object(WasteFlyer.objects, "get_or_create_by_url") as mocked_lookup:
            response = self._post_cpv(self._cpv_payload(flyer_urls=[url]))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        mocked_lookup.assert_not_called()
        self.assertFalse(WasteFlyer.objects.filter(url=url).exists())
        self.assertFalse(
            CollectionPropertyValue.objects.filter(
                collection=self.published_collection
            ).exists()
        )

    def test_race_returning_unreadable_flyer_denies(self):
        """A URL empty at preflight that resolves to an unreadable row at
        resolution time still denies inside the transaction."""
        url = "https://example.com/race-unreadable-flyer"
        self.client.force_login(self.registered)

        with patch.object(
            WasteFlyer.objects,
            "get_or_create_by_url",
            return_value=(self.private_foreign_flyer, False),
        ):
            response = self._post_cpv(self._cpv_payload(flyer_urls=[url]))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            CollectionPropertyValue.objects.filter(
                collection=self.published_collection
            ).exists()
        )

    # -- 14. ACPV-specific coverage ------------------------------------------------

    def _existing_acpv(
        self,
        *,
        owner=None,
        publication_status="private",
        collections=None,
        year=2024,
    ):
        acpv = AggregatedCollectionPropertyValue.objects.create(
            name="Existing aggregated",
            owner=owner or self.registered,
            publication_status=publication_status,
            property=self.property,
            unit=self.unit,
            year=year,
            average=7.0,
        )
        acpv.collections.set(collections or [self.published_collection])
        return acpv

    def test_acpv_duplicate_parent_inputs_return_canonical_set(self):
        self.client.force_login(self.registered)

        response = self._post_acpv(
            collections=[
                self.published_collection,
                self.second_published,
                self.published_collection,
            ]
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data["collection_ids"],
            sorted([self.published_collection.pk, self.second_published.pk]),
        )
        acpv = AggregatedCollectionPropertyValue.objects.get(pk=response.data["id"])
        self.assertEqual(
            sorted(acpv.collections.values_list("pk", flat=True)),
            sorted([self.published_collection.pk, self.second_published.pk]),
        )
        self.assertEqual(
            AggregatedCollectionPropertyValue.objects.filter(
                property=self.property
            ).count(),
            1,
        )

    def test_acpv_relation_delta_revises_once_preserving_comments(self):
        existing = self._existing_acpv(publication_status="review")
        ReviewAction.objects.create(
            content_type=ContentType.objects.get_for_model(
                AggregatedCollectionPropertyValue
            ),
            object_id=existing.pk,
            user=self.stranger,
            action=ReviewAction.ACTION_COMMENT,
            comment="prior review feedback",
            content_revision=existing.content_revision,
            changed_fields=[],
        )
        revision_before = existing.content_revision
        self.client.force_login(self.registered)

        response = self._post_acpv(
            self._acpv_payload(sources=[self.published_source.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        existing.refresh_from_db()
        self.assertEqual(existing.owner, self.registered)
        self.assertEqual(existing.publication_status, "review")
        self.assertEqual(existing.average, 7.0)
        self.assertEqual(existing.content_revision, revision_before + 1)
        self.assertEqual(self._events(existing, ReviewAction.ACTION_EDITED).count(), 1)
        self.assertEqual(self._events(existing, ReviewAction.ACTION_COMMENT).count(), 1)
        self.assertTrue(existing.sources.filter(pk=self.published_source.pk).exists())

    def test_acpv_frozen_records_deny_relation_delta_even_for_admin(self):
        admin = User.objects.create_superuser(username="evidence-acpv-admin")
        self.client.force_login(admin)
        real_content_mutation = services.content_mutation
        for frozen_status, year in (("published", 2024), ("archived", 2025)):
            # The ACPV dedup is owner-scoped; the frozen record must belong
            # to the acting admin and match the payload key so the reuse
            # delta path is exercised against this exact fixture.
            existing = self._existing_acpv(
                owner=admin, publication_status=frozen_status, year=year
            )
            revision_before = existing.content_revision
            url = f"https://example.com/frozen-flyer-{frozen_status}"
            mutated_targets = []

            def spy_content_mutation(actor, target, _seen=mutated_targets, **kwargs):
                _seen.append(target.pk)
                return real_content_mutation(actor, target, **kwargs)

            with (
                self.subTest(frozen_status=frozen_status),
                patch.object(services, "content_mutation", spy_content_mutation),
            ):
                response = self._post_acpv(
                    self._acpv_payload(
                        year=year,
                        sources=[self.published_source.pk],
                        flyer_urls=[url],
                    )
                )
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
                self.assertEqual(mutated_targets, [existing.pk])
                existing.refresh_from_db()
                self.assertEqual(existing.content_revision, revision_before)
                self.assertFalse(
                    existing.sources.filter(pk=self.published_source.pk).exists()
                )
                self.assertFalse(WasteFlyer.objects.filter(url=url).exists())
                self.assertFalse(self._events(existing).exists())

    def test_acpv_candidate_deleted_before_freeze_creates_new(self):
        """A candidate that vanishes between prefetch discovery and the
        row lock is skipped instead of raising — a fresh record is created."""
        existing = self._existing_acpv()
        real_select_for_update = (
            AggregatedCollectionPropertyValue.objects.select_for_update
        )

        def delete_then_lock(*args, **kwargs):
            AggregatedCollectionPropertyValue.objects.filter(pk=existing.pk).delete()
            return real_select_for_update(*args, **kwargs)

        self.client.force_login(self.registered)
        with patch.object(
            AggregatedCollectionPropertyValue.objects,
            "select_for_update",
            side_effect=delete_then_lock,
        ):
            response = self._post_acpv()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["created"])
        self.assertNotEqual(response.data["id"], existing.pk)
        self.assertFalse(
            AggregatedCollectionPropertyValue.objects.filter(pk=existing.pk).exists()
        )
        self.assertEqual(
            AggregatedCollectionPropertyValue.objects.filter(
                property=self.property
            ).count(),
            1,
        )

    def test_acpv_unreadable_candidate_no_op_fails_closed(self):
        """When the read recheck on the locked reuse candidate denies, the
        endpoint must fail closed instead of returning a readable-looking
        no-op for an ineligible record."""
        existing = self._existing_acpv()
        real_decide = services.decide

        def deny_read_on_existing(actor, action, target, **kwargs):
            if (
                action == "read"
                and isinstance(target, AggregatedCollectionPropertyValue)
                and getattr(target, "pk", None) == existing.pk
            ):
                return Decision(False, "invalid_state")
            return real_decide(actor, action, target, **kwargs)

        self.client.force_login(self.registered)
        with patch.object(services, "decide", deny_read_on_existing):
            response = self._post_acpv()

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(self._events(existing).exists())

    def test_acpv_no_delta_reuse_without_change_permission(self):
        existing = self._existing_acpv(owner=self.adder)
        revision_before = existing.content_revision
        self.client.force_login(self.adder)

        response = self._post_acpv(self._acpv_payload(average=99.0))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["id"], existing.pk)
        self.assertTrue(response.data["skipped"])
        existing.refresh_from_db()
        self.assertEqual(existing.average, 7.0)
        self.assertEqual(existing.content_revision, revision_before)
        self.assertFalse(self._events(existing).exists())

    def test_acpv_audit_failure_rolls_back_reuse_delta(self):
        existing = self._existing_acpv()
        revision_before = existing.content_revision
        url = "https://example.com/acpv-rolled-back-flyer"
        self.client.force_login(self.registered)

        with (
            self.assertLogs("django.request", level="ERROR"),
            self.assertRaises(RuntimeError),
            patch.object(
                ReviewAction.objects,
                "create",
                side_effect=RuntimeError("audit insertion failure"),
            ),
        ):
            self._post_acpv(
                self._acpv_payload(sources=[self.published_source.pk], flyer_urls=[url])
            )

        existing.refresh_from_db()
        self.assertEqual(existing.content_revision, revision_before)
        self.assertFalse(existing.sources.filter(pk=self.published_source.pk).exists())
        self.assertFalse(WasteFlyer.objects.filter(url=url).exists())
        self.assertFalse(self._events(existing).exists())

    def test_acpv_submission_idempotent(self):
        existing = self._existing_acpv()
        self.client.force_login(self.registered)

        response = self._post_acpv(self._acpv_payload(submit_for_review=True))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["submitted"])
        existing.refresh_from_db()
        self.assertEqual(existing.publication_status, "review")

        response = self._post_acpv(self._acpv_payload(submit_for_review=True))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data["submitted"])
        self.assertEqual(
            self._events(existing, ReviewAction.ACTION_SUBMITTED).count(), 1
        )


class EvidenceMutationConcurrencyTests(TransactionTestCase):
    """Real-connection concurrency contract for the API actor lock.

    The API locks the actor row with ``FOR NO KEY UPDATE`` so a concurrent
    ``content_mutation`` holding the evidence row can still insert an
    audit row that references the same user (FK key-share) and commit —
    a plain ``FOR UPDATE`` user lock deadlocks against that ordering.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="evidence-race")
        self.user.groups.clear()
        self.user.user_permissions.add(
            _perm(CollectionPropertyValue, "add_collectionpropertyvalue"),
            _perm(CollectionPropertyValue, "change_collectionpropertyvalue"),
        )
        catchment = CollectionCatchment.objects.create(
            name="Race Catchment", publication_status="published"
        )
        system = CollectionSystem.objects.create(
            name="Race System", publication_status="published"
        )
        category = WasteCategory.objects.create(
            name="Race Category", publication_status="published"
        )
        self.property = Property.objects.create(
            name="Race Property", publication_status="published"
        )
        self.unit = Unit.objects.create(
            name="Race Unit", publication_status="published"
        )
        self.collection = Collection.objects.create(
            name="Race collection",
            owner=self.user,
            catchment=catchment,
            collection_system=system,
            waste_category=category,
            valid_from=date(2020, 1, 1),
            publication_status="published",
        )
        self.cpv = CollectionPropertyValue.objects.create(
            name="Race raw",
            owner=self.user,
            publication_status="private",
            collection=self.collection,
            property=self.property,
            unit=self.unit,
            year=2024,
            average=42.0,
        )

    def tearDown(self):
        connections.close_all()
        super().tearDown()

    def test_api_reuse_does_not_deadlock_with_concurrent_audit(self):
        """A holds the CPV row inside ``content_mutation`` and must finish
        its audit insert while B's API call already holds the NO KEY actor
        and parent locks and waits on the CPV row itself."""
        a_holds_cpv = threading.Event()
        b_holds_user_lock = threading.Event()
        b_upstream_locks_ready = threading.Event()
        errors = []

        def mutate_first():
            try:
                with content_mutation(self.user, self.cpv, action="edit") as locked:
                    locked.average = 99.0
                    locked.save()
                    a_holds_cpv.set()
                    if not b_upstream_locks_ready.wait(timeout=30):
                        raise RuntimeError("timed out waiting for the API dedup lock")
            except Exception as exc:  # surfaced to the main thread
                errors.append(exc)
            finally:
                connections.close_all()

        holder = threading.Thread(target=mutate_first, daemon=True)
        revision_before = self.cpv.content_revision
        holder.start()
        self.assertTrue(a_holds_cpv.wait(timeout=30))

        original_locked_actor = services._locked_actor

        def instrumented_locked_actor(actor):
            fresh = original_locked_actor(actor)
            b_holds_user_lock.set()
            return fresh

        real_first = QuerySet.first

        def signal_dedup_ready(queryset):
            # Fires in the named API thread right before the CPV dedup
            # SELECT executes — at that point B already holds the actor and
            # parent row locks and will block on A's CPV row lock.
            if (
                queryset.model is CollectionPropertyValue
                and threading.current_thread().name == "evidence-api-caller"
            ):
                b_upstream_locks_ready.set()
            return real_first(queryset)

        result = {}

        def call_api():
            try:
                client = APIClient()
                client.force_login(self.user)
                result["response"] = client.post(
                    reverse(CPV_URL_NAME),
                    {
                        "collection": self.collection.pk,
                        "property_id": self.property.pk,
                        "unit_name": self.unit.name,
                        "year": 2024,
                        "average": 12.5,
                        "submit_for_review": False,
                    },
                    format="json",
                )
            except Exception as exc:  # surfaced to the main thread
                errors.append(exc)
            finally:
                connections.close_all()

        with (
            patch.object(services, "_locked_actor", instrumented_locked_actor),
            patch.object(QuerySet, "first", signal_dedup_ready),
        ):
            caller = threading.Thread(
                target=call_api, name="evidence-api-caller", daemon=True
            )
            caller.start()
            caller.join(timeout=60)
        holder.join(timeout=60)

        self.assertTrue(b_holds_user_lock.is_set())
        self.assertTrue(b_upstream_locks_ready.is_set())
        self.assertFalse(caller.is_alive(), "API thread did not finish")
        self.assertFalse(holder.is_alive(), "mutation thread did not finish")
        self.assertEqual(errors, [])
        response = result["response"]
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["id"], self.cpv.pk)
        self.assertEqual(response.data["cpv_unchanged"], 1)
        self.cpv.refresh_from_db()
        self.assertEqual(self.cpv.average, 99.0)
        self.assertEqual(self.cpv.content_revision, revision_before + 1)
        ct = ContentType.objects.get_for_model(CollectionPropertyValue)
        self.assertEqual(
            ReviewAction.objects.filter(
                content_type=ct,
                object_id=self.cpv.pk,
                action=ReviewAction.ACTION_EDITED,
            ).count(),
            1,
        )
        self.assertEqual(
            CollectionPropertyValue.objects.filter(collection=self.collection).count(),
            1,
        )
