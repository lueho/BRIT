import datetime

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone

from case_studies.soilcom.models import Collection, WasteCategory

from ..models import UserCreatedObject


class ReviewWorkflowModelTests(TestCase):
    """Test the model methods for the review workflow."""

    def setUp(self):
        self.owner = User.objects.create_user(username="owner")
        self.moderator = User.objects.create_user(username="moderator")
        self.regular_user = User.objects.create_user(username="regular")

        # Add moderator permissions (created automatically by signal)
        content_type = ContentType.objects.get_for_model(Collection)
        permission = Permission.objects.get(
            codename="can_moderate_collection",
            content_type=content_type,
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
