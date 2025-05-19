import datetime

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from case_studies.soilcom.models import Collection, WasteCategory
from utils.models import UserCreatedObject
from utils.permissions import UserCreatedObjectPermission


class ReviewWorkflowModelTests(TestCase):
    """Test the model methods for the review workflow."""

    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="password")
        self.moderator = User.objects.create_user(
            username="moderator", password="password"
        )
        self.regular_user = User.objects.create_user(
            username="regular", password="password"
        )

        # Add moderator permissions
        content_type = ContentType.objects.get_for_model(Collection)
        permission = Permission.objects.create(
            codename="can_moderate_collection",
            name="Can moderate collections",
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
            self.collection.publication_status, UserCreatedObject.STATUS_PRIVATE
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


class ReviewWorkflowPermissionTests(TestCase):
    """Test the permissions for the review workflow."""

    def setUp(self):
        # Create users
        self.owner = User.objects.create_user(username="owner", password="password")
        self.moderator = User.objects.create_user(
            username="moderator", password="password"
        )
        self.regular_user = User.objects.create_user(
            username="regular", password="password"
        )

        # Add moderator permissions
        content_type = ContentType.objects.get_for_model(Collection)
        permission = Permission.objects.create(
            codename="can_moderate_collection",
            name="Can moderate collections",
            content_type=content_type,
        )
        self.moderator.user_permissions.add(permission)

        # Create test collections in different states
        self.private_collection = Collection.objects.create(
            name="Private Collection",
            owner=self.owner,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )

        self.review_collection = Collection.objects.create(
            name="Review Collection",
            owner=self.owner,
            publication_status=UserCreatedObject.STATUS_REVIEW,
        )

        self.published_collection = Collection.objects.create(
            name="Published Collection",
            owner=self.owner,
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
        )

        # Create permission checker
        self.permission_checker = UserCreatedObjectPermission()
        self.factory = RequestFactory()

    def test_submit_permission(self):
        """Test permission to submit an object for review."""
        # Owner should be able to submit their private object
        request = self.factory.post("/")
        request.user = self.owner
        self.assertTrue(
            self.permission_checker.has_submit_permission(
                request, self.private_collection
            )
        )

        # Regular user should not be able to submit someone else's private object
        request.user = self.regular_user
        self.assertFalse(
            self.permission_checker.has_submit_permission(
                request, self.private_collection
            )
        )

        # No one should be able to submit an object already in review
        request.user = self.owner
        self.assertFalse(
            self.permission_checker.has_submit_permission(
                request, self.review_collection
            )
        )

    def test_withdraw_permission(self):
        """Test permission to withdraw an object from review."""
        # Owner should be able to withdraw their object from review
        request = self.factory.post("/")
        request.user = self.owner
        self.assertTrue(
            self.permission_checker.has_withdraw_permission(
                request, self.review_collection
            )
        )

        # Regular user should not be able to withdraw someone else's object
        request.user = self.regular_user
        self.assertFalse(
            self.permission_checker.has_withdraw_permission(
                request, self.review_collection
            )
        )

        # No one should be able to withdraw a private object
        request.user = self.owner
        self.assertFalse(
            self.permission_checker.has_withdraw_permission(
                request, self.private_collection
            )
        )

    def test_approve_permission(self):
        """Test permission to approve an object."""
        # Moderator should be able to approve an object in review
        request = self.factory.post("/")
        request.user = self.moderator
        self.assertTrue(
            self.permission_checker.has_approve_permission(
                request, self.review_collection
            )
        )

        # Owner should not be able to approve their own object
        request.user = self.owner
        self.assertFalse(
            self.permission_checker.has_approve_permission(
                request, self.review_collection
            )
        )

        # Regular user should not be able to approve any object
        request.user = self.regular_user
        self.assertFalse(
            self.permission_checker.has_approve_permission(
                request, self.review_collection
            )
        )

        # No one should be able to approve a private object
        request.user = self.moderator
        self.assertFalse(
            self.permission_checker.has_approve_permission(
                request, self.private_collection
            )
        )

    def test_reject_permission(self):
        """Test permission to reject an object."""
        # Moderator should be able to reject an object in review
        request = self.factory.post("/")
        request.user = self.moderator
        self.assertTrue(
            self.permission_checker.has_reject_permission(
                request, self.review_collection
            )
        )

        # Owner should not be able to reject their own object
        request.user = self.owner
        self.assertFalse(
            self.permission_checker.has_reject_permission(
                request, self.review_collection
            )
        )

        # Regular user should not be able to reject any object
        request.user = self.regular_user
        self.assertFalse(
            self.permission_checker.has_reject_permission(
                request, self.review_collection
            )
        )

        # No one should be able to reject a private object
        request.user = self.moderator
        self.assertFalse(
            self.permission_checker.has_reject_permission(
                request, self.private_collection
            )
        )


class ReviewWorkflowViewTests(TestCase):
    """Test the views for the review workflow."""

    def setUp(self):
        # Create users
        self.owner = User.objects.create_user(username="owner", password="password")
        self.moderator = User.objects.create_user(
            username="moderator", password="password"
        )
        self.regular_user = User.objects.create_user(
            username="regular", password="password"
        )

        # Add moderator permissions
        content_type = ContentType.objects.get_for_model(Collection)
        permission = Permission.objects.create(
            codename="can_moderate_collection",
            name="Can moderate collections",
            content_type=content_type,
        )
        self.moderator.user_permissions.add(permission)

        # Create test collections in different states
        self.private_collection = Collection.objects.create(
            name="Private Collection",
            owner=self.owner,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )

        self.review_collection = Collection.objects.create(
            name="Review Collection",
            owner=self.owner,
            publication_status=UserCreatedObject.STATUS_REVIEW,
        )

        # Create clients
        self.owner_client = Client()
        self.owner_client.login(username="owner", password="password")

        self.moderator_client = Client()
        self.moderator_client.login(username="moderator", password="password")

        self.regular_client = Client()
        self.regular_client.login(username="regular", password="password")

        # Get content type for URLs
        self.content_type_id = ContentType.objects.get_for_model(Collection).id

    def test_submit_for_review_view(self):
        """Test the submit for review view."""
        url = reverse(
            "moderation:submit_for_review",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.private_collection.id,
            },
        )

        # Owner should be able to submit their private object
        response = self.owner_client.post(url)
        self.assertEqual(response.status_code, 302)  # Redirect after success

        # Refresh from database
        self.private_collection.refresh_from_db()
        self.assertEqual(
            self.private_collection.publication_status, UserCreatedObject.STATUS_REVIEW
        )

        # Regular user should not be able to submit someone else's private object
        self.private_collection.publication_status = UserCreatedObject.STATUS_PRIVATE
        self.private_collection.save()

        response = self.regular_client.post(url)
        self.assertEqual(response.status_code, 403)  # Permission denied

        # Refresh from database
        self.private_collection.refresh_from_db()
        self.assertEqual(
            self.private_collection.publication_status, UserCreatedObject.STATUS_PRIVATE
        )

    def test_withdraw_from_review_view(self):
        """Test the withdraw from review view."""
        url = reverse(
            "moderation:withdraw_from_review",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.review_collection.id,
            },
        )

        # Owner should be able to withdraw their object from review
        response = self.owner_client.post(url)
        self.assertEqual(response.status_code, 302)  # Redirect after success

        # Refresh from database
        self.review_collection.refresh_from_db()
        self.assertEqual(
            self.review_collection.publication_status, UserCreatedObject.STATUS_PRIVATE
        )

        # Regular user should not be able to withdraw someone else's object
        self.review_collection.publication_status = UserCreatedObject.STATUS_REVIEW
        self.review_collection.save()

        response = self.regular_client.post(url)
        self.assertEqual(response.status_code, 403)  # Permission denied

        # Refresh from database
        self.review_collection.refresh_from_db()
        self.assertEqual(
            self.review_collection.publication_status, UserCreatedObject.STATUS_REVIEW
        )

    def test_approve_view(self):
        """Test the approve view."""
        url = reverse(
            "moderation:approve_item",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.review_collection.id,
            },
        )

        # Moderator should be able to approve an object in review
        response = self.moderator_client.post(url)
        self.assertEqual(response.status_code, 302)  # Redirect after success

        # Refresh from database
        self.review_collection.refresh_from_db()
        self.assertEqual(
            self.review_collection.publication_status,
            UserCreatedObject.STATUS_PUBLISHED,
        )
        self.assertEqual(self.review_collection.approved_by, self.moderator)

        # Regular user should not be able to approve any object
        self.review_collection.publication_status = UserCreatedObject.STATUS_REVIEW
        self.review_collection.approved_by = None
        self.review_collection.approved_at = None
        self.review_collection.save()

        response = self.regular_client.post(url)
        self.assertEqual(response.status_code, 403)  # Permission denied

        # Refresh from database
        self.review_collection.refresh_from_db()
        self.assertEqual(
            self.review_collection.publication_status, UserCreatedObject.STATUS_REVIEW
        )
        self.assertIsNone(self.review_collection.approved_by)

    def test_reject_view(self):
        """Test the reject view."""
        url = reverse(
            "moderation:reject_item",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.review_collection.id,
            },
        )

        # Moderator should be able to reject an object in review
        response = self.moderator_client.post(url)
        self.assertEqual(response.status_code, 302)  # Redirect after success

        # Refresh from database
        self.review_collection.refresh_from_db()
        self.assertEqual(
            self.review_collection.publication_status, UserCreatedObject.STATUS_PRIVATE
        )

        # Regular user should not be able to reject any object
        self.review_collection.publication_status = UserCreatedObject.STATUS_REVIEW
        self.review_collection.save()

        response = self.regular_client.post(url)
        self.assertEqual(response.status_code, 403)  # Permission denied

        # Refresh from database
        self.review_collection.refresh_from_db()
        self.assertEqual(
            self.review_collection.publication_status, UserCreatedObject.STATUS_REVIEW
        )

    def test_dashboard_view(self):
        """Test the review dashboard view."""
        url = reverse("moderation:review_dashboard")

        # Moderator should be able to see the dashboard
        response = self.moderator_client.get(url)
        self.assertEqual(response.status_code, 200)

        # Dashboard should contain objects in review
        expected_name = self.review_collection.construct_name()
        if expected_name not in response.content.decode():
            print("DASHBOARD HTML FOR DEBUGGING:")
            print(response.content.decode())
        self.assertContains(response, expected_name)

        # Regular user should be able to access the dashboard but see no items
        response = self.regular_client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Review Collection")
