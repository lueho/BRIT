import datetime

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from bibliography.models import Source
from sources.waste_collection.models import Collection, WasteCategory
from utils.properties.models import Property

from ..models import ReviewAction, UserCreatedObject


class ReviewWorkflowModelTests(TestCase):
    """Test the model methods for the review workflow."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner")
        cls.moderator = User.objects.create_user(username="moderator")
        cls.regular_user = User.objects.create_user(username="regular")

        # Add moderator permissions
        content_type = ContentType.objects.get_for_model(Collection)
        permission, _ = Permission.objects.get_or_create(
            codename="can_moderate_collection",
            content_type=content_type,
            defaults={"name": "Can moderate collections"},
        )
        cls.moderator.user_permissions.add(permission)

        # Create a test collection
        cls.category = WasteCategory.objects.create(
            name="Test Category",
            owner=cls.owner,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )

        cls.source = Source.objects.create(
            owner=cls.owner,
            title="Review Workflow Model Source",
        )

    def setUp(self):
        # The collection's review state is the mutation under test, so it is
        # created per test instead of shared via setUpTestData.
        self.collection = Collection.objects.create(
            name="Test Collection",
            owner=self.owner,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )
        self.collection.sources.add(self.source)

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

    def test_approve_requires_the_approving_user(self):
        """approve() must always record who published the object."""
        self.collection.submit_for_review()

        with self.assertRaisesMessage(
            ValidationError, "approve() requires the approving user"
        ):
            self.collection.approve()

        self.collection.refresh_from_db()
        self.assertEqual(
            self.collection.publication_status, UserCreatedObject.STATUS_REVIEW
        )
        self.assertIsNone(self.collection.approved_at)
        self.assertIsNone(self.collection.approved_by)

    def test_clean_rejects_transition_to_published_without_approval(self):
        self.collection.publication_status = UserCreatedObject.STATUS_PUBLISHED

        with self.assertRaises(ValidationError) as context:
            self.collection.clean()

        self.assertIn("approved_at", str(context.exception))
        self.assertIn("approved_by", str(context.exception))

    def test_clean_rejects_transition_to_published_with_partial_approval(self):
        self.collection.publication_status = UserCreatedObject.STATUS_PUBLISHED
        self.collection.approved_at = timezone.now()

        with self.assertRaises(ValidationError) as context:
            self.collection.clean()

        self.assertIn("approved_by", str(context.exception))

    def test_clean_allows_publishing_transition_with_approval_metadata(self):
        self.collection.publication_status = UserCreatedObject.STATUS_PUBLISHED
        self.collection.approved_at = timezone.now()
        self.collection.approved_by = self.moderator

        self.collection.clean()

    def test_clean_allows_updates_to_already_published_objects(self):
        """Rows already stored as published (e.g. pre-workflow data) stay editable."""
        Collection.objects.filter(pk=self.collection.pk).update(
            publication_status=UserCreatedObject.STATUS_PUBLISHED
        )
        published = Collection.objects.get(pk=self.collection.pk)
        self.assertIsNone(published.approved_at)
        self.assertIsNone(published.approved_by)

        published.name = "Renamed collection"
        published.clean()

    def test_direct_create_as_published_stamps_approval_metadata(self):
        """ORM saves bypass clean(), so save() must still record approval."""
        category = WasteCategory.objects.create(
            name="Directly published",
            owner=self.owner,
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
        )

        category.refresh_from_db()
        self.assertIsNotNone(category.approved_at)
        self.assertEqual(category.approved_by, self.owner)

    def test_direct_save_publishing_with_update_fields_stamps_approval(self):
        self.collection.publication_status = UserCreatedObject.STATUS_PUBLISHED
        self.collection.save(update_fields=("publication_status",))

        self.collection.refresh_from_db()
        self.assertEqual(
            self.collection.publication_status, UserCreatedObject.STATUS_PUBLISHED
        )
        self.assertIsNotNone(self.collection.approved_at)
        self.assertEqual(self.collection.approved_by, self.owner)

    def test_partial_publish_save_writes_explicit_approval_metadata(self):
        approved_at = timezone.now() - datetime.timedelta(days=1)
        self.collection.publication_status = UserCreatedObject.STATUS_PUBLISHED
        self.collection.approved_at = approved_at
        self.collection.approved_by = self.moderator
        self.collection.save(update_fields=["publication_status"])

        self.collection.refresh_from_db()
        self.assertEqual(self.collection.approved_at, approved_at)
        self.assertEqual(self.collection.approved_by, self.moderator)

    def test_direct_publish_keeps_existing_approval_metadata(self):
        approved_at = timezone.now() - datetime.timedelta(days=1)
        category = WasteCategory.objects.create(
            name="Explicitly approved",
            owner=self.owner,
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
            approved_at=approved_at,
            approved_by=self.moderator,
        )

        category.refresh_from_db()
        self.assertEqual(category.approved_at, approved_at)
        self.assertEqual(category.approved_by, self.moderator)

    def test_save_of_non_published_object_leaves_approval_empty(self):
        self.collection.name = "Renamed private collection"
        self.collection.save()

        self.collection.refresh_from_db()
        self.assertIsNone(self.collection.approved_at)
        self.assertIsNone(self.collection.approved_by)

    def test_save_of_already_published_object_does_not_stamp(self):
        """Pre-workflow rows are backfilled by migration, not by unrelated edits."""
        Collection.objects.filter(pk=self.collection.pk).update(
            publication_status=UserCreatedObject.STATUS_PUBLISHED
        )
        published = Collection.objects.get(pk=self.collection.pk)

        published.name = "Renamed collection"
        published.save()

        published.refresh_from_db()
        self.assertIsNone(published.approved_at)
        self.assertIsNone(published.approved_by)

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

    def test_stale_review_object_cannot_overwrite_a_concurrent_withdrawal(self):
        self.collection.submit_for_review()
        stale_collection = Collection.objects.get(pk=self.collection.pk)

        concurrent_collection = Collection.objects.get(pk=self.collection.pk)
        concurrent_collection.withdraw_from_review()

        with self.assertRaisesMessage(
            ValidationError, "Only objects in review can be approved."
        ):
            stale_collection.approve(user=self.moderator)

        self.collection.refresh_from_db()
        self.assertEqual(
            self.collection.publication_status, UserCreatedObject.STATUS_PRIVATE
        )

    def test_stale_review_object_cannot_bypass_a_direct_status_change(self):
        self.collection.publication_status = UserCreatedObject.STATUS_REVIEW
        self.collection.save()
        stale_collection = Collection.objects.get(pk=self.collection.pk)

        Collection.objects.filter(pk=self.collection.pk).update(
            publication_status=UserCreatedObject.STATUS_PRIVATE
        )

        with self.assertRaisesMessage(
            ValidationError, "Only objects in review can be approved."
        ):
            stale_collection.approve(user=self.moderator)

        self.collection.refresh_from_db()
        self.assertEqual(
            self.collection.publication_status, UserCreatedObject.STATUS_PRIVATE
        )

    def test_submit_for_review_preserves_a_concurrent_content_edit(self):
        stale_collection = Collection.objects.get(pk=self.collection.pk)
        Collection.objects.filter(pk=self.collection.pk).update(
            description="Concurrent edit"
        )

        stale_collection.submit_for_review()

        self.collection.refresh_from_db()
        self.assertEqual(self.collection.description, "Concurrent edit")
        self.assertEqual(
            self.collection.publication_status, UserCreatedObject.STATUS_REVIEW
        )

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


class BreadcrumbLabelModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="breadcrumb-model-owner")

    def test_plural_breadcrumb_label_uses_model_metadata(self):
        self.assertEqual(Property.get_breadcrumb_plural_label(), "properties")

    def test_object_breadcrumb_label_uses_string_representation(self):
        source = Source.objects.create(
            owner=self.owner,
            title="Canonical breadcrumb source",
            citation_key="CanonicalKey",
        )

        self.assertEqual(source.get_breadcrumb_object_label(), str(source))
