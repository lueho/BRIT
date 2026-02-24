"""Regression tests for review workflow consistency.

Tests that submission timestamps are consistent between:
- object.submitted_at (current state)
- ReviewAction.ACTION_SUBMITTED records (audit trail)

After resubmissions, the UI should show the latest submission timestamp.
"""

import time

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from case_studies.soilcom.models import Collection
from utils.object_management.models import ReviewAction

User = get_user_model()


class ReviewSubmissionConsistencyTests(TestCase):
    """Test submission timestamp consistency after resubmissions."""

    def setUp(self):
        self.owner = User.objects.create_user(username="owner")
        self.moderator = User.objects.create_user(username="moderator", is_staff=True)

        # Add moderator permissions

        content_type = ContentType.objects.get_for_model(Collection)
        permission, _ = Permission.objects.get_or_create(
            codename="can_moderate_collection",
            content_type=content_type,
            defaults={"name": "Can moderate collections"},
        )
        self.moderator.user_permissions.add(permission)

        # Create a test collection
        self.collection = Collection.objects.create(
            name="Test Collection",
            owner=self.owner,
            publication_status=Collection.STATUS_PRIVATE,
        )

    def test_initial_submission_consistency(self):
        """First submission: submitted_at and latest ReviewAction should match."""
        # Submit for review via view (which creates ReviewAction)
        self.client.force_login(self.owner)
        url = reverse(
            "object_management:submit_for_review",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(Collection).pk,
                "object_id": self.collection.pk,
            },
        )
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)

        self.collection.refresh_from_db()

        # Verify submitted_at is set
        self.assertIsNotNone(self.collection.submitted_at)

        # Verify a ReviewAction was created
        ct = ContentType.objects.get_for_model(Collection)
        actions = ReviewAction.objects.filter(
            content_type=ct,
            object_id=self.collection.pk,
            action=ReviewAction.ACTION_SUBMITTED,
        )
        self.assertEqual(actions.count(), 1, "Should have exactly one submitted action")

        # Get the latest submitted action
        latest_action = actions.order_by("-created_at", "-id").first()
        self.assertIsNotNone(latest_action)

        # Check timestamps are very close (within 1 second due to potential timing differences)
        time_diff = abs(self.collection.submitted_at - latest_action.created_at)
        self.assertLess(
            time_diff.total_seconds(),
            1.0,
            "Initial submission: submitted_at should match latest ReviewAction timestamp (within 1 second)",
        )

    def test_resubmission_consistency(self):
        """After withdraw and resubmit, timestamps should be updated and consistent."""
        # Initial submission
        self.client.force_login(self.owner)
        url = reverse(
            "object_management:submit_for_review",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(Collection).pk,
                "object_id": self.collection.pk,
            },
        )
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.collection.refresh_from_db()
        initial_submitted_at = self.collection.submitted_at
        initial_action = (
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(Collection),
                object_id=self.collection.pk,
                action=ReviewAction.ACTION_SUBMITTED,
            )
            .order_by("-created_at", "-id")
            .first()
        )

        # Withdraw (clears submitted_at)
        url = reverse(
            "object_management:withdraw_from_review",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(Collection).pk,
                "object_id": self.collection.pk,
            },
        )
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.collection.refresh_from_db()
        self.assertIsNone(self.collection.submitted_at)

        # Wait a bit to ensure different timestamp (microseconds suffice)
        time.sleep(0.01)

        # Resubmit
        url = reverse(
            "object_management:submit_for_review",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(Collection).pk,
                "object_id": self.collection.pk,
            },
        )
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.collection.refresh_from_db()

        # Get the latest submitted action
        latest_action = (
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(Collection),
                object_id=self.collection.pk,
                action=ReviewAction.ACTION_SUBMITTED,
            )
            .order_by("-created_at", "-id")
            .first()
        )

        # Verify consistency
        self.assertIsNotNone(self.collection.submitted_at)
        self.assertIsNotNone(latest_action)
        # Check timestamps are very close (within 1 second due to potential timing differences)
        time_diff = abs(self.collection.submitted_at - latest_action.created_at)
        self.assertLess(
            time_diff.total_seconds(),
            1.0,
            "Resubmission: submitted_at should match latest ReviewAction timestamp (within 1 second)",
        )

        # Verify timestamps are newer than initial submission
        self.assertGreater(
            self.collection.submitted_at,
            initial_submitted_at,
            "Resubmission timestamp should be newer than initial submission",
        )
        self.assertGreater(
            latest_action.created_at,
            initial_action.created_at,
            "Latest ReviewAction should be newer than initial action",
        )

    def test_review_ui_shows_latest_submission(self):
        """Review detail view should show the latest submission timestamp."""
        # Submit, withdraw, and resubmit to create multiple submission actions
        self.client.force_login(self.owner)

        # Initial submission
        url = reverse(
            "object_management:submit_for_review",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(Collection).pk,
                "object_id": self.collection.pk,
            },
        )
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)

        time.sleep(0.01)

        # Withdraw
        url = reverse(
            "object_management:withdraw_from_review",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(Collection).pk,
                "object_id": self.collection.pk,
            },
        )
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)

        time.sleep(0.01)

        # Resubmit
        url = reverse(
            "object_management:submit_for_review",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(Collection).pk,
                "object_id": self.collection.pk,
            },
        )
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.collection.refresh_from_db()

        # Get the review detail view as moderator
        self.client.force_login(self.moderator)
        url = reverse(
            "object_management:review_item_detail",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(Collection).pk,
                "object_id": self.collection.pk,
            },
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # The view should include review_submitted_action in context
        self.assertIn("review_submitted_action", response.context)
        submitted_action = response.context["review_submitted_action"]
        self.assertIsNotNone(submitted_action)
        self.assertEqual(submitted_action.action, ReviewAction.ACTION_SUBMITTED)

        # Verify this is the latest action, not the oldest
        latest_action = (
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(Collection),
                object_id=self.collection.pk,
                action=ReviewAction.ACTION_SUBMITTED,
            )
            .order_by("-created_at", "-id")
            .first()
        )
        self.assertEqual(
            submitted_action.pk,
            latest_action.pk,
            "Review UI should show the latest submission action",
        )

        # Verify timestamp matches object.submitted_at
        time_diff = abs(submitted_action.created_at - self.collection.submitted_at)
        self.assertLess(
            time_diff.total_seconds(),
            1.0,
            "Review UI submission timestamp should match object.submitted_at (within 1 second)",
        )

    def test_approval_preserves_submission_timestamp(self):
        """Approval should not change the submission timestamp."""
        # Submit
        self.client.force_login(self.owner)
        url = reverse(
            "object_management:submit_for_review",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(Collection).pk,
                "object_id": self.collection.pk,
            },
        )
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.collection.refresh_from_db()
        submitted_at_before = self.collection.submitted_at

        # Approve
        self.client.force_login(self.moderator)
        url = reverse(
            "object_management:approve_item",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(Collection).pk,
                "object_id": self.collection.pk,
            },
        )
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.collection.refresh_from_db()

        # submitted_at should remain unchanged
        self.assertEqual(
            self.collection.submitted_at,
            submitted_at_before,
            "Approval should not change submitted_at timestamp",
        )

        # Latest submitted action should still match
        latest_action = (
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(Collection),
                object_id=self.collection.pk,
                action=ReviewAction.ACTION_SUBMITTED,
            )
            .order_by("-created_at", "-id")
            .first()
        )
        # Check timestamps are very close (within 1 second due to potential timing differences)
        time_diff = abs(self.collection.submitted_at - latest_action.created_at)
        self.assertLess(
            time_diff.total_seconds(),
            1.0,
            "After approval, submitted_at should still match latest submission action (within 1 second)",
        )
