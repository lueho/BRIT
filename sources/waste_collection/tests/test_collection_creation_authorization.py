"""Governed programmatic collection creation authorization.

The custom collection create, new-version, frequency-create and bulk-import
routes must delegate to the shared policy instead of staff shortcuts:
creation requires the model ``add`` capability, every referenced record
requires independent read access, new roots get a creation audit, and
submissions flow through the revision-bound transition service. ``is_staff``
grants none of this.
"""

from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from distributions.models import TemporalDistribution, Timestep
from distributions.utils import ensure_initial_data as ensure_distribution_data
from sources.waste_collection.models import (
    Collection,
    CollectionCatchment,
    CollectionCountOptions,
    CollectionFrequency,
    CollectionSeason,
    Collector,
    WasteFlyer,
)
from sources.waste_collection.tests.test_collection_update_authorization import (
    CollectionUpdateFixture,
)
from sources.waste_collection.viewsets import CollectionViewSet
from utils.object_management.models import ObjectEditorGrant, ReviewAction
from utils.object_management.services import _record_event


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
        cls.create_only = User.objects.create_user("create-only")
        cls.create_only.groups.clear()
        cls.create_only.user_permissions.clear()
        cls.create_only.user_permissions.add(
            Permission.objects.get(
                codename="add_collection",
                content_type=ContentType.objects.get_for_model(Collection),
            )
        )
        cls.freq_only = User.objects.create_user("create-freq-only")
        cls.freq_only.groups.clear()
        cls.freq_only.user_permissions.clear()
        cls.freq_only.user_permissions.add(
            Permission.objects.get(
                codename="add_collectionfrequency",
                content_type=ContentType.objects.get_for_model(CollectionFrequency),
            )
        )

        # The seeded calendar rows default to private ownership; publish the
        # distribution and timesteps used by positive payloads and keep one
        # private timestep for the read-authorization cases. This is test
        # fixture state only - production seed data is unchanged.
        cls.months_distribution = TemporalDistribution.objects.get(
            name="Months of the year"
        )
        cls.months_distribution.publication_status = "published"
        cls.months_distribution.save(update_fields=["publication_status"])
        Timestep.objects.filter(distribution=cls.months_distribution).update(
            publication_status="published"
        )
        cls.public_timestep = Timestep.objects.get(
            distribution=cls.months_distribution, name="March"
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

    def test_create_flyer_denied_without_add_wasteflyer_despite_add_collection(self):
        """add_collection alone must not create a flyer; the URL manager is
        never reached when the flyer capability is missing."""
        self.assertTrue(self.create_only.has_perm("waste_collection.add_collection"))
        self.assertFalse(self.create_only.has_perm("waste_collection.add_wasteflyer"))
        before = set(WasteFlyer.objects.values_list("pk", flat=True))
        with patch.object(WasteFlyer.objects, "get_or_create_by_url") as mocked:
            response = self._post_create(
                self.create_only,
                flyer_urls=["https://example.com/no-cap-flyer"],
                submit_for_review=False,
            )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        mocked.assert_not_called()
        self.assertEqual(set(WasteFlyer.objects.values_list("pk", flat=True)), before)

    def test_create_response_status_matches_persisted_state(self):
        """After submit_for_review the response must show the fresh 'review'
        state, not the stale pre-transition 'private'."""
        response = self._post_create(self.owner, submit_for_review=True)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        collection = Collection.objects.get(pk=response.data["id"])
        self.assertEqual(collection.publication_status, "review")
        self.assertEqual(response.data["publication_status"], "review")
        self.assertTrue(response.data["submitted"])

    def test_create_persists_access_control_booleans(self):
        response = self._post_create(
            self.owner,
            submit_for_review=False,
            access_control_bp=True,
            access_control_pap=False,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        collection = Collection.objects.get(pk=response.data["id"])
        self.assertTrue(collection.access_control_bp)
        self.assertFalse(collection.access_control_pap)

    def test_create_denied_after_validation_when_actor_deactivated(self):
        """Deactivation injected after serializer validation but inside the
        write boundary must still deny and leave no partial rows."""
        before_collections = set(Collection.objects.values_list("pk", flat=True))
        before_events = set(ReviewAction.objects.values_list("pk", flat=True))

        real_attach = CollectionViewSet._attach_sources_and_flyers

        def deactivate_then_attach(*args, **kwargs):
            User.objects.filter(pk=self.owner.pk).update(is_active=False)
            return real_attach(*args, **kwargs)

        with patch.object(
            CollectionViewSet,
            "_attach_sources_and_flyers",
            side_effect=deactivate_then_attach,
        ):
            response = self._post_create(
                self.owner,
                flyer_urls=["https://example.com/late-deny"],
                submit_for_review=False,
            )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            set(Collection.objects.values_list("pk", flat=True)), before_collections
        )
        self.assertFalse(
            WasteFlyer.objects.filter(url="https://example.com/late-deny").exists()
        )
        self.assertEqual(
            set(ReviewAction.objects.values_list("pk", flat=True)), before_events
        )

    def test_create_denied_when_capability_revoked_after_validation(self):
        """Revoking add_collection after validation must deny the write and
        roll back every side effect."""
        before_collections = set(Collection.objects.values_list("pk", flat=True))
        add_perm = Permission.objects.get(
            codename="add_collection",
            content_type=ContentType.objects.get_for_model(Collection),
        )

        real_attach = CollectionViewSet._attach_sources_and_flyers

        def revoke_then_attach(*args, **kwargs):
            self.owner.groups.clear()
            self.owner.user_permissions.remove(add_perm)
            return real_attach(*args, **kwargs)

        with patch.object(
            CollectionViewSet,
            "_attach_sources_and_flyers",
            side_effect=revoke_then_attach,
        ):
            response = self._post_create(
                self.owner,
                flyer_urls=["https://example.com/revoked-cap"],
                submit_for_review=False,
            )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            set(Collection.objects.values_list("pk", flat=True)), before_collections
        )
        self.assertFalse(
            WasteFlyer.objects.filter(url="https://example.com/revoked-cap").exists()
        )

    def test_create_rolls_back_everything_on_submission_failure(self):
        """A submitted-event failure after real writes leaves no root, m2m,
        flyer or audit rows behind."""
        before_collections = set(Collection.objects.values_list("pk", flat=True))
        before_events = set(ReviewAction.objects.values_list("pk", flat=True))
        real_record = _record_event
        observed = {}

        def fail_on_submit(obj, actor, action, **kwargs):
            if action == ReviewAction.ACTION_SUBMITTED:
                observed["m2m"] = obj.allowed_materials.exists()
                observed["flyer"] = obj.flyers.filter(
                    url="https://example.com/submit-fail"
                ).exists()
                observed["created_event"] = self._created_events(obj).exists()
                raise RuntimeError("injected submit failure")
            return real_record(obj, actor, action, **kwargs)

        with patch(
            "utils.object_management.services._record_event",
            side_effect=fail_on_submit,
        ):
            with self.assertLogs("django.request", "ERROR") as logs:
                with self.assertRaises(RuntimeError):
                    self._post_create(
                        self.owner,
                        allowed_materials=[self.public_material.pk],
                        flyer_urls=["https://example.com/submit-fail"],
                        submit_for_review=True,
                    )
            self.assertTrue(any("injected submit failure" in m for m in logs.output))
        self.assertTrue(observed["m2m"])
        self.assertTrue(observed["flyer"])
        self.assertTrue(observed["created_event"])
        self.assertEqual(
            set(Collection.objects.values_list("pk", flat=True)), before_collections
        )
        self.assertEqual(
            set(ReviewAction.objects.values_list("pk", flat=True)), before_events
        )
        self.assertFalse(
            WasteFlyer.objects.filter(url="https://example.com/submit-fail").exists()
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

    def test_new_version_response_status_matches_persisted_state(self):
        response = self._post_version(
            self.owner, self.published_col, submit_for_review=True
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        version = Collection.objects.get(pk=response.data["id"])
        self.assertEqual(version.publication_status, "review")
        self.assertEqual(response.data["publication_status"], "review")
        events = list(
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(Collection),
                object_id=version.pk,
            ).order_by("pk")
        )
        self.assertEqual([e.action for e in events], ["created", "submitted"])
        self.assertTrue(all(e.user_id == self.owner.pk for e in events))
        self.assertEqual(events[0].content_revision, version.content_revision)
        self.assertEqual(events[1].content_revision, version.content_revision)

    def test_new_version_denies_unreadable_inherited_references(self):
        """An unreadable inherited scalar/material reference must deny the
        version rather than silently dropping protected content."""
        stranger_collector = self.__class__.collector
        stranger_collector.owner = self.stranger
        stranger_collector.publication_status = "private"
        stranger_collector.save()
        stranger_frequency = CollectionFrequency.objects.create(
            name="stranger frequency", owner=self.stranger, publication_status="private"
        )
        pred = self._collection("pred private refs", self.stranger, "published")
        pred.collector = stranger_collector
        pred.frequency = stranger_frequency
        pred.save()
        pred.allowed_materials.set([self.private_material])

        response = self._post_version(self.owner, pred, submit_for_review=False)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(pred.successors.exists())

    def test_new_version_explicit_readable_override_accepted(self):
        response = self._post_version(
            self.owner,
            self.published_col,
            collector=self.collector.pk,
            allowed_materials=[self.public_material.pk],
            submit_for_review=False,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        version = Collection.objects.get(pk=response.data["id"])
        self.assertEqual(version.collector_id, self.collector.pk)
        self.assertEqual(
            list(version.allowed_materials.values_list("pk", flat=True)),
            [self.public_material.pk],
        )

    def test_new_version_persists_access_control_booleans(self):
        self.published_col.access_control_bp = True
        self.published_col.access_control_pap = True
        self.published_col.save()

        response = self._post_version(
            self.owner, self.published_col, submit_for_review=False
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        version = Collection.objects.get(pk=response.data["id"])
        self.assertTrue(version.access_control_bp)
        self.assertTrue(version.access_control_pap)

        response = self._post_version(
            self.owner,
            self.published_col,
            access_control_bp=False,
            access_control_pap=False,
            submit_for_review=False,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        version2 = Collection.objects.get(pk=response.data["id"])
        self.assertFalse(version2.access_control_bp)
        self.assertFalse(version2.access_control_pap)

    def _locked_state_proof(self):
        """State snapshots used by late-revocation assertions."""
        return {
            "collections": set(Collection.objects.values_list("pk", flat=True)),
            "flyers": set(WasteFlyer.objects.values_list("pk", flat=True)),
            "events": set(ReviewAction.objects.values_list("pk", flat=True)),
        }

    def test_new_version_denied_when_capability_revoked_after_attachment(self):
        """Revoking add_collection after the compound helper wrote the graph
        must deny at the final check and roll back every write."""
        before = self._locked_state_proof()
        add_perm = Permission.objects.get(
            codename="add_collection",
            content_type=ContentType.objects.get_for_model(Collection),
        )
        real_attach = CollectionViewSet._attach_sources_and_flyers
        observed = {}

        def attach_then_revoke(collection, **kwargs):
            result = real_attach(collection, **kwargs)
            observed["collection_exists"] = Collection.objects.filter(
                pk=collection.pk
            ).exists()
            observed["flyer_exists"] = collection.flyers.filter(
                url="https://example.com/version-late-revoke"
            ).exists()
            self.owner.groups.clear()
            self.owner.user_permissions.remove(add_perm)
            return result

        with patch.object(
            CollectionViewSet,
            "_attach_sources_and_flyers",
            side_effect=attach_then_revoke,
        ):
            response = self._post_version(
                self.owner,
                self.published_col,
                flyer_urls=["https://example.com/version-late-revoke"],
                submit_for_review=False,
            )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(observed["collection_exists"])
        self.assertTrue(observed["flyer_exists"])
        after = self._locked_state_proof()
        self.assertEqual(after["collections"], before["collections"])
        self.assertEqual(after["flyers"], before["flyers"])
        self.assertEqual(after["events"], before["events"])
        self.assertFalse(self.published_col.successors.exists())

    def test_new_version_denied_when_actor_deactivated_after_attachment(self):
        """Deactivation after the helper writes must deny at the final
        actor check and roll back the whole graph."""
        before = self._locked_state_proof()
        real_attach = CollectionViewSet._attach_sources_and_flyers
        observed = {}

        def attach_then_deactivate(collection, **kwargs):
            result = real_attach(collection, **kwargs)
            observed["collection_exists"] = Collection.objects.filter(
                pk=collection.pk
            ).exists()
            User.objects.filter(pk=self.owner.pk).update(is_active=False)
            return result

        with patch.object(
            CollectionViewSet,
            "_attach_sources_and_flyers",
            side_effect=attach_then_deactivate,
        ):
            response = self._post_version(
                self.owner,
                self.published_col,
                flyer_urls=["https://example.com/version-late-deactivate"],
                submit_for_review=False,
            )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(observed["collection_exists"])
        after = self._locked_state_proof()
        self.assertEqual(after["collections"], before["collections"])
        self.assertEqual(after["events"], before["events"])
        self.assertFalse(self.published_col.successors.exists())

    def test_new_version_404_when_read_lost_after_attachment(self):
        """Losing object read after the compound helper wrote the graph must
        abort the transaction - the response is 404, never a committed
        partial root."""
        before = self._locked_state_proof()
        ct = ContentType.objects.get_for_model(Collection)
        grant = ObjectEditorGrant.objects.create(
            content_type=ct,
            object_id=self.foreign_private.pk,
            editor=self.owner,
            granted_by=self.stranger,
        )
        real_attach = CollectionViewSet._attach_sources_and_flyers
        observed = {}

        def attach_then_revoke(collection, **kwargs):
            result = real_attach(collection, **kwargs)
            observed["collection_exists"] = Collection.objects.filter(
                pk=collection.pk
            ).exists()
            observed["edge_exists"] = collection.predecessors.filter(
                pk=self.foreign_private.pk
            ).exists()
            observed["flyer_exists"] = collection.flyers.filter(
                url="https://example.com/version-read-lost"
            ).exists()
            observed["flyer_event"] = self._created_events(
                collection.flyers.get(url="https://example.com/version-read-lost")
            ).exists()
            grant.delete()
            return result

        with patch.object(
            CollectionViewSet,
            "_attach_sources_and_flyers",
            side_effect=attach_then_revoke,
        ):
            response = self._post_version(
                self.owner,
                self.foreign_private,
                flyer_urls=["https://example.com/version-read-lost"],
                submit_for_review=False,
            )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(observed["collection_exists"])
        self.assertTrue(observed["edge_exists"])
        self.assertTrue(observed["flyer_exists"])
        self.assertTrue(observed["flyer_event"])
        after = self._locked_state_proof()
        self.assertEqual(after["collections"], before["collections"])
        self.assertEqual(after["flyers"], before["flyers"])
        self.assertEqual(after["events"], before["events"])
        self.assertFalse(self.foreign_private.successors.exists())

    def test_new_version_denies_each_unreadable_inherited_reference(self):
        """Each inherited scalar/material reference is independently
        validated on the locked predecessor."""
        stranger_collector = Collector.objects.create(
            name="hidden collector",
            owner=self.stranger,
            publication_status="private",
        )
        stranger_frequency = CollectionFrequency.objects.create(
            name="hidden frequency",
            owner=self.stranger,
            publication_status="private",
        )

        cases = {
            "collector": {"collector": stranger_collector},
            "frequency": {"frequency": stranger_frequency},
            "allowed_materials": {"allowed_materials": [self.private_material]},
            "forbidden_materials": {"forbidden_materials": [self.private_material]},
        }
        for label, overrides in cases.items():
            with self.subTest(reference=label):
                pred = self._collection(
                    f"pred hidden {label}", self.stranger, "published"
                )
                for field, value in overrides.items():
                    if isinstance(value, list):
                        getattr(pred, field).set(value)
                    else:
                        setattr(pred, field, value)
                if not any(isinstance(v, list) for v in overrides.values()):
                    pred.save()

                response = self._post_version(self.owner, pred, submit_for_review=False)
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
                self.assertFalse(pred.successors.exists())

    def test_new_version_override_replaces_hidden_inherited_references(self):
        """Explicit readable overrides replace genuinely hidden inherited
        references and succeed."""
        hidden_collector = Collector.objects.create(
            name="override hidden collector",
            owner=self.stranger,
            publication_status="private",
        )
        hidden_frequency = CollectionFrequency.objects.create(
            name="override hidden frequency",
            owner=self.stranger,
            publication_status="private",
        )
        pred = self._collection("pred overrides", self.stranger, "published")
        pred.collector = hidden_collector
        pred.frequency = hidden_frequency
        pred.save()
        pred.allowed_materials.set([self.private_material])

        response = self._post_version(
            self.owner,
            pred,
            collector=self.collector.pk,
            frequency=self.frequency.pk,
            allowed_materials=[self.public_material.pk],
            submit_for_review=False,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        version = Collection.objects.get(pk=response.data["id"])
        self.assertEqual(version.collector_id, self.collector.pk)
        self.assertEqual(version.frequency_id, self.frequency.pk)
        self.assertEqual(
            list(version.allowed_materials.values_list("pk", flat=True)),
            [self.public_material.pk],
        )


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


class CollectionFrequencyGovernanceTests(CollectionFrequencyAuthorizationTests):
    """Independent frequency/row/season capabilities inside the boundary."""

    def _published_season(self):
        return CollectionSeason.objects.create(
            distribution=self.months_distribution,
            first_timestep=self.public_timestep,
            last_timestep=Timestep.objects.get(
                distribution=self.months_distribution, name="October"
            ),
            owner=self.stranger,
            publication_status="published",
        )

    def test_frequency_create_denied_without_countoptions_add(self):
        """A readable existing season isolates the missing
        add_collectioncountoptions capability."""
        self._published_season()
        self.assertTrue(
            self.freq_only.has_perm("waste_collection.add_collectionfrequency")
        )
        self.assertFalse(
            self.freq_only.has_perm("waste_collection.add_collectioncountoptions")
        )
        before_freq = set(CollectionFrequency.objects.values_list("pk", flat=True))
        before_rows = set(CollectionCountOptions.objects.values_list("pk", flat=True))
        before_seasons = set(CollectionSeason.objects.values_list("pk", flat=True))
        before_events = set(ReviewAction.objects.values_list("pk", flat=True))
        response = self._post(self.freq_only)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            set(CollectionFrequency.objects.values_list("pk", flat=True)), before_freq
        )
        self.assertEqual(
            set(CollectionCountOptions.objects.values_list("pk", flat=True)),
            before_rows,
        )
        self.assertEqual(
            set(CollectionSeason.objects.values_list("pk", flat=True)), before_seasons
        )
        self.assertEqual(
            set(ReviewAction.objects.values_list("pk", flat=True)), before_events
        )

    def test_frequency_create_denied_without_season_add_for_new_season(self):
        """A brand-new season needs add_collectionseason; the actor here has
        only the frequency capability plus count-option creation."""
        count_perm = Permission.objects.get(
            codename="add_collectioncountoptions",
            content_type=ContentType.objects.get_for_model(CollectionCountOptions),
        )
        self.freq_only.user_permissions.add(count_perm)
        self.assertFalse(
            self.freq_only.has_perm("waste_collection.add_collectionseason")
        )
        before_freq = set(CollectionFrequency.objects.values_list("pk", flat=True))
        before_rows = set(CollectionCountOptions.objects.values_list("pk", flat=True))
        before_seasons = set(CollectionSeason.objects.values_list("pk", flat=True))
        before_events = set(ReviewAction.objects.values_list("pk", flat=True))
        response = self._post(self.freq_only)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            set(CollectionFrequency.objects.values_list("pk", flat=True)), before_freq
        )
        self.assertEqual(
            set(CollectionCountOptions.objects.values_list("pk", flat=True)),
            before_rows,
        )
        self.assertEqual(
            set(CollectionSeason.objects.values_list("pk", flat=True)), before_seasons
        )
        self.assertEqual(
            set(ReviewAction.objects.values_list("pk", flat=True)), before_events
        )

    def test_frequency_create_denied_on_unreadable_calendar_refs(self):
        """Calendar refs hidden by a private distribution are denied (403),
        even though the name still passes serializer validation."""
        TemporalDistribution.objects.filter(pk=self.months_distribution.pk).update(
            publication_status="private", owner=self.stranger
        )
        response = self._post(
            self.owner,
            rows=[
                {
                    "distribution": "Months of the year",
                    "first_timestep": "March",
                    "last_timestep": "October",
                    "standard_cadence": "every_two_weeks",
                }
            ],
            name="Hidden step cadence",
            submit_for_review=False,
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.data)
        self.assertFalse(
            CollectionFrequency.objects.filter(name="Hidden step cadence").exists()
        )

    def test_frequency_new_season_owned_by_actor_with_audit(self):
        response = self._post(self.owner)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        frequency = CollectionFrequency.objects.get(pk=response.data["id"])
        season = frequency.collectioncountoptions_set.get().season
        self.assertEqual(season.owner, self.owner)
        self.assertEqual(season.publication_status, "private")
        self.assertEqual(self._created_events(season).count(), 1)

    def test_frequency_reuses_readable_season_without_add_capability(self):
        """An existing readable season is reused with read access only."""
        existing = self._published_season()
        self.freq_only.user_permissions.add(
            Permission.objects.get(
                codename="add_collectioncountoptions",
                content_type=ContentType.objects.get_for_model(CollectionCountOptions),
            )
        )
        self.assertTrue(
            self.freq_only.has_perm("waste_collection.add_collectionfrequency")
        )
        self.assertFalse(
            self.freq_only.has_perm("waste_collection.add_collectionseason")
        )
        season_count = CollectionSeason.objects.count()
        response = self._post(self.freq_only)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(CollectionSeason.objects.count(), season_count)
        self.assertEqual(self._created_events(existing).count(), 0)

    def test_frequency_denied_when_capability_revoked_after_helper(self):
        """Revoking add_collectionfrequency after the helper wrote real
        rows must deny at the final fresh check and roll everything back."""
        freq_perm = Permission.objects.get(
            codename="add_collectionfrequency",
            content_type=ContentType.objects.get_for_model(CollectionFrequency),
        )
        count_perm = Permission.objects.get(
            codename="add_collectioncountoptions",
            content_type=ContentType.objects.get_for_model(CollectionCountOptions),
        )
        season_perm = Permission.objects.get(
            codename="add_collectionseason",
            content_type=ContentType.objects.get_for_model(
                CollectionSeason, for_concrete_model=False
            ),
        )
        self.freq_only.user_permissions.add(count_perm)
        self.freq_only.user_permissions.add(season_perm)
        before_freq = set(CollectionFrequency.objects.values_list("pk", flat=True))
        before_rows = set(CollectionCountOptions.objects.values_list("pk", flat=True))
        before_seasons = set(CollectionSeason.objects.values_list("pk", flat=True))
        before_events = set(ReviewAction.objects.values_list("pk", flat=True))
        real_create = CollectionViewSet._create_collection_frequency
        view = CollectionViewSet()
        observed = {}

        def create_then_revoke(actor, data):
            result = real_create(view, actor, data)
            frequency, rows = result[0], result[1]
            observed["frequency_exists"] = CollectionFrequency.objects.filter(
                pk=frequency.pk
            ).exists()
            observed["row_exists"] = (
                rows and CollectionCountOptions.objects.filter(pk=rows[0].pk).exists()
            )
            self.freq_only.user_permissions.remove(freq_perm)
            return result

        with patch.object(
            CollectionViewSet,
            "_create_collection_frequency",
            side_effect=create_then_revoke,
        ):
            response = self._post(self.freq_only)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(observed["frequency_exists"])
        self.assertTrue(observed["row_exists"])
        self.assertEqual(
            set(CollectionFrequency.objects.values_list("pk", flat=True)), before_freq
        )
        self.assertEqual(
            set(CollectionCountOptions.objects.values_list("pk", flat=True)),
            before_rows,
        )
        self.assertEqual(
            set(CollectionSeason.objects.values_list("pk", flat=True)), before_seasons
        )
        self.assertEqual(
            set(ReviewAction.objects.values_list("pk", flat=True)), before_events
        )

    def test_frequency_denied_when_reused_season_becomes_unreadable(self):
        """A reused season losing read access after the helper wrote rows
        must deny at the final validation and roll the graph back."""
        existing = self._published_season()
        self.freq_only.user_permissions.add(
            Permission.objects.get(
                codename="add_collectioncountoptions",
                content_type=ContentType.objects.get_for_model(CollectionCountOptions),
            )
        )
        self.freq_only.user_permissions.add(
            Permission.objects.get(
                codename="add_collectionseason",
                content_type=ContentType.objects.get_for_model(
                    CollectionSeason, for_concrete_model=False
                ),
            )
        )
        before_freq = set(CollectionFrequency.objects.values_list("pk", flat=True))
        before_rows = set(CollectionCountOptions.objects.values_list("pk", flat=True))
        before_events = set(ReviewAction.objects.values_list("pk", flat=True))
        real_create = CollectionViewSet._create_collection_frequency
        view = CollectionViewSet()
        observed = {}

        def create_then_hide_season(actor, data):
            result = real_create(view, actor, data)
            rows = result[1]
            observed["row_season"] = rows[0].season_id == existing.pk
            observed["frequency_exists"] = CollectionFrequency.objects.filter(
                pk=result[0].pk
            ).exists()
            observed["row_exists"] = CollectionCountOptions.objects.filter(
                pk=rows[0].pk
            ).exists()
            CollectionSeason.objects.filter(pk=existing.pk).update(
                publication_status="private", owner=self.stranger
            )
            return result

        with patch.object(
            CollectionViewSet,
            "_create_collection_frequency",
            side_effect=create_then_hide_season,
        ):
            response = self._post(self.freq_only)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(observed["row_season"])
        self.assertTrue(observed["frequency_exists"])
        self.assertTrue(observed["row_exists"])
        self.assertEqual(
            set(CollectionFrequency.objects.values_list("pk", flat=True)), before_freq
        )
        self.assertEqual(
            set(CollectionCountOptions.objects.values_list("pk", flat=True)),
            before_rows,
        )
        self.assertEqual(
            set(ReviewAction.objects.values_list("pk", flat=True)), before_events
        )

    def test_frequency_rolls_back_all_writes_on_row_audit_failure(self):
        """A failing count-options creation audit rolls back the frequency,
        its seasons and any earlier creation events."""
        before_freq = set(CollectionFrequency.objects.values_list("pk", flat=True))
        before_rows = set(CollectionCountOptions.objects.values_list("pk", flat=True))
        before_seasons = set(CollectionSeason.objects.values_list("pk", flat=True))
        before_events = set(ReviewAction.objects.values_list("pk", flat=True))
        real_record = _record_event
        observed = {}

        def fail_on_row(obj, actor, action, **kwargs):
            if action == ReviewAction.ACTION_CREATED and isinstance(
                obj, CollectionCountOptions
            ):
                observed["frequency_exists"] = CollectionFrequency.objects.filter(
                    pk=obj.frequency_id
                ).exists()
                observed["row_exists"] = CollectionCountOptions.objects.filter(
                    pk=obj.pk
                ).exists()
                observed["season_exists"] = CollectionSeason.objects.filter(
                    pk=obj.season_id
                ).exists()
                observed["frequency_event"] = self._created_events(
                    obj.frequency
                ).exists()
                raise RuntimeError("injected row audit failure")
            return real_record(obj, actor, action, **kwargs)

        with patch(
            "utils.object_management.services._record_event",
            side_effect=fail_on_row,
        ):
            with self.assertLogs("django.request", "ERROR") as logs:
                with self.assertRaises(RuntimeError):
                    self._post(self.owner)
            self.assertTrue(any("injected row audit failure" in m for m in logs.output))
        self.assertTrue(observed["frequency_exists"])
        self.assertTrue(observed["row_exists"])
        self.assertTrue(observed["season_exists"])
        self.assertTrue(observed["frequency_event"])
        self.assertEqual(
            set(CollectionFrequency.objects.values_list("pk", flat=True)), before_freq
        )
        self.assertEqual(
            set(CollectionCountOptions.objects.values_list("pk", flat=True)),
            before_rows,
        )
        self.assertEqual(
            set(CollectionSeason.objects.values_list("pk", flat=True)), before_seasons
        )
        self.assertEqual(
            set(ReviewAction.objects.values_list("pk", flat=True)), before_events
        )

    def test_frequency_submit_response_matches_persisted_state(self):
        response = self._post(self.owner, submit_for_review=True)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        frequency = CollectionFrequency.objects.get(pk=response.data["id"])
        self.assertEqual(frequency.publication_status, "review")
        self.assertEqual(response.data["publication_status"], "review")
        self.assertTrue(response.data["submitted"])
        row = CollectionCountOptions.objects.get(frequency=frequency)
        self.assertEqual(row.publication_status, "review")


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
