from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from sources.waste_collection.models import (
    Collection,
    CollectionCatchment,
    CollectionSystem,
    WasteCategory,
)
from utils.object_management.models import ReviewAction
from utils.object_management.services import perform_transition


class CollectionApprovePredecessorArchivalTests(TestCase):
    """Only published predecessors may be archived on governed approval.

    Archived records are public historical data, so archiving a private,
    review or declined predecessor would expose an unpublished draft.
    """

    @classmethod
    def setUpTestData(cls):
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
        from utils.object_management.policy import decide, scope_queryset

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
        from utils.object_management.policy import decide

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

        from utils.object_management import services as om_services

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

    def test_raw_orm_approve_archives_only_published_predecessors(self):
        published = self._collection("Published pred", self.owner, "published")
        private = self._collection("Private pred", self.other_owner, "private")
        candidate = self._collection("Candidate", self.owner, "review")
        candidate.predecessors.add(published, private)

        candidate.approve()

        candidate.refresh_from_db()
        published.refresh_from_db()
        private.refresh_from_db()
        self.assertEqual(candidate.publication_status, "published")
        self.assertEqual(published.publication_status, "archived")
        self.assertEqual(private.publication_status, "private")
        # Raw ORM approval does not invent historic audit actors.
        self.assertEqual(
            self._review_events(published, ReviewAction.ACTION_ARCHIVED).count(),
            0,
        )
