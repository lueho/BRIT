"""Real PostgreSQL request races for governed collection updates.

Each worker request must be authorized by the shared mutation boundary
against the state it sees after acquiring the row lock, not the state it
read before blocking. These tests synchronize on the actual
``select_for_update`` query, never on a sleep or a mocked decision.
"""

import threading
from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db import connections, transaction
from django.db.models import QuerySet
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from sources.waste_collection.models import (
    Collection,
    CollectionCatchment,
    CollectionSystem,
    WasteCategory,
)
from utils.object_management.models import (
    ObjectEditorGrant,
    ReviewAction,
)
from utils.object_management.services import perform_transition
from utils.tests.testcases import ensure_test_default_owner


def _blocked_worker(case, target, work, change):
    """Run ``work`` on a worker blocked on ``target``'s row lock; commit
    ``change`` on this thread; release; the worker's response must finish
    with exactly 403, never a partial save."""
    entered = threading.Event()
    finished = threading.Event()
    result = {}
    original_get = QuerySet.get

    def signal_get(queryset, *args, **kwargs):
        if (
            threading.current_thread() is worker
            and queryset.model is type(target)
            and queryset.query.select_for_update
        ):
            entered.set()
        return original_get(queryset, *args, **kwargs)

    def run():
        try:
            result["response"] = work()
        except Exception as exc:
            result["exception"] = exc
        finally:
            try:
                connections["default"].close()
            finally:
                finished.set()

    worker = threading.Thread(target=run, daemon=True)
    with patch.object(QuerySet, "get", signal_get):
        try:
            with transaction.atomic():
                type(target)._base_manager.select_for_update().get(pk=target.pk)
                worker.start()
                case.assertTrue(
                    entered.wait(timeout=10),
                    f"Worker never reached the row lock: {result!r}",
                )
                case.assertFalse(
                    finished.wait(timeout=0.2),
                    f"Worker passed a held row lock: {result!r}",
                )
                change()
        finally:
            if worker.ident is not None:
                worker.join(timeout=15)
                case.assertFalse(worker.is_alive(), f"Worker did not exit: {result!r}")
    case.assertTrue(finished.is_set(), result)
    case.assertIsNone(result.get("exception"), result)
    return result["response"]


class CollectionUpdateConcurrencyTests(TransactionTestCase):
    """Use narrow capabilities to isolate lock-boundary authorization.

    Role-provisioned contributor workflows have separate request coverage.
    """

    def setUp(self):
        ensure_test_default_owner()
        self.owner = User.objects.create_user("update-race-owner")
        self.grantee = User.objects.create_user("update-race-grantee")
        self.moderator = User.objects.create_user("update-race-moderator")
        collection_ct = ContentType.objects.get_for_model(Collection)
        change_perm = Permission.objects.get(
            codename="change_collection", content_type=collection_ct
        )
        self.owner.user_permissions.add(change_perm)
        self.grantee.user_permissions.add(change_perm)
        self.moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_collection", content_type=collection_ct
            )
        )
        self.collection_ct = collection_ct
        self.catchment = CollectionCatchment.objects.create(
            name="Race Catchment", publication_status="published"
        )
        self.system = CollectionSystem.objects.create(
            name="Race System", publication_status="published"
        )
        self.category = WasteCategory.objects.create(
            name="Race Category", publication_status="published"
        )
        self.private_col = Collection.objects.create(
            name="Race Private",
            description="original description",
            catchment=self.catchment,
            collection_system=self.system,
            waste_category=self.category,
            valid_from=date(2020, 1, 1),
            publication_status="private",
            owner=self.owner,
        )
        self.review_col = Collection.objects.create(
            name="Race Review",
            description="original description",
            catchment=self.catchment,
            collection_system=self.system,
            waste_category=self.category,
            valid_from=date(2020, 1, 1),
            publication_status="review",
            owner=self.owner,
        )

    def _update_post(self, user, collection, **payload):
        client = APIClient()
        client.force_login(user)
        return client.post(
            reverse("api-waste-collection-update", kwargs={"pk": collection.pk}),
            {
                "expected_catchment_id": collection.catchment_id,
                "expected_waste_category_id": collection.waste_category_id,
                "expected_collection_system_id": collection.collection_system_id,
                "expected_publication_status": collection.publication_status,
                "expected_valid_from": collection.valid_from.isoformat(),
                **payload,
            },
            format="json",
        )

    def test_deactivated_actor_denied_after_lock(self):
        response = _blocked_worker(
            self,
            self.private_col,
            lambda: self._update_post(
                self.owner, self.private_col, description="raced"
            ),
            lambda: User.objects.filter(pk=self.owner.pk).update(is_active=False),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.private_col.refresh_from_db()
        self.assertEqual(self.private_col.description, "original description")
        self.assertEqual(self.private_col.content_revision, 1)
        self.assertEqual(
            ReviewAction.objects.filter(
                content_type=self.collection_ct,
                object_id=self.private_col.pk,
                action=ReviewAction.ACTION_EDITED,
            ).count(),
            0,
        )

    def test_revoked_grant_denied_after_lock(self):
        ct = ContentType.objects.get_for_model(Collection)
        grant = ObjectEditorGrant.objects.create(
            content_type=ct,
            object_id=self.private_col.pk,
            editor=self.grantee,
            granted_by=self.owner,
        )

        def revoke():
            grant.delete()

        response = _blocked_worker(
            self,
            self.private_col,
            lambda: self._update_post(
                self.grantee, self.private_col, description="raced"
            ),
            revoke,
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.private_col.refresh_from_db()
        self.assertEqual(self.private_col.description, "original description")
        self.assertEqual(self.private_col.content_revision, 1)
        self.assertEqual(
            ReviewAction.objects.filter(
                content_type=self.collection_ct,
                object_id=self.private_col.pk,
                action=ReviewAction.ACTION_EDITED,
            ).count(),
            0,
        )

    def test_moderator_approval_wins_race_and_denies_late_edit(self):
        response = _blocked_worker(
            self,
            self.review_col,
            lambda: self._update_post(self.owner, self.review_col, description="raced"),
            lambda: perform_transition(
                self.moderator,
                self.review_col,
                "approve",
                expected_revision=self.review_col.content_revision,
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.review_col.refresh_from_db()
        self.assertEqual(self.review_col.description, "original description")
        self.assertEqual(self.review_col.publication_status, "published")
        self.assertTrue(
            ReviewAction.objects.filter(
                content_type=self.collection_ct,
                object_id=self.review_col.pk,
                action=ReviewAction.ACTION_APPROVED,
            ).exists()
        )
        self.assertEqual(
            ReviewAction.objects.filter(
                content_type=self.collection_ct,
                object_id=self.review_col.pk,
                action=ReviewAction.ACTION_EDITED,
            ).count(),
            0,
        )
