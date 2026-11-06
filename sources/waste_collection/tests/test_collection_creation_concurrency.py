"""Real PostgreSQL request races for governed collection new-version creation.

A version-creation request must authorize the predecessor it sees after the
row lock lands, never the state it read before blocking. The synchronization
relies on the actual ``select_for_update`` query, never sleeps or mocked
decisions.
"""

from datetime import date
from io import StringIO

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from distributions.models import TemporalDistribution, Timestep
from distributions.utils import ensure_initial_data as ensure_distribution_data
from sources.waste_collection.models import (
    Collection,
    CollectionCatchment,
    CollectionFrequency,
    CollectionSystem,
    WasteCategory,
)
from sources.waste_collection.tests.test_collection_update_concurrency import (
    _blocked_worker,
)
from utils.object_management.models import (
    ObjectEditorGrant,
    ReviewAction,
)
from utils.object_management.services import perform_transition
from utils.tests.testcases import ensure_test_default_owner


class CollectionFrequencyReuseConcurrencyTests(TransactionTestCase):
    """A frequency-reuse request must authorize the state seen after the
    matched frequency's row lock lands, never the pre-wait state."""

    def setUp(self):
        ensure_test_default_owner()
        ensure_distribution_data(stdout=StringIO())
        months = TemporalDistribution.objects.get(name="Months of the year")
        months.publication_status = "published"
        months.save(update_fields=["publication_status"])
        Timestep.objects.filter(distribution=months).update(
            publication_status="published"
        )
        self.freq_actor = User.objects.create_user("freq-reuse-actor")
        self.stranger = User.objects.create_user("freq-reuse-stranger")
        self.freq_actor.user_permissions.add(
            Permission.objects.get(
                codename="add_collectionfrequency",
                content_type=ContentType.objects.get_for_model(CollectionFrequency),
            )
        )
        self.published_freq = CollectionFrequency.objects.create(
            name="Reuse Published",
            owner=self.stranger,
            publication_status="published",
        )
        self.foreign_private_freq = CollectionFrequency.objects.create(
            name="Reuse Foreign Private",
            owner=self.stranger,
            publication_status="private",
        )

    def _frequency_post(self, user, frequency):
        client = APIClient()
        client.force_login(user)
        return client.post(
            reverse("api-waste-collection-frequency-create"),
            {
                "name": frequency.name,
                "description": "",
                "submit_for_review": False,
                "rows": [
                    {
                        "distribution": "Months of the year",
                        "first_timestep": "March",
                        "last_timestep": "October",
                        "standard_cadence": "every_two_weeks",
                    }
                ],
            },
            format="json",
        )

    def test_deactivated_actor_denied_after_frequency_lock(self):
        self.assertTrue(
            self.freq_actor.has_perm("waste_collection.add_collectionfrequency")
        )
        self.assertFalse(
            self.freq_actor.has_perm("waste_collection.add_collectioncountoptions")
        )
        response = _blocked_worker(
            self,
            self.published_freq,
            lambda: self._frequency_post(self.freq_actor, self.published_freq),
            lambda: User.objects.filter(pk=self.freq_actor.pk).update(is_active=False),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(CollectionFrequency),
                object_id=self.published_freq.pk,
            ).count(),
            0,
        )

    def test_revoked_grant_denied_after_foreign_private_lock(self):
        self.assertTrue(
            self.freq_actor.has_perm("waste_collection.add_collectionfrequency")
        )
        ct = ContentType.objects.get_for_model(CollectionFrequency)
        grant = ObjectEditorGrant.objects.create(
            content_type=ct,
            object_id=self.foreign_private_freq.pk,
            editor=self.freq_actor,
            granted_by=self.stranger,
        )

        response = _blocked_worker(
            self,
            self.foreign_private_freq,
            lambda: self._frequency_post(self.freq_actor, self.foreign_private_freq),
            grant.delete,
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            ReviewAction.objects.filter(
                content_type=ct, object_id=self.foreign_private_freq.pk
            ).count(),
            0,
        )


class CollectionNewVersionConcurrencyTests(TransactionTestCase):
    """Race a new-version request against predecessor lifecycle changes."""

    def setUp(self):
        ensure_test_default_owner()
        self.owner = User.objects.create_user("version-race-owner")
        self.grantee = User.objects.create_user("version-race-grantee")
        self.moderator = User.objects.create_user("version-race-moderator")
        self.stranger = User.objects.create_user("version-race-stranger")
        collection_ct = ContentType.objects.get_for_model(Collection)
        self.collection_ct = collection_ct
        add_perm = Permission.objects.get(
            codename="add_collection", content_type=collection_ct
        )
        change_perm = Permission.objects.get(
            codename="change_collection", content_type=collection_ct
        )
        for user in (self.owner, self.grantee):
            user.user_permissions.add(add_perm)
            user.user_permissions.add(change_perm)
        self.moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_collection", content_type=collection_ct
            )
        )
        self.catchment = CollectionCatchment.objects.create(
            name="Version Race Catchment", publication_status="published"
        )
        self.system = CollectionSystem.objects.create(
            name="Version Race System", publication_status="published"
        )
        self.category = WasteCategory.objects.create(
            name="Version Race Category", publication_status="published"
        )
        self.published_col = Collection.objects.create(
            name="Version Race Published",
            description="predecessor description",
            catchment=self.catchment,
            collection_system=self.system,
            waste_category=self.category,
            valid_from=date(2020, 1, 1),
            publication_status="published",
            owner=self.owner,
        )
        self.foreign_private = Collection.objects.create(
            name="Version Race Foreign Private",
            description="foreign private",
            catchment=self.catchment,
            collection_system=self.system,
            waste_category=self.category,
            valid_from=date(2020, 1, 1),
            publication_status="private",
            owner=self.stranger,
        )

    def _version_post(self, user, predecessor):
        client = APIClient()
        client.force_login(user)
        return client.post(
            reverse(
                "api-waste-collection-new-version",
                kwargs={"pk": predecessor.pk},
            ),
            {"valid_from": "2025-03-15", "submit_for_review": False},
            format="json",
        )

    def _predecessor_events(self, predecessor):
        return ReviewAction.objects.filter(
            content_type=self.collection_ct, object_id=predecessor.pk
        )

    def test_deactivated_actor_denied_after_predecessor_lock(self):
        response = _blocked_worker(
            self,
            self.published_col,
            lambda: self._version_post(self.owner, self.published_col),
            lambda: User.objects.filter(pk=self.owner.pk).update(is_active=False),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(self.published_col.successors.exists())
        self.assertEqual(self._predecessor_events(self.published_col).count(), 0)

    def test_revoked_grant_makes_foreign_private_predecessor_unreadable(self):
        grant = ObjectEditorGrant.objects.create(
            content_type=self.collection_ct,
            object_id=self.foreign_private.pk,
            editor=self.grantee,
            granted_by=self.stranger,
        )

        response = _blocked_worker(
            self,
            self.foreign_private,
            lambda: self._version_post(self.grantee, self.foreign_private),
            grant.delete,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(self.foreign_private.successors.exists())
        self.assertEqual(self._predecessor_events(self.foreign_private).count(), 0)

    def test_archived_predecessor_denied_after_lock(self):
        response = _blocked_worker(
            self,
            self.published_col,
            lambda: self._version_post(self.owner, self.published_col),
            lambda: perform_transition(self.moderator, self.published_col, "archive"),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(self.published_col.successors.exists())

    def test_version_copies_locked_scalar_state(self):
        """A scalar change committed while the worker waits is what the new
        version inherits - never a stale prefetch."""

        def edit_description():
            Collection.objects.filter(pk=self.published_col.pk).update(
                description="locked description"
            )

        response = _blocked_worker(
            self,
            self.published_col,
            lambda: self._version_post(self.owner, self.published_col),
            edit_description,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        version = Collection.objects.get(pk=response.data["id"])
        self.assertEqual(version.description, "locked description")
        self.assertTrue(version.predecessors.filter(pk=self.published_col.pk).exists())
