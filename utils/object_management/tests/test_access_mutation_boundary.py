"""Concurrency boundary tests for ``perform_access_change``.

A real PostgreSQL ``TransactionTestCase``: a competing mutation must block
on the service's ``select_for_update`` lock and then fail the fresh
authorization check once the lock is released — not read a stale actor or
target. No sleeps; Events + bounded waits only.
"""

import threading
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db import connections, transaction
from django.db.models import QuerySet
from django.test import TransactionTestCase

from bibliography.models import Author, Source, SourceAuthor
from materials.models import AnalyticalMethod
from utils.object_management.models import ObjectEditorGrant, ReviewAction
from utils.object_management.services import (
    content_mutation,
    perform_access_change,
    perform_transition,
    record_comment,
)


def _locked_race(case, target, work, change):
    """Commit a competing change while a service waits for a real row lock."""
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
            work()
            result["returned"] = True
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
            # Exit atomic (releasing the lock) before joining, even on failure.
            if worker.ident is not None:
                worker.join(timeout=15)
                case.assertFalse(worker.is_alive(), f"Worker did not exit: {result!r}")
    case.assertTrue(finished.is_set(), result)
    case.assertIsInstance(result.get("exception"), PermissionDenied, result)


class AccessChangeConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="cc-owner")
        self.other = User.objects.create_user(username="cc-other")
        self.recipient = User.objects.create_user(username="cc-recipient")
        self.method = AnalyticalMethod.objects.create(
            owner=self.owner, name="CC method", publication_status="private"
        )

    def test_competing_change_blocks_then_denies(self):
        def work():
            perform_access_change(self.owner, self.method, "add_editor", self.recipient)

        def transfer():
            AnalyticalMethod.objects.filter(pk=self.method.pk).update(owner=self.other)

        _locked_race(self, self.method, work, transfer)
        self.assertFalse(
            ObjectEditorGrant.objects.filter(
                object_id=self.method.pk, editor=self.recipient
            ).exists()
        )
        self.method.refresh_from_db()
        self.assertEqual(self.method.owner, self.other)


class FreshActorAfterLockTests(TransactionTestCase):
    """The canonical boundary: actor state is refreshed AFTER the row lock,
    never before. A deactivation racing the lock must deny — the worker
    blocks, then re-reads ``is_active`` and fails."""

    def setUp(self):
        self.owner = User.objects.create_user(username="fa-owner")
        self.method = AnalyticalMethod.objects.create(
            owner=self.owner, name="FA method", publication_status="private"
        )
        self.owner_ct = ContentType.objects.get_for_model(AnalyticalMethod)
        self.owner.user_permissions.add(
            Permission.objects.get(
                content_type=self.owner_ct, codename="change_analyticalmethod"
            ),
            Permission.objects.get(
                content_type=ContentType.objects.get_for_model(Source),
                codename="change_source",
            ),
        )
        self.assertTrue(self.owner.has_perm("materials.change_analyticalmethod"))
        self.assertTrue(self.owner.has_perm("bibliography.change_source"))

    def _race(self, worker_fn, deactivate_pk):
        _locked_race(
            self,
            self.method,
            worker_fn,
            lambda: User.objects.filter(pk=deactivate_pk).update(is_active=False),
        )

    def _assert_method_unchanged(self, status):
        self.method.refresh_from_db()
        self.assertEqual(self.method.name, "FA method")
        self.assertEqual(self.method.publication_status, status)
        self.assertEqual(self.method.content_revision, 1)
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type=self.owner_ct, object_id=self.method.pk
            ).exists()
        )

    def test_content_mutation_denies_deactivated_actor(self):
        def work():
            with content_mutation(self.owner, self.method, action="edit") as locked:
                locked.name = "Mutated"
                locked.save(update_fields=["name"])

        self._race(work, self.owner.pk)
        self._assert_method_unchanged("private")

    def test_perform_transition_denies_deactivated_actor(self):
        self.method.publication_status = "review"
        self.method.save()
        moderator = User.objects.create_user(username="fa-moderator")
        moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_analyticalmethod",
                content_type=self.owner_ct,
            )
        )

        self.assertTrue(moderator.has_perm("materials.can_moderate_analyticalmethod"))

        def work():
            perform_transition(moderator, self.method, "approve", expected_revision=1)

        self._race(work, moderator.pk)
        self._assert_method_unchanged("review")

    def test_record_comment_denies_deactivated_actor(self):
        self.method.publication_status = "review"
        self.method.save()

        def work():
            record_comment(
                self.owner,
                self.method,
                "racing comment",
                expected_revision=1,
            )

        self._race(work, self.owner.pk)
        self._assert_method_unchanged("review")

    def test_owned_child_lock_precedes_actor_refresh(self):
        source = Source.objects.create(owner=self.owner, title="Locked parent")
        author = Author.objects.create(
            owner=self.owner, first_names="First", last_names="Last"
        )
        row = SourceAuthor.objects.create(source=source, author=author, position=1)

        def work():
            with content_mutation(self.owner, row) as locked:
                locked.position = 2
                locked.save(update_fields=["position"])

        _locked_race(
            self,
            row,
            work,
            lambda: User.objects.filter(pk=self.owner.pk).update(is_active=False),
        )
        row.refresh_from_db()
        source.refresh_from_db()
        self.assertEqual(row.position, 1)
        self.assertEqual(source.publication_status, "private")
        self.assertEqual(source.content_revision, 1)
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(Source),
                object_id=source.pk,
            ).exists()
        )
