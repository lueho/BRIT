"""Admin boundary concurrency: a real admin ``Client`` POST that waits on
the service's ``select_for_update`` must re-authorize after the lock —
stale actor/site eligibility or a state change committed while waiting
must deny the whole write. PostgreSQL ``TransactionTestCase``, joined
workers, bounded Events, no sleeps.
"""

import threading
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db import connections, transaction
from django.db.models import QuerySet
from django.test import Client, TransactionTestCase

from bibliography.models import Author, Source, SourceAuthor
from materials.models import Composition, Material, MaterialComponentGroup, Sample
from utils.object_management.models import ReviewAction
from utils.object_management.services import perform_transition
from utils.tests.testcases import ensure_test_default_owner


def _admin_race(case, target, work, change):
    """Run ``work`` on a worker blocked on ``target``'s row lock; commit
    ``change`` on this thread; release; the worker's POST must finish with
    exactly 403 — never a partial save."""
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
    case.assertEqual(result["response"].status_code, 403, result)


def _source_changeform(source, **changes):
    payload = {
        "title": source.title,
        "type": source.type or "misc",
        "citation_key": "",
        "licence": "",
        "sourceauthors-TOTAL_FORMS": "0",
        "sourceauthors-INITIAL_FORMS": "0",
        "sourceauthors-MIN_NUM_FORMS": "0",
        "sourceauthors-MAX_NUM_FORMS": "1000",
        "_save": "Save",
    }
    payload.update(changes)
    return payload


class AdminPostRaceTests(TransactionTestCase):
    """Post-lock re-authorization for real admin POSTs."""

    def setUp(self):
        ensure_test_default_owner()
        self.owner = User.objects.create_user(username="ar-owner", is_staff=True)
        self.moderator = User.objects.create_user(username="ar-moderator")
        self.moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_source",
                content_type=ContentType.objects.get_for_model(Source),
            )
        )
        self.ct = ContentType.objects.get_for_model(Source)

    def _events(self, source):
        return ReviewAction.objects.filter(content_type=self.ct, object_id=source.pk)

    def test_approval_commit_denies_waiting_admin_edit(self):
        source = Source.objects.create(
            owner=self.owner, title="Racing", publication_status="review"
        )
        self.owner.user_permissions.add(
            Permission.objects.get(codename="change_source", content_type=self.ct)
        )
        author = Author.objects.create(
            owner=self.owner, first_names="New", last_names="Contributor"
        )

        def work():
            client = Client()
            client.force_login(self.owner)
            return client.post(
                f"/admin/bibliography/source/{source.pk}/change/",
                _source_changeform(
                    source,
                    title="Racing renamed",
                    **{
                        "sourceauthors-TOTAL_FORMS": "1",
                        "sourceauthors-0-author": str(author.pk),
                        "sourceauthors-0-position": "1",
                    },
                ),
            )

        def approve():
            perform_transition(self.moderator, source, "approve", expected_revision=1)

        _admin_race(self, source, work, approve)
        source.refresh_from_db()
        # Approval committed; the waited-on edit lost and changed nothing.
        self.assertEqual(source.publication_status, "published")
        self.assertEqual(source.title, "Racing")
        self.assertEqual(source.content_revision, 1)
        self.assertFalse(SourceAuthor.objects.filter(source=source).exists())
        self.assertFalse(self._events(source).filter(action="edited").exists())
        self.assertEqual(self._events(source).filter(action="approved").count(), 1)

    def test_losing_staff_flag_denies_waiting_admin_edit(self):
        source = Source.objects.create(
            owner=self.owner, title="Owned", publication_status="private"
        )
        self.owner.user_permissions.add(
            Permission.objects.get(codename="change_source", content_type=self.ct)
        )

        def work():
            client = Client()
            client.force_login(self.owner)
            return client.post(
                f"/admin/bibliography/source/{source.pk}/change/",
                _source_changeform(source, title="Should not land"),
            )

        def revoke_staff():
            User.objects.filter(pk=self.owner.pk).update(is_staff=False)

        _admin_race(self, source, work, revoke_staff)
        source.refresh_from_db()
        self.assertEqual(source.title, "Owned")
        self.assertEqual(source.publication_status, "private")
        self.assertEqual(source.content_revision, 1)
        self.assertFalse(self._events(source).exists())

    def test_deactivation_denies_waiting_admin_edit(self):
        source = Source.objects.create(
            owner=self.owner, title="Owned2", publication_status="private"
        )
        self.owner.user_permissions.add(
            Permission.objects.get(codename="change_source", content_type=self.ct)
        )

        def work():
            client = Client()
            client.force_login(self.owner)
            return client.post(
                f"/admin/bibliography/source/{source.pk}/change/",
                _source_changeform(source, title="Should not land"),
            )

        def deactivate():
            User.objects.filter(pk=self.owner.pk).update(is_active=False)

        _admin_race(self, source, work, deactivate)
        source.refresh_from_db()
        self.assertEqual(source.title, "Owned2")
        self.assertEqual(source.publication_status, "private")
        self.assertEqual(source.content_revision, 1)
        self.assertFalse(self._events(source).exists())

    def test_losing_staff_denies_owned_create_waiting_for_parent_lock(self):
        material = Material.objects.create(owner=self.owner, name="Material")
        sample = Sample.objects.create(
            owner=self.owner, name="Sample", material=material
        )
        group = MaterialComponentGroup.objects.create(
            owner=self.owner, name="Composition group"
        )
        self.owner.user_permissions.add(
            Permission.objects.get(
                content_type=ContentType.objects.get_for_model(Sample),
                codename="change_sample",
            )
        )
        before = list(Composition.objects.filter(sample=sample).values())

        def work():
            client = Client()
            client.force_login(self.owner)
            return client.post(
                "/admin/materials/composition/add/",
                {
                    "name": "Must not be created",
                    "sample": str(sample.pk),
                    "group": str(group.pk),
                    "order": "1",
                    "_save": "Save",
                },
            )

        def revoke_staff():
            User.objects.filter(pk=self.owner.pk).update(is_staff=False)

        _admin_race(self, sample, work, revoke_staff)
        self.assertEqual(
            list(Composition.objects.filter(sample=sample).values()), before
        )
        sample.refresh_from_db()
        self.assertEqual(sample.content_revision, 1)
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(Sample),
                object_id=sample.pk,
            ).exists()
        )
