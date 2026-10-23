"""Governed programmatic collection creation authorization.

The custom collection create, new-version, frequency-create and bulk-import
routes must delegate to the shared policy instead of staff shortcuts:
creation requires the model ``add`` capability, every referenced record
requires independent read access, new roots get a creation audit, and
submissions flow through the revision-bound transition service. ``is_staff``
grants none of this.
"""

from io import StringIO

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from distributions.utils import ensure_initial_data as ensure_distribution_data
from sources.waste_collection.models import (
    Collection,
    CollectionCatchment,
    CollectionCountOptions,
    CollectionFrequency,
    WasteFlyer,
)
from sources.waste_collection.tests.test_collection_update_authorization import (
    CollectionUpdateFixture,
)
from utils.object_management.models import ObjectEditorGrant, ReviewAction


class CollectionCreationFixture(CollectionUpdateFixture):
    """Extend the update fixture with version-creation records."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        ensure_distribution_data(stdout=StringIO())
        cls.foreign_published = cls._collection(
            "foreign published", cls.stranger, "published"
        )
        cls.private_catchment = CollectionCatchment.objects.create(
            name="private catchment",
            region=cls._region_with_borders("private catchment region"),
            owner=cls.stranger,
            publication_status="private",
        )
        cls.staff_col_only = User.objects.create_user(
            "create-staff-col-only", is_staff=True
        )
        cls.staff_col_only.groups.clear()
        cls.staff_col_only.user_permissions.clear()
        cls.staff_col_only.user_permissions.add(
            Permission.objects.get(
                codename="add_collection",
                content_type=ContentType.objects.get_for_model(Collection),
            )
        )

    def _create_url(self):
        return reverse("api-waste-collection-create")

    def _create_payload(self, **overrides):
        payload = {
            "catchment": self.catchment.pk,
            "waste_category": self.category.pk,
            "collection_system": self.system.pk,
            "valid_from": "2025-01-01",
        }
        payload.update(overrides)
        return payload

    def _post_create(self, user, **payload):
        self.client.force_login(user)
        return self.client.post(
            self._create_url(), self._create_payload(**payload), format="json"
        )

    def _created_events(self, obj):
        return ReviewAction.objects.filter(
            content_type=ContentType.objects.get_for_model(type(obj)),
            object_id=obj.pk,
            action=ReviewAction.ACTION_CREATED,
        )

    def _submitted_events(self, obj):
        return ReviewAction.objects.filter(
            content_type=ContentType.objects.get_for_model(type(obj)),
            object_id=obj.pk,
            action=ReviewAction.ACTION_SUBMITTED,
        )


class CollectionCreateAuthorizationTests(CollectionCreationFixture, APITestCase):
    """The create route uses capability, references and creation audit."""

    def test_contributor_create_records_single_creation_audit(self):
        response = self._post_create(self.owner, submit_for_review=False)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        collection = Collection.objects.get(pk=response.data["id"])
        self.assertEqual(collection.owner, self.owner)
        self.assertEqual(collection.publication_status, "private")
        events = self._created_events(collection)
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.get().user, self.owner)
        self.assertEqual(events.get().content_revision, collection.content_revision)

    def test_create_submit_for_review_records_single_transition(self):
        response = self._post_create(self.owner, submit_for_review=True)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        collection = Collection.objects.get(pk=response.data["id"])
        self.assertEqual(collection.publication_status, "review")
        self.assertTrue(response.data["submitted"])
        events = self._submitted_events(collection)
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.get().user, self.owner)

    def test_create_without_submit_stays_private(self):
        response = self._post_create(self.owner, submit_for_review=False)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        collection = Collection.objects.get(pk=response.data["id"])
        self.assertEqual(collection.publication_status, "private")
        self.assertFalse(response.data["submitted"])
        self.assertFalse(self._submitted_events(collection).exists())

    def test_staff_only_cannot_create(self):
        before = set(Collection.objects.values_list("pk", flat=True))
        response = self._post_create(self.staff_only)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(set(Collection.objects.values_list("pk", flat=True)), before)

    def test_inactive_actor_cannot_create(self):
        # The shared permission boundary denies inactive actors before the view.
        response = self._post_create(self.inactive)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_add_capability_cannot_create(self):
        response = self._post_create(self.no_cap)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_administrator_can_create(self):
        response = self._post_create(self.admin, submit_for_review=False)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            Collection.objects.get(pk=response.data["id"]).owner, self.admin
        )

    def test_create_rejects_unreadable_collector(self):
        before = set(Collection.objects.values_list("pk", flat=True))
        response = self._post_create(self.owner, collector=self.private_collector.pk)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(set(Collection.objects.values_list("pk", flat=True)), before)

    def test_create_rejects_unreadable_material(self):
        before = set(Collection.objects.values_list("pk", flat=True))
        response = self._post_create(
            self.owner, allowed_materials=[self.private_material.pk]
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(set(Collection.objects.values_list("pk", flat=True)), before)

    def test_create_rejects_unreadable_frequency(self):
        response = self._post_create(self.owner, frequency=self.private_frequency.pk)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_rejects_unreadable_catchment(self):
        response = self._post_create(self.owner, catchment=self.private_catchment.pk)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_rejects_unreadable_fee_and_bin(self):
        before = set(Collection.objects.values_list("pk", flat=True))
        response = self._post_create(
            self.owner,
            fee_system=self.private_fee.pk,
            bin_configuration=self.private_bin.pk,
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(set(Collection.objects.values_list("pk", flat=True)), before)

    def test_create_rejects_unreadable_new_flyer_without_add_capability(self):
        """New flyer creation needs the flyer's own add capability."""
        before_flyers = set(WasteFlyer.objects.values_list("pk", flat=True))
        response = self._post_create(
            self.update_only, flyer_urls=["https://example.com/create-denied"]
        )
        # update_only lacks both add_collection and add_wasteflyer.
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            set(WasteFlyer.objects.values_list("pk", flat=True)), before_flyers
        )


class CollectionNewVersionAuthorizationTests(CollectionCreationFixture, APITestCase):
    """New-version creation binds read access, capability and audit."""

    def _version_url(self, collection):
        return reverse("api-waste-collection-new-version", kwargs={"pk": collection.pk})

    def _post_version(self, user, collection, **payload):
        self.client.force_login(user)
        data = {"valid_from": "2025-03-15"}
        data.update(payload)
        return self.client.post(self._version_url(collection), data, format="json")

    def test_new_version_records_creation_audit_and_graph(self):
        response = self._post_version(
            self.owner, self.published_col, submit_for_review=False
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        version = Collection.objects.get(pk=response.data["id"])
        self.assertEqual(version.owner, self.owner)
        self.assertEqual(version.publication_status, "private")
        self.assertTrue(version.predecessors.filter(pk=self.published_col.pk).exists())
        events = self._created_events(version)
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.get().user, self.owner)

    def test_new_version_submit_records_transition(self):
        response = self._post_version(
            self.owner, self.published_col, submit_for_review=True
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        version = Collection.objects.get(pk=response.data["id"])
        self.assertEqual(version.publication_status, "review")
        self.assertEqual(self._submitted_events(version).count(), 1)

    def test_new_version_foreign_published_allowed(self):
        """Duplicate semantics: any readable predecessor plus add capability."""
        response = self._post_version(
            self.owner, self.foreign_published, submit_for_review=False
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        version = Collection.objects.get(pk=response.data["id"])
        self.assertEqual(version.owner, self.owner)
        self.assertTrue(
            version.predecessors.filter(pk=self.foreign_published.pk).exists()
        )

    def test_new_version_shared_private_allowed_via_grant(self):
        """An editor grant makes a private predecessor readable and versionable."""
        ObjectEditorGrant.objects.create(
            content_type=ContentType.objects.get_for_model(Collection),
            object_id=self.foreign_private.pk,
            editor=self.owner,
        )
        response = self._post_version(
            self.owner, self.foreign_private, submit_for_review=False
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        version = Collection.objects.get(pk=response.data["id"])
        self.assertEqual(version.owner, self.owner)

    def test_new_version_administrator_allowed(self):
        response = self._post_version(
            self.admin, self.foreign_published, submit_for_review=False
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_new_version_unreadable_predecessor_is_404(self):
        response = self._post_version(self.owner, self.foreign_private)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_new_version_archived_is_denied(self):
        response = self._post_version(self.owner, self.archived_col)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(self.archived_col.successors.exists())

    def test_new_version_missing_capability_is_denied(self):
        response = self._post_version(self.no_cap, self.published_col)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_new_version_staff_only_is_denied(self):
        response = self._post_version(self.staff_only, self.staff_col)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(self.staff_col.successors.exists())

    def test_new_version_drops_unreadable_inherited_references(self):
        """Unreadable inherited sources/flyers are skipped, not leaked or copied."""
        self.published_col.sources.add(self.public_source, self.private_source)
        self.published_col.flyers.add(self.public_flyer, self.hidden_flyer)

        response = self._post_version(
            self.owner, self.published_col, submit_for_review=False
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        version = Collection.objects.get(pk=response.data["id"])
        self.assertEqual(
            set(version.sources.values_list("pk", flat=True)),
            {self.public_source.pk},
        )
        self.assertEqual(
            set(version.flyers.values_list("pk", flat=True)),
            {self.public_flyer.pk},
        )

    def test_new_version_submitted_source_still_requires_read(self):
        response = self._post_version(
            self.owner,
            self.published_col,
            sources=[self.private_source.pk],
            submit_for_review=False,
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(self.published_col.successors.exists())


class CollectionFrequencyAuthorizationTests(CollectionCreationFixture, APITestCase):
    """Frequency creation uses capability and creation audits."""

    def _payload(self, **overrides):
        payload = {
            "name": "Audited seasonal",
            "description": "Frequency audit coverage.",
            "submit_for_review": False,
            "rows": [
                {
                    "distribution": "Months of the year",
                    "first_timestep": "March",
                    "last_timestep": "October",
                    "standard_cadence": "every_two_weeks",
                }
            ],
        }
        payload.update(overrides)
        return payload

    def _post(self, user, **overrides):
        self.client.force_login(user)
        return self.client.post(
            reverse("api-waste-collection-frequency-create"),
            self._payload(**overrides),
            format="json",
        )

    def test_frequency_create_records_creation_audits(self):
        response = self._post(self.owner)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        frequency = CollectionFrequency.objects.get(pk=response.data["id"])
        self.assertEqual(frequency.owner, self.owner)
        events = self._created_events(frequency)
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.get().user, self.owner)

        rows = CollectionCountOptions.objects.filter(frequency=frequency)
        self.assertEqual(rows.count(), 1)
        row = rows.get()
        self.assertEqual(row.owner, self.owner)
        row_events = self._created_events(row)
        self.assertEqual(row_events.count(), 1)
        self.assertEqual(row_events.get().user, self.owner)

    def test_frequency_submit_records_single_transition(self):
        response = self._post(self.owner, submit_for_review=True)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        frequency = CollectionFrequency.objects.get(pk=response.data["id"])
        self.assertEqual(frequency.publication_status, "review")
        self.assertEqual(self._submitted_events(frequency).count(), 1)
        row = CollectionCountOptions.objects.get(frequency=frequency)
        self.assertEqual(row.publication_status, "review")
        self.assertEqual(self._submitted_events(row).count(), 1)

    def test_frequency_staff_only_denied(self):
        before = set(CollectionFrequency.objects.values_list("pk", flat=True))
        response = self._post(self.staff_only)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            set(CollectionFrequency.objects.values_list("pk", flat=True)), before
        )


class BulkImportGateTests(CollectionCreationFixture, APITestCase):
    """The bulk-import gate uses create capabilities, not staff status."""

    def _post(self, user, **payload):
        self.client.force_login(user)
        data = {"records": [], "dry_run": True}
        data.update(payload)
        return self.client.post(
            reverse("api-waste-collection-bulk-import"), data, format="json"
        )

    def test_staff_only_without_capability_is_denied(self):
        response = self._post(self.staff_only)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_contributor_with_create_capability_passes_gate(self):
        response = self._post(self.owner)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["dry_run"])

    def test_create_collectors_requires_collector_capability(self):
        response = self._post(self.staff_col_only, create_collectors=True)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_collectors_allowed_with_capability(self):
        response = self._post(self.owner, create_collectors=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ScopedReadAdapterTests(CollectionCreationFixture, APITestCase):
    """Public/archived scopes and extended-list gates follow the policy."""

    def test_anonymous_archived_scope_is_public(self):
        self.client.force_authenticate(None)
        response = self.client.get(
            reverse("api-waste-collection-summaries"), {"scope": "archived"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_anonymous_review_scope_denied(self):
        self.client.force_authenticate(None)
        response = self.client.get(
            reverse("api-waste-collection-summaries"), {"scope": "review"}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_extended_list_denies_staff_without_admin_or_group(self):
        self.client.force_login(self.staff_only)
        response = self.client.get(
            reverse("api-waste-collection-list"), {"view": "extended"}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_extended_list_allows_application_admin(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("api-waste-collection-list"), {"view": "extended"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_extended_list_allows_analysis_group_member(self):
        analyst = User.objects.create_user("create-analyst")
        analyst.groups.add(Group.objects.get_or_create(name="analysis_api")[0])
        self.client.force_login(analyst)
        response = self.client.get(
            reverse("api-waste-collection-list"), {"view": "extended"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
