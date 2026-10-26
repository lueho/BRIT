"""Real PostgreSQL races on governed collection approval.

A competing worker calls ``perform_transition`` while the main thread holds
the predecessor's row lock. The worker's dependency-lock query blocks on the
predecessor; the main thread then mutates actor state (deactivation or
capability revocation) *before* releasing the lock. Because the dependency
locks are acquired BEFORE the fresh actor check, the worker must re-read
authority after the lock lands and deny - never write on stale credentials.
"""

import threading
from datetime import date

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db import connections, transaction
from django.test import TransactionTestCase

from sources.waste_collection.models import (
    Collection,
    CollectionCatchment,
    CollectionSystem,
    WasteCategory,
)
from utils.object_management.models import ReviewAction
from utils.object_management.services import perform_transition
from utils.tests.testcases import ensure_test_default_owner


class CollectionApprovalRaceTests(TransactionTestCase):
    """Hold a predecessor lock, race a governed approve, mutate authority
    mid-wait, release; the worker must deny."""

    def setUp(self):
        ensure_test_default_owner()
        self.owner = User.objects.create_user("race-owner")
        self.moderator = User.objects.create_user("race-moderator")
        self.moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_collection",
                content_type=ContentType.objects.get_for_model(Collection),
            )
        )
        self.catchment = CollectionCatchment.objects.create(
            name="Race Catchment", publication_status="published"
        )
        self.system = CollectionSystem.objects.create(
            name="Race System", publication_status="published"
        )
        self.category = WasteCategory.objects.create(
            name="Race Category", publication_status="published"
        )
        self.ct = ContentType.objects.get_for_model(Collection)

    def _collection(self, name, owner, status):
        return Collection.objects.create(
            name=name,
            catchment=self.catchment,
            collection_system=self.system,
            waste_category=self.category,
            valid_from=date(2020, 1, 1),
            publication_status=status,
            owner=owner,
        )

    def _events(self, obj):
        return ReviewAction.objects.filter(content_type=self.ct, object_id=obj.pk)

    def _race(self, predecessor, change):
        """Main holds ``predecessor``'s row lock; worker performs the real
        governed approve on a candidate in review; ``change`` runs while the
        worker waits, then the lock releases."""
        candidate = self._collection("Candidate", self.owner, "review")
        candidate.predecessors.add(predecessor)
        entered = threading.Event()
        finished = threading.Event()
        result = {}
        through_table = Collection.predecessors.through._meta.db_table

        def signal_wrapper(execute, sql, params, many, context):
            if (
                threading.current_thread() is worker
                and "FOR UPDATE" in sql.upper()
                and through_table in sql
            ):
                entered.set()
            return execute(sql, params, many, context)

        def work():
            try:
                with connections["default"].execute_wrapper(signal_wrapper):
                    perform_transition(
                        self.moderator,
                        candidate,
                        "approve",
                        expected_revision=candidate.content_revision,
                    )
                result["returned"] = True
            except Exception as exc:
                result["exception"] = exc
            finally:
                try:
                    connections["default"].close()
                finally:
                    finished.set()

        worker = threading.Thread(target=work, daemon=True)
        try:
            with transaction.atomic():
                Collection._base_manager.select_for_update().get(pk=predecessor.pk)
                worker.start()
                self.assertTrue(
                    entered.wait(timeout=10),
                    f"Worker never reached the predecessor lock: {result!r}",
                )
                self.assertFalse(
                    finished.wait(timeout=0.2),
                    f"Worker passed a held predecessor lock: {result!r}",
                )
                change()
        finally:
            if worker.ident is not None:
                worker.join(timeout=15)
                self.assertFalse(worker.is_alive(), f"Worker did not exit: {result!r}")
        self.assertTrue(finished.is_set(), result)
        self.assertIsInstance(result.get("exception"), PermissionDenied, result)

        candidate.refresh_from_db()
        predecessor.refresh_from_db()
        self.assertEqual(candidate.publication_status, "review", result)
        return candidate, predecessor

    def test_deactivated_actor_denied_while_waiting_on_private_predecessor(
        self,
    ):
        predecessor = self._collection("Priv pred", self.owner, "private")

        def deactivate():
            User.objects.filter(pk=self.moderator.pk).update(is_active=False)

        candidate, predecessor = self._race(predecessor, deactivate)
        self.assertEqual(predecessor.publication_status, "private")
        self.assertFalse(
            self._events(candidate).filter(action=ReviewAction.ACTION_APPROVED).exists()
        )
        self.assertFalse(
            self._events(predecessor)
            .filter(action=ReviewAction.ACTION_ARCHIVED)
            .exists()
        )

    def test_revoked_moderation_denied_while_waiting_on_published_predecessor(
        self,
    ):
        predecessor = self._collection("Pub pred", self.owner, "published")

        def revoke():
            self.moderator.user_permissions.clear()

        candidate, predecessor = self._race(predecessor, revoke)
        self.assertEqual(predecessor.publication_status, "published")
        self.assertFalse(
            self._events(candidate).filter(action=ReviewAction.ACTION_APPROVED).exists()
        )
        self.assertFalse(
            self._events(predecessor)
            .filter(action=ReviewAction.ACTION_ARCHIVED)
            .exists()
        )
