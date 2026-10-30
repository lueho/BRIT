from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from sources.waste_collection.models import (
    Collection,
    CollectionCatchment,
    CollectionSystem,
    Collector,
    WasteCategory,
)
from utils.object_management import services as om_services
from utils.object_management.models import ReviewAction
from utils.object_management.policy import decide, scope_queryset
from utils.object_management.services import perform_transition, record_comment
from utils.tests.testcases import ensure_test_default_owner


class CollectionApprovePredecessorArchivalTests(TestCase):
    """Only published predecessors may be archived on governed approval.

    Archived records are public historical data, so archiving a private,
    review or declined predecessor would expose an unpublished draft.
    """

    @classmethod
    def setUpTestData(cls):
        ensure_test_default_owner()
        cls.owner = User.objects.create_user("pred-owner")
        cls.other_owner = User.objects.create_user("pred-other-owner")
        cls.moderator = User.objects.create_user("pred-moderator")
        cls.moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_collection",
                content_type=ContentType.objects.get_for_model(Collection),
            )
        )
        cls.catchment = CollectionCatchment.objects.create(
            name="Pred Catchment", publication_status="published"
        )
        cls.system = CollectionSystem.objects.create(
            name="Pred System", publication_status="published"
        )
        cls.category = WasteCategory.objects.create(
            name="Pred Category", publication_status="published"
        )

    def _collection(self, name, owner, status, valid_from=None):
        return Collection.objects.create(
            name=name,
            catchment=self.catchment,
            collection_system=self.system,
            waste_category=self.category,
            valid_from=valid_from or date(2020, 1, 1),
            publication_status=status,
            owner=owner,
        )

    def _review_events(self, obj, action=None):
        qs = ReviewAction.objects.filter(
            content_type=ContentType.objects.get_for_model(obj), object_id=obj.pk
        )
        if action is not None:
            qs = qs.filter(action=action)
        return qs

    def test_approve_archives_published_predecessor_with_bound_audit(self):
        predecessor = self._collection("Published pred", self.owner, "published")
        candidate = self._collection("Candidate", self.owner, "review")
        candidate.predecessors.add(predecessor)
        predecessor_revision = predecessor.content_revision

        candidate.refresh_from_db()
        perform_transition(
            self.moderator,
            candidate,
            "approve",
            expected_revision=candidate.content_revision,
        )

        candidate.refresh_from_db()
        predecessor.refresh_from_db()
        self.assertEqual(candidate.publication_status, "published")
        self.assertEqual(predecessor.publication_status, "archived")

        archived_events = self._review_events(predecessor, ReviewAction.ACTION_ARCHIVED)
        self.assertEqual(archived_events.count(), 1)
        event = archived_events.get()
        self.assertEqual(event.user, self.moderator)
        self.assertEqual(event.content_revision, predecessor_revision)

    def test_published_predecessor_remains_public_historical(self):
        predecessor = self._collection("Public pred", self.owner, "published")
        candidate = self._collection("Candidate", self.owner, "review")
        candidate.predecessors.add(predecessor)

        candidate.refresh_from_db()
        perform_transition(
            self.moderator,
            candidate,
            "approve",
            expected_revision=candidate.content_revision,
        )

        predecessor.refresh_from_db()
        self.assertEqual(predecessor.publication_status, "archived")
        self.assertTrue(decide(AnonymousUser(), "read", predecessor).allowed)
        self.assertIn(
            predecessor.pk,
            scope_queryset(
                AnonymousUser(), Collection.objects.all(), "archived"
            ).values_list("pk", flat=True),
        )
        self.assertNotIn(
            predecessor.pk,
            scope_queryset(
                AnonymousUser(), Collection.objects.all(), "published"
            ).values_list("pk", flat=True),
        )

    def test_unpublished_predecessors_are_never_archived(self):
        for status in ("private", "review", "declined"):
            with self.subTest(status=status):
                predecessor = self._collection(
                    f"{status} pred", self.other_owner, status
                )
                candidate = self._collection(
                    f"Candidate {status}", self.owner, "review"
                )
                candidate.predecessors.add(predecessor)

                candidate.refresh_from_db()
                perform_transition(
                    self.moderator,
                    candidate,
                    "approve",
                    expected_revision=candidate.content_revision,
                )

                candidate.refresh_from_db()
                predecessor.refresh_from_db()
                self.assertEqual(candidate.publication_status, "published")
                self.assertEqual(predecessor.publication_status, status)
                self.assertEqual(
                    self._review_events(
                        predecessor, ReviewAction.ACTION_ARCHIVED
                    ).count(),
                    0,
                )

    def test_foreign_private_predecessor_stays_private(self):
        predecessor = self._collection(
            "Foreign private pred", self.other_owner, "private"
        )
        candidate = self._collection("Candidate", self.owner, "review")
        candidate.predecessors.add(predecessor)

        candidate.refresh_from_db()
        perform_transition(
            self.moderator,
            candidate,
            "approve",
            expected_revision=candidate.content_revision,
        )

        predecessor.refresh_from_db()
        self.assertEqual(predecessor.publication_status, "private")
        self.assertFalse(decide(AnonymousUser(), "read", predecessor).allowed)
        self.assertEqual(self._review_events(predecessor).count(), 0)

    def test_archive_failure_rolls_back_candidate_and_predecessor(self):
        predecessor = self._collection("Published pred", self.owner, "published")
        candidate = self._collection("Candidate", self.owner, "review")
        candidate.predecessors.add(predecessor)

        real_record_event = om_services._record_event

        def failing_archive_event(obj, actor, action, **kwargs):
            if action == ReviewAction.ACTION_ARCHIVED:
                raise RuntimeError("audit transport failed")
            return real_record_event(obj, actor, action, **kwargs)

        candidate.refresh_from_db()
        with (
            self.assertRaises(RuntimeError),
            patch(
                "utils.object_management.services._record_event",
                side_effect=failing_archive_event,
            ),
        ):
            perform_transition(
                self.moderator,
                candidate,
                "approve",
                expected_revision=candidate.content_revision,
            )

        candidate.refresh_from_db()
        predecessor.refresh_from_db()
        self.assertEqual(candidate.publication_status, "review")
        self.assertEqual(predecessor.publication_status, "published")

    def test_multi_predecessor_rollback_on_second_archive_failure(self):
        """A later archive-event failure rolls back already-applied earlier
        archives - the write is all-or-nothing across predecessors."""
        pred1 = self._collection("Pred1", self.owner, "published")
        pred2 = self._collection("Pred2", self.owner, "published")
        private = self._collection("Priv", self.owner, "private")
        candidate = self._collection("Cand", self.owner, "review")
        # Deterministic pk order so pred1 archives first.
        candidate.predecessors.add(pred1, pred2, private)
        # A prior comment and the saved revisions prove the rollback
        # leaves earlier history and persistence untouched.
        comment = record_comment(
            self.moderator,
            candidate,
            "prior comment",
            expected_revision=candidate.content_revision,
        )
        candidate_rev = candidate.content_revision
        pred1_rev = pred1.content_revision
        pred2_rev = pred2.content_revision

        attempts = []
        real_record_event = om_services._record_event

        def fail_on_second(obj, actor, action, **kwargs):
            if action == ReviewAction.ACTION_ARCHIVED:
                attempts.append(obj.pk)
                if obj.pk == pred2.pk:
                    raise RuntimeError("second archive write failed")
            return real_record_event(obj, actor, action, **kwargs)

        with (
            self.assertRaises(RuntimeError),
            patch(
                "utils.object_management.services._record_event",
                side_effect=fail_on_second,
            ),
        ):
            perform_transition(
                self.moderator,
                candidate,
                "approve",
                expected_revision=candidate.content_revision,
            )

        # The first archive was actually attempted before the failure.
        self.assertEqual(attempts, [pred1.pk, pred2.pk])
        for obj, expected in (
            (candidate, "review"),
            (pred1, "published"),
            (pred2, "published"),
            (private, "private"),
        ):
            obj.refresh_from_db()
            self.assertEqual(obj.publication_status, expected)
        # No new approved or archived events anywhere.
        self.assertFalse(
            self._review_events(candidate)
            .filter(
                action__in=[
                    ReviewAction.ACTION_APPROVED,
                    ReviewAction.ACTION_ARCHIVED,
                ]
            )
            .exists()
        )
        # Earlier comment history and every root's revision survive the
        # rolled-back transaction.
        comment.refresh_from_db()
        self.assertEqual(comment.comment, "prior comment")
        self.assertEqual(comment.user_id, self.moderator.pk)
        self.assertEqual(comment.content_revision, candidate_rev)
        for obj, expected_rev in (
            (candidate, candidate_rev),
            (pred1, pred1_rev),
            (pred2, pred2_rev),
        ):
            obj.refresh_from_db()
            self.assertEqual(obj.content_revision, expected_rev)
        for pred in (pred1, pred2):
            self.assertFalse(
                self._review_events(pred)
                .filter(action=ReviewAction.ACTION_ARCHIVED)
                .exists()
            )

    def test_direct_approve_archives_only_published_predecessors(self):
        published = self._collection("Published pred", self.owner, "published")
        private = self._collection("Private pred", self.other_owner, "private")
        candidate = self._collection("Candidate", self.owner, "review")
        candidate.predecessors.add(published, private)

        candidate.approve(user=self.moderator)

        candidate.refresh_from_db()
        published.refresh_from_db()
        private.refresh_from_db()
        self.assertEqual(candidate.publication_status, "published")
        self.assertEqual(candidate.approved_by, self.moderator)
        self.assertEqual(published.publication_status, "archived")
        self.assertEqual(private.publication_status, "private")
        archived_event = self._review_events(
            published, ReviewAction.ACTION_ARCHIVED
        ).get()
        self.assertEqual(archived_event.user, self.moderator)
        self.assertEqual(self._review_events(private).count(), 0)
        # Only perform_transition records the candidate's own approval.
        self.assertEqual(
            self._review_events(candidate, ReviewAction.ACTION_APPROVED).count(),
            0,
        )

    def test_approve_without_user_is_rejected(self):
        published = self._collection("Published pred", self.owner, "published")
        candidate = self._collection("Candidate", self.owner, "review")
        candidate.predecessors.add(published)

        with self.assertRaises(ValidationError):
            candidate.approve()

        candidate.refresh_from_db()
        published.refresh_from_db()
        self.assertEqual(candidate.publication_status, "review")
        self.assertEqual(published.publication_status, "published")

    def _assert_older_version_rejected(self, older, approve):
        with self.assertRaises(ValidationError):
            approve(older)
        older.refresh_from_db()
        self.assertEqual(older.publication_status, "review")
        self.assertFalse(
            self._review_events(older, ReviewAction.ACTION_APPROVED).exists()
        )

    def test_older_version_cannot_publish_after_its_successor(self):
        older = self._collection("Older", self.other_owner, "private")
        newer = self._collection("Newer", self.owner, "review")
        newer.predecessors.add(older)
        newer.refresh_from_db()
        perform_transition(
            self.moderator, newer, "approve", expected_revision=newer.content_revision
        )
        older.refresh_from_db()
        self.assertEqual(older.publication_status, "private")

        older.submit_for_review()
        older.refresh_from_db()
        self._assert_older_version_rejected(
            older,
            lambda obj: perform_transition(
                self.moderator, obj, "approve", expected_revision=obj.content_revision
            ),
        )
        newer.refresh_from_db()
        self.assertEqual(newer.publication_status, "published")

    def test_older_version_cannot_publish_after_later_descendant(self):
        older = self._collection("Older", self.other_owner, "review")
        middle = self._collection("Middle", self.owner, "archived")
        newest = self._collection("Newest", self.owner, "published")
        middle.predecessors.add(older)
        newest.predecessors.add(middle)

        self._assert_older_version_rejected(
            older, lambda obj: obj.approve(user=self.moderator)
        )

    def test_direct_approve_rejects_older_version_with_published_successor(self):
        older = self._collection("Older", self.other_owner, "review")
        newer = self._collection("Newer", self.owner, "published")
        newer.predecessors.add(older)

        self._assert_older_version_rejected(
            older, lambda obj: obj.approve(user=self.moderator)
        )


class CollectionApproveHttpTests(TestCase):
    """Real generic approve-item requests reach the governed archive path."""

    @classmethod
    def setUpTestData(cls):
        ensure_test_default_owner()
        cls.owner = User.objects.create_user("http-owner")
        cls.moderator = User.objects.create_user("http-moderator")
        cls.moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_collection",
                content_type=ContentType.objects.get_for_model(Collection),
            )
        )
        cls.staff_only = User.objects.create_user("http-staff", is_staff=True)
        cls.catchment = CollectionCatchment.objects.create(
            name="HTTP Catchment", publication_status="published"
        )
        cls.system = CollectionSystem.objects.create(
            name="HTTP System", publication_status="published"
        )
        cls.category = WasteCategory.objects.create(
            name="HTTP Category", publication_status="published"
        )
        cls.ct = ContentType.objects.get_for_model(Collection)

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

    def _approve_url(self, obj, modal=False):
        name = (
            "object_management:approve_item_modal"
            if modal
            else ("object_management:approve_item")
        )
        return reverse(
            name,
            kwargs={
                "content_type_id": self.ct.pk,
                "object_id": obj.pk,
            },
        )

    def _events(self, obj, action=None):
        qs = ReviewAction.objects.filter(content_type=self.ct, object_id=obj.pk)
        if action is not None:
            qs = qs.filter(action=action)
        return qs

    def test_approve_item_and_modal_mixed_predecessors(self):
        for modal in (False, True):
            with self.subTest(modal=modal):
                tag = "modal" if modal else "plain"
                published = self._collection(f"{tag} pub", self.owner, "published")
                private = self._collection(f"{tag} priv", self.owner, "private")
                already_arch = self._collection(f"{tag} arch", self.owner, "archived")
                candidate = self._collection(f"{tag} cand", self.owner, "review")
                candidate.predecessors.add(published, private, already_arch)
                candidate_revision = candidate.content_revision
                published_revision = published.content_revision
                # A prior review comment survives the approval.
                comment = record_comment(
                    self.moderator,
                    candidate,
                    "prior comment",
                    expected_revision=candidate_revision,
                )
                self.client.force_login(self.moderator)
                response = self.client.post(
                    self._approve_url(candidate, modal=modal),
                    data={"expected_revision": candidate_revision},
                )
                self.assertEqual(response.status_code, 302)
                candidate.refresh_from_db()
                published.refresh_from_db()
                private.refresh_from_db()
                already_arch.refresh_from_db()
                self.assertEqual(candidate.publication_status, "published")
                self.assertEqual(candidate.content_revision, candidate_revision)
                self.assertEqual(published.content_revision, published_revision)
                approved = self._events(candidate, ReviewAction.ACTION_APPROVED).get()
                self.assertEqual(approved.user_id, self.moderator.pk)
                self.assertEqual(approved.content_revision, candidate_revision)
                self.assertEqual(published.publication_status, "archived")
                archived = self._events(published, ReviewAction.ACTION_ARCHIVED).get()
                self.assertEqual(archived.user_id, self.moderator.pk)
                self.assertEqual(archived.content_revision, published_revision)
                self.assertEqual(private.publication_status, "private")
                self.assertFalse(decide(AnonymousUser(), "read", private).allowed)
                self.assertEqual(already_arch.publication_status, "archived")
                self.assertFalse(self._events(already_arch).exists())
                # The prior comment survives with its original actor and
                # bound revision.
                comment.refresh_from_db()
                self.assertEqual(comment.comment, "prior comment")
                self.assertEqual(comment.user_id, self.moderator.pk)
                self.assertEqual(comment.content_revision, candidate_revision)
                # Prior comment retained.
                self.assertTrue(
                    self._events(candidate)
                    .filter(action=ReviewAction.ACTION_COMMENT)
                    .exists()
                )

    def test_approve_item_archives_published_predecessor(self):
        predecessor = self._collection("Pred", self.owner, "published")
        candidate = self._collection("Candidate", self.owner, "review")
        candidate.predecessors.add(predecessor)
        self.client.force_login(self.moderator)
        response = self.client.post(
            self._approve_url(candidate),
            data={"expected_revision": candidate.content_revision},
        )
        self.assertEqual(response.status_code, 302)
        predecessor.refresh_from_db()
        candidate.refresh_from_db()
        self.assertEqual(candidate.publication_status, "published")
        self.assertEqual(predecessor.publication_status, "archived")
        self.assertEqual(
            ReviewAction.objects.filter(
                content_type=self.ct,
                object_id=predecessor.pk,
                action=ReviewAction.ACTION_ARCHIVED,
            ).count(),
            1,
        )

    def test_stale_revision_denies_approval_and_archive(self):
        predecessor = self._collection("Pred", self.owner, "published")
        candidate = self._collection("Candidate", self.owner, "review")
        candidate.predecessors.add(predecessor)
        self.client.force_login(self.moderator)
        response = self.client.post(
            self._approve_url(candidate),
            data={"expected_revision": candidate.content_revision + 9},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            "The record changed since it was inspected. "
            "Reload the review page and approve again.",
            [str(m) for m in get_messages(response.wsgi_request)],
        )
        candidate.refresh_from_db()
        predecessor.refresh_from_db()
        self.assertEqual(candidate.publication_status, "review")
        self.assertEqual(predecessor.publication_status, "published")
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type=self.ct,
                object_id=predecessor.pk,
                action=ReviewAction.ACTION_ARCHIVED,
            ).exists()
        )

    def test_missing_revision_denies_approval_and_archive(self):
        predecessor = self._collection("Pred", self.owner, "published")
        candidate = self._collection("Candidate", self.owner, "review")
        candidate.predecessors.add(predecessor)
        self.client.force_login(self.moderator)
        response = self.client.post(self._approve_url(candidate), data={})
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            "An inspected content revision is required to approve.",
            [str(m) for m in get_messages(response.wsgi_request)],
        )
        candidate.refresh_from_db()
        predecessor.refresh_from_db()
        self.assertEqual(candidate.publication_status, "review")
        self.assertEqual(predecessor.publication_status, "published")

    def test_inactive_moderator_denied(self):
        predecessor = self._collection("Pred", self.owner, "published")
        candidate = self._collection("Candidate", self.owner, "review")
        candidate.predecessors.add(predecessor)
        self.client.force_login(self.moderator)
        # Deactivate after login so the request gate re-reads the actor.
        User.objects.filter(pk=self.moderator.pk).update(is_active=False)
        response = self.client.post(
            self._approve_url(candidate),
            data={"expected_revision": candidate.content_revision},
        )
        # A deactivated actor is redirected to login, not authorized.
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)
        candidate.refresh_from_db()
        predecessor.refresh_from_db()
        self.assertEqual(candidate.publication_status, "review")
        self.assertEqual(predecessor.publication_status, "published")

    def test_staff_only_denied_no_approval_or_archive(self):
        predecessor = self._collection("Pred", self.owner, "published")
        candidate = self._collection("Candidate", self.owner, "review")
        candidate.predecessors.add(predecessor)
        self.client.force_login(self.staff_only)
        response = self.client.post(
            self._approve_url(candidate),
            data={"expected_revision": candidate.content_revision},
        )
        self.assertEqual(response.status_code, 403)
        candidate.refresh_from_db()
        predecessor.refresh_from_db()
        self.assertEqual(candidate.publication_status, "review")
        self.assertEqual(predecessor.publication_status, "published")

    def test_conflicting_published_successor_denies(self):
        predecessor = self._collection("Pred", self.owner, "published")
        sibling = self._collection("Sibling", self.owner, "published")
        predecessor.successors.add(sibling)
        candidate = self._collection("Candidate", self.owner, "review")
        candidate.predecessors.add(predecessor)
        self.client.force_login(self.moderator)
        response = self.client.post(
            self._approve_url(candidate),
            data={"expected_revision": candidate.content_revision},
        )
        self.assertEqual(response.status_code, 302)
        candidate.refresh_from_db()
        predecessor.refresh_from_db()
        self.assertEqual(candidate.publication_status, "review")
        self.assertEqual(predecessor.publication_status, "published")
        sibling.refresh_from_db()
        self.assertEqual(sibling.publication_status, "published")
        self.assertFalse(
            self._events(candidate).filter(action=ReviewAction.ACTION_APPROVED).exists()
        )
        self.assertFalse(
            self._events(predecessor)
            .filter(action=ReviewAction.ACTION_ARCHIVED)
            .exists()
        )

    def test_html_update_invalidates_inspected_approval_revision(self):
        """An edit through the HTML update path bumps ``content_revision``:
        a revision the moderator inspected before the edit can no longer
        satisfy the approval contract — the stale approve is denied."""
        candidate = self._collection("Candidate", self.owner, "review")
        inspected = candidate.content_revision
        # The moderator verifiably inspected the current revision.
        record_comment(
            self.moderator,
            candidate,
            "inspected",
            expected_revision=inspected,
        )
        collector = Collector.objects.create(
            name="Update Collector", publication_status="published"
        )
        self.owner.user_permissions.add(
            Permission.objects.get(codename="change_collection")
        )

        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("collection-update", kwargs={"pk": candidate.pk}),
            data={
                "catchment": self.catchment.pk,
                "collector": collector.pk,
                "collection_system": self.system.pk,
                "waste_category": self.category.pk,
                "valid_from": "2020-01-01",
                "description": "edited after inspection",
                "form-TOTAL_FORMS": "0",
                "form-INITIAL_FORMS": "0",
            },
        )
        self.assertEqual(response.status_code, 302)
        candidate.refresh_from_db()
        self.assertEqual(candidate.content_revision, inspected + 1)

        self.client.force_login(self.moderator)
        response = self.client.post(
            self._approve_url(candidate),
            data={"expected_revision": inspected},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            "The record changed since it was inspected. "
            "Reload the review page and approve again.",
            [str(m) for m in get_messages(response.wsgi_request)],
        )
        candidate.refresh_from_db()
        self.assertEqual(candidate.publication_status, "review")
        self.assertFalse(
            self._events(candidate).filter(action=ReviewAction.ACTION_APPROVED).exists()
        )
