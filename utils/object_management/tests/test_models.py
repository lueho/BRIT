import datetime

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone

from case_studies.soilcom.models import Collection, WasteCategory

from ..models import ReviewAction, UserCreatedObject


class ReviewWorkflowModelTests(TestCase):
    """Test the model methods for the review workflow."""

    def setUp(self):
        self.owner = User.objects.create_user(username="owner")
        self.moderator = User.objects.create_user(username="moderator")
        self.regular_user = User.objects.create_user(username="regular")

        # Add moderator permissions
        content_type = ContentType.objects.get_for_model(Collection)
        permission, _ = Permission.objects.get_or_create(
            codename="can_moderate_collection",
            content_type=content_type,
            defaults={"name": "Can moderate collections"},
        )
        self.moderator.user_permissions.add(permission)

        # Create a test collection
        self.category = WasteCategory.objects.create(
            name="Test Category",
            owner=self.owner,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )

        self.collection = Collection.objects.create(
            name="Test Collection",
            owner=self.owner,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )

    def test_submit_for_review(self):
        """Test submitting an object for review."""
        # Initial state
        self.assertEqual(
            self.collection.publication_status, UserCreatedObject.STATUS_PRIVATE
        )
        self.assertIsNone(self.collection.submitted_at)

        # Submit for review
        self.collection.submit_for_review()

        # Check state after submission
        self.assertEqual(
            self.collection.publication_status, UserCreatedObject.STATUS_REVIEW
        )
        self.assertIsNotNone(self.collection.submitted_at)
        self.assertIsNone(self.collection.approved_at)
        self.assertIsNone(self.collection.approved_by)

    def test_approve(self):
        """Test approving an object."""
        # Set up initial state
        self.collection.publication_status = UserCreatedObject.STATUS_REVIEW
        self.collection.save()

        # Approve the object
        self.collection.approve(user=self.moderator)

        # Check state after approval
        self.assertEqual(
            self.collection.publication_status, UserCreatedObject.STATUS_PUBLISHED
        )
        self.assertIsNotNone(self.collection.approved_at)
        self.assertEqual(self.collection.approved_by, self.moderator)

    def test_reject(self):
        """Test rejecting an object."""
        # Set up initial state
        self.collection.publication_status = UserCreatedObject.STATUS_REVIEW
        self.collection.submitted_at = timezone.make_aware(
            datetime.datetime(2025, 1, 1)
        )
        self.collection.save()

        # Reject the object
        self.collection.reject()

        # Check state after rejection
        self.assertEqual(
            self.collection.publication_status, UserCreatedObject.STATUS_DECLINED
        )
        self.assertIsNone(self.collection.submitted_at)
        self.assertIsNone(self.collection.approved_at)
        self.assertIsNone(self.collection.approved_by)

    def test_withdraw_from_review(self):
        """Test withdrawing an object from review."""
        # Set up initial state
        self.collection.publication_status = UserCreatedObject.STATUS_REVIEW
        self.collection.submitted_at = timezone.make_aware(
            datetime.datetime(2025, 1, 1)
        )
        self.collection.save()

        # Withdraw from review
        self.collection.withdraw_from_review()

        # Check state after withdrawal
        self.assertEqual(
            self.collection.publication_status, UserCreatedObject.STATUS_PRIVATE
        )
        self.assertIsNone(self.collection.submitted_at)

    def test_has_review_feedback_only_reflects_current_submission_cycle(self):
        self.assertFalse(self.collection.has_review_feedback)
        self.assertIsNone(self.collection.latest_review_feedback_action)

        first_submission = ReviewAction.objects.create(
            content_type=ContentType.objects.get_for_model(Collection),
            object_id=self.collection.pk,
            action=ReviewAction.ACTION_SUBMITTED,
            user=self.owner,
        )
        ReviewAction.objects.create(
            content_type=ContentType.objects.get_for_model(Collection),
            object_id=self.collection.pk,
            action=ReviewAction.ACTION_COMMENT,
            comment="owner follow-up",
            user=self.owner,
        )
        moderator_comment = ReviewAction.objects.create(
            content_type=ContentType.objects.get_for_model(Collection),
            object_id=self.collection.pk,
            action=ReviewAction.ACTION_COMMENT,
            comment="moderator note",
            user=self.moderator,
        )

        self.collection.__dict__.pop("latest_submission_action", None)
        self.collection.__dict__.pop("latest_review_feedback_action", None)

        self.assertEqual(
            self.collection.latest_submission_action.pk, first_submission.pk
        )
        self.assertTrue(self.collection.has_review_feedback)
        self.assertEqual(
            self.collection.latest_review_feedback_action.pk,
            moderator_comment.pk,
        )

        second_submission = ReviewAction.objects.create(
            content_type=ContentType.objects.get_for_model(Collection),
            object_id=self.collection.pk,
            action=ReviewAction.ACTION_SUBMITTED,
            user=self.owner,
        )

        self.collection.__dict__.pop("latest_submission_action", None)
        self.collection.__dict__.pop("latest_review_feedback_action", None)

        self.assertEqual(
            self.collection.latest_submission_action.pk, second_submission.pk
        )
        self.assertFalse(self.collection.has_review_feedback)
        self.assertIsNone(self.collection.latest_review_feedback_action)

        rejection = ReviewAction.objects.create(
            content_type=ContentType.objects.get_for_model(Collection),
            object_id=self.collection.pk,
            action=ReviewAction.ACTION_REJECTED,
            comment="needs changes",
            user=self.moderator,
        )

        self.collection.__dict__.pop("latest_review_feedback_action", None)

        self.assertTrue(self.collection.has_review_feedback)
        self.assertEqual(self.collection.latest_review_feedback_action.pk, rejection.pk)
