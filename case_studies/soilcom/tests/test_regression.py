"""
Test cases for Collection review action cascade functionality.

ARCHITECTURE NOTE:
Cascade is a VIEW-LEVEL feature, not a model-level feature.
Direct model method calls (e.g., collection.submit_for_review()) do NOT cascade.
Only views using CollectionReviewActionCascadeMixin trigger cascade.

These tests verify that the mixin correctly cascades review actions to
CollectionPropertyValues and AggregatedCollectionPropertyValues when used in
Collection-specific review action views.

Tests use RequestFactory to simulate view-level calls and test the mixin logic
in isolation, bypassing URL routing.
"""

import time
from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory, TestCase
from django.urls import reverse

from case_studies.soilcom.models import (
    AggregatedCollectionPropertyValue,
    Collection,
    CollectionCatchment,
    CollectionPropertyValue,
    CollectionSystem,
    WasteCategory,
    WasteStream,
)
from case_studies.soilcom.views import (
    CollectionApproveItemView,
    CollectionRejectItemView,
    CollectionSubmitForReviewView,
    CollectionWithdrawFromReviewView,
)
from utils.object_management.models import ReviewAction
from utils.properties.models import Property, Unit

User = get_user_model()


class CollectionCascadeMixinTestCase(TestCase):
    """Test the CollectionReviewActionCascadeMixin functionality."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        # Create users
        cls.owner = User.objects.create_user(
            username="owner", email="owner@test.com", password="pass"
        )
        cls.other_owner = User.objects.create_user(
            username="other", email="other@test.com", password="pass"
        )
        cls.staff = User.objects.create_user(
            username="staff", email="staff@test.com", password="pass", is_staff=True
        )

        # Create base data
        cls.catchment = CollectionCatchment.objects.create(
            name="Test Catchment", publication_status="published"
        )
        cls.system = CollectionSystem.objects.create(
            name="Test System", publication_status="published"
        )
        cls.category = WasteCategory.objects.create(
            name="Test Category", publication_status="published"
        )
        cls.stream = WasteStream.objects.create(
            category=cls.category, publication_status="published"
        )

        # Create properties
        cls.prop1 = Property.objects.create(
            name="Property 1", publication_status="published"
        )
        cls.prop2 = Property.objects.create(
            name="Property 2", publication_status="published"
        )
        cls.unit1 = Unit.objects.create(name="Unit 1", publication_status="published")
        cls.unit2 = Unit.objects.create(name="Unit 2", publication_status="published")
        cls.prop1.allowed_units.add(cls.unit1)
        cls.prop2.allowed_units.add(cls.unit2)

        cls.factory = RequestFactory()

    def _create_collection(self, name, owner, status="private", valid_from=None):
        """Helper to create a collection."""
        return Collection.objects.create(
            name=name,
            catchment=self.catchment,
            collection_system=self.system,
            waste_stream=self.stream,
            valid_from=valid_from or date(2020, 1, 1),
            publication_status=status,
            owner=owner,
        )

    def _create_cpv(self, collection, prop, unit, owner, status="private", **kwargs):
        """Helper to create a collection property value."""
        return CollectionPropertyValue.objects.create(
            collection=collection,
            property=prop,
            unit=unit,
            owner=owner,
            publication_status=status,
            year=kwargs.get("year", 2020),
            average=kwargs.get("average", 10.0),
        )

    def _create_acpv(self, collections, prop, unit, owner, status="private", **kwargs):
        """Helper to create an aggregated collection property value."""
        acpv = AggregatedCollectionPropertyValue.objects.create(
            property=prop,
            unit=unit,
            owner=owner,
            publication_status=status,
            year=kwargs.get("year", 2020),
            average=kwargs.get("average", 20.0),
        )
        acpv.collections.set(collections)
        return acpv


class SubmitCascadeMixinTest(CollectionCascadeMixinTestCase):
    """Test submit_for_review cascade via CollectionSubmitForReviewView."""

    def test_submit_cascades_to_owner_cpvs(self):
        """Submit cascades to owner's private and declined CPVs."""
        collection = self._create_collection("C1", self.owner, status="private")
        cpv_private = self._create_cpv(
            collection, self.prop1, self.unit1, self.owner, "private", year=2020
        )
        cpv_declined = self._create_cpv(
            collection, self.prop1, self.unit1, self.owner, "declined", year=2021
        )
        cpv_published = self._create_cpv(
            collection, self.prop1, self.unit1, self.owner, "published", year=2022
        )

        request = self.factory.post("/")
        request.user = self.owner

        view = CollectionSubmitForReviewView()
        view.request = request
        view.object = collection
        view.action_attr_name = "submit_for_review"
        view.post_action_hook(request, "private")

        cpv_private.refresh_from_db()
        cpv_declined.refresh_from_db()
        cpv_published.refresh_from_db()

        self.assertEqual(cpv_private.publication_status, "review")
        self.assertEqual(cpv_declined.publication_status, "review")
        self.assertEqual(cpv_published.publication_status, "published")  # Unchanged

    def test_submit_includes_collaborator_cpvs(self):
        """Submit cascades to all CPVs on owner's collection, including collaborators' CPVs."""
        collection = self._create_collection("C1", self.owner, status="private")
        cpv_owner = self._create_cpv(
            collection, self.prop1, self.unit1, self.owner, "private"
        )
        # Other user contributed a CPV to owner's collection
        cpv_other = self._create_cpv(
            collection, self.prop2, self.unit2, self.other_owner, "private"
        )

        request = self.factory.post("/")
        request.user = self.owner

        view = CollectionSubmitForReviewView()
        view.request = request
        view.object = collection
        view.action_attr_name = "submit_for_review"
        view.post_action_hook(request, "private")

        cpv_owner.refresh_from_db()
        cpv_other.refresh_from_db()

        # Both cascade because they're on the owner's collection
        self.assertEqual(cpv_owner.publication_status, "review")
        self.assertEqual(cpv_other.publication_status, "review")  # Also cascaded

    def test_submit_cascades_to_acpvs(self):
        """Submit cascades to owner's aggregated property values."""
        collection = self._create_collection("C1", self.owner, status="private")
        acpv = self._create_acpv(
            [collection], self.prop1, self.unit1, self.owner, "private"
        )

        request = self.factory.post("/")
        request.user = self.owner

        view = CollectionSubmitForReviewView()
        view.request = request
        view.object = collection
        view.action_attr_name = "submit_for_review"
        view.post_action_hook(request, "private")

        acpv.refresh_from_db()
        self.assertEqual(acpv.publication_status, "review")

    def test_submit_cascades_across_version_chain(self):
        """Submit cascades to CPVs on all versions in the chain."""
        v1 = self._create_collection("V1", self.owner, "published", date(2020, 1, 1))
        v2 = self._create_collection("V2", self.owner, "published", date(2021, 1, 1))
        v3 = self._create_collection("V3", self.owner, "private", date(2022, 1, 1))
        v2.predecessors.add(v1)
        v3.predecessors.add(v2)

        cpv1 = self._create_cpv(v1, self.prop1, self.unit1, self.owner, "private")
        cpv2 = self._create_cpv(v2, self.prop1, self.unit1, self.owner, "declined")
        cpv3 = self._create_cpv(v3, self.prop1, self.unit1, self.owner, "private")

        request = self.factory.post("/")
        request.user = self.owner

        view = CollectionSubmitForReviewView()
        view.request = request
        view.object = v3
        view.action_attr_name = "submit_for_review"
        view.post_action_hook(request, "private")

        cpv1.refresh_from_db()
        cpv2.refresh_from_db()
        cpv3.refresh_from_db()

        self.assertEqual(cpv1.publication_status, "review")
        self.assertEqual(cpv2.publication_status, "review")
        self.assertEqual(cpv3.publication_status, "review")


class WithdrawCascadeMixinTest(CollectionCascadeMixinTestCase):
    """Test withdraw_from_review cascade via CollectionWithdrawFromReviewView."""

    def test_withdraw_cascades_to_owner_cpvs(self):
        """Withdraw cascades to owner's CPVs in review."""
        collection = self._create_collection("C1", self.owner, status="review")
        cpv = self._create_cpv(collection, self.prop1, self.unit1, self.owner, "review")

        request = self.factory.post("/")
        request.user = self.owner

        view = CollectionWithdrawFromReviewView()
        view.request = request
        view.object = collection
        view.action_attr_name = "withdraw_from_review"
        view.post_action_hook(request, "review")

        cpv.refresh_from_db()
        self.assertEqual(cpv.publication_status, "private")

    def test_withdraw_includes_collaborator_cpvs(self):
        """Withdraw cascades to all CPVs on owner's collection, including collaborators'."""
        collection = self._create_collection("C1", self.owner, status="review")
        cpv_owner = self._create_cpv(
            collection, self.prop1, self.unit1, self.owner, "review"
        )
        cpv_other = self._create_cpv(
            collection, self.prop2, self.unit2, self.other_owner, "review"
        )

        request = self.factory.post("/")
        request.user = self.owner

        view = CollectionWithdrawFromReviewView()
        view.request = request
        view.object = collection
        view.action_attr_name = "withdraw_from_review"
        view.post_action_hook(request, "review")

        cpv_owner.refresh_from_db()
        cpv_other.refresh_from_db()

        # Both cascade because they're on the owner's collection
        self.assertEqual(cpv_owner.publication_status, "private")
        self.assertEqual(cpv_other.publication_status, "private")  # Also cascaded


class ApproveCascadeMixinTest(CollectionCascadeMixinTestCase):
    """Test approve cascade via CollectionApproveItemView."""

    def test_approve_cascades_to_all_cpvs_in_review(self):
        """Approve cascades to ALL CPVs in review, regardless of owner."""
        collection = self._create_collection("C1", self.owner, status="review")
        cpv_owner = self._create_cpv(
            collection, self.prop1, self.unit1, self.owner, "review"
        )
        cpv_other = self._create_cpv(
            collection, self.prop2, self.unit2, self.other_owner, "review"
        )

        request = self.factory.post("/")
        request.user = self.staff

        view = CollectionApproveItemView()
        view.request = request
        view.object = collection
        view.action_attr_name = "approve"
        view.post_action_hook(request, "review")

        cpv_owner.refresh_from_db()
        cpv_other.refresh_from_db()

        # Both should be approved
        self.assertEqual(cpv_owner.publication_status, "published")
        self.assertEqual(cpv_other.publication_status, "published")
        self.assertEqual(cpv_owner.approved_by, self.staff)
        self.assertEqual(cpv_other.approved_by, self.staff)

    def test_approve_cascades_to_acpvs(self):
        """Approve cascades to aggregated property values."""
        collection = self._create_collection("C1", self.owner, status="review")
        acpv = self._create_acpv(
            [collection], self.prop1, self.unit1, self.owner, "review"
        )

        request = self.factory.post("/")
        request.user = self.staff

        view = CollectionApproveItemView()
        view.request = request
        view.object = collection
        view.action_attr_name = "approve"
        view.post_action_hook(request, "review")

        acpv.refresh_from_db()
        self.assertEqual(acpv.publication_status, "published")
        self.assertEqual(acpv.approved_by, self.staff)

    def test_approve_cascades_across_version_chain(self):
        """Approve cascades to CPVs on all versions."""
        v1 = self._create_collection("V1", self.owner, "published", date(2020, 1, 1))
        v2 = self._create_collection("V2", self.owner, "review", date(2021, 1, 1))
        v2.predecessors.add(v1)

        cpv1 = self._create_cpv(v1, self.prop1, self.unit1, self.owner, "review")
        cpv2 = self._create_cpv(v2, self.prop1, self.unit1, self.owner, "review")

        request = self.factory.post("/")
        request.user = self.staff

        view = CollectionApproveItemView()
        view.request = request
        view.object = v2
        view.action_attr_name = "approve"
        view.post_action_hook(request, "review")

        cpv1.refresh_from_db()
        cpv2.refresh_from_db()

        self.assertEqual(cpv1.publication_status, "published")
        self.assertEqual(cpv2.publication_status, "published")


class RejectCascadeMixinTest(CollectionCascadeMixinTestCase):
    """Test reject cascade via CollectionRejectItemView."""

    def test_reject_cascades_to_all_cpvs_in_review(self):
        """Reject cascades to ALL CPVs in review, regardless of owner."""
        collection = self._create_collection("C1", self.owner, status="review")
        cpv_owner = self._create_cpv(
            collection, self.prop1, self.unit1, self.owner, "review"
        )
        cpv_other = self._create_cpv(
            collection, self.prop2, self.unit2, self.other_owner, "review"
        )

        request = self.factory.post("/")
        request.user = self.staff

        view = CollectionRejectItemView()
        view.request = request
        view.object = collection
        view.action_attr_name = "reject"
        view.post_action_hook(request, "review")

        cpv_owner.refresh_from_db()
        cpv_other.refresh_from_db()

        # Both should be rejected
        self.assertEqual(cpv_owner.publication_status, "declined")
        self.assertEqual(cpv_other.publication_status, "declined")

    def test_reject_cascades_to_acpvs(self):
        """Reject cascades to aggregated property values."""
        collection = self._create_collection("C1", self.owner, status="review")
        acpv = self._create_acpv(
            [collection], self.prop1, self.unit1, self.owner, "review"
        )

        request = self.factory.post("/")
        request.user = self.staff

        view = CollectionRejectItemView()
        view.request = request
        view.object = collection
        view.action_attr_name = "reject"
        view.post_action_hook(request, "review")

        acpv.refresh_from_db()
        self.assertEqual(acpv.publication_status, "declined")

    def test_reject_cascades_across_version_chain(self):
        """Reject cascades to CPVs on all versions."""
        v1 = self._create_collection("V1", self.owner, "published", date(2020, 1, 1))
        v2 = self._create_collection("V2", self.owner, "review", date(2021, 1, 1))
        v2.predecessors.add(v1)

        cpv1 = self._create_cpv(v1, self.prop1, self.unit1, self.owner, "review")
        cpv2 = self._create_cpv(v2, self.prop1, self.unit1, self.owner, "review")

        request = self.factory.post("/")
        request.user = self.staff

        view = CollectionRejectItemView()
        view.request = request
        view.object = v2
        view.action_attr_name = "reject"
        view.post_action_hook(request, "review")

        cpv1.refresh_from_db()
        cpv2.refresh_from_db()

        self.assertEqual(cpv1.publication_status, "declined")
        self.assertEqual(cpv2.publication_status, "declined")


class ReviewSubmissionConsistencyTests(TestCase):
    """Regression tests ensuring review-submission timestamps remain consistent."""

    def setUp(self):
        self.owner = User.objects.create_user(username="owner")
        self.moderator = User.objects.create_user(username="moderator", is_staff=True)

        content_type = ContentType.objects.get_for_model(Collection)
        permission, _ = Permission.objects.get_or_create(
            codename="can_moderate_collection",
            content_type=content_type,
            defaults={"name": "Can moderate collections"},
        )
        self.moderator.user_permissions.add(permission)

        self.collection = Collection.objects.create(
            name="Test Collection",
            owner=self.owner,
            publication_status=Collection.STATUS_PRIVATE,
        )

    def test_initial_submission_consistency(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse(
                "object_management:submit_for_review",
                kwargs={
                    "content_type_id": ContentType.objects.get_for_model(Collection).pk,
                    "object_id": self.collection.pk,
                },
            ),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        self.collection.refresh_from_db()
        self.assertIsNotNone(self.collection.submitted_at)

        actions = ReviewAction.objects.filter(
            content_type=ContentType.objects.get_for_model(Collection),
            object_id=self.collection.pk,
            action=ReviewAction.ACTION_SUBMITTED,
        )
        self.assertEqual(actions.count(), 1)

        latest_action = actions.order_by("-created_at", "-id").first()
        self.assertIsNotNone(latest_action)

        time_diff = abs(self.collection.submitted_at - latest_action.created_at)
        self.assertLess(time_diff.total_seconds(), 1.0)

    def test_resubmission_consistency(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse(
                "object_management:submit_for_review",
                kwargs={
                    "content_type_id": ContentType.objects.get_for_model(Collection).pk,
                    "object_id": self.collection.pk,
                },
            ),
            follow=True,
        )
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

        response = self.client.post(
            reverse(
                "object_management:withdraw_from_review",
                kwargs={
                    "content_type_id": ContentType.objects.get_for_model(Collection).pk,
                    "object_id": self.collection.pk,
                },
            ),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.collection.refresh_from_db()
        self.assertIsNone(self.collection.submitted_at)

        time.sleep(0.01)

        response = self.client.post(
            reverse(
                "object_management:submit_for_review",
                kwargs={
                    "content_type_id": ContentType.objects.get_for_model(Collection).pk,
                    "object_id": self.collection.pk,
                },
            ),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.collection.refresh_from_db()

        latest_action = (
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(Collection),
                object_id=self.collection.pk,
                action=ReviewAction.ACTION_SUBMITTED,
            )
            .order_by("-created_at", "-id")
            .first()
        )

        self.assertIsNotNone(self.collection.submitted_at)
        self.assertIsNotNone(latest_action)
        time_diff = abs(self.collection.submitted_at - latest_action.created_at)
        self.assertLess(time_diff.total_seconds(), 1.0)

        self.assertGreater(self.collection.submitted_at, initial_submitted_at)
        self.assertGreater(latest_action.created_at, initial_action.created_at)

    def test_review_ui_shows_latest_submission(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse(
                "object_management:submit_for_review",
                kwargs={
                    "content_type_id": ContentType.objects.get_for_model(Collection).pk,
                    "object_id": self.collection.pk,
                },
            ),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        time.sleep(0.01)

        response = self.client.post(
            reverse(
                "object_management:withdraw_from_review",
                kwargs={
                    "content_type_id": ContentType.objects.get_for_model(Collection).pk,
                    "object_id": self.collection.pk,
                },
            ),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        time.sleep(0.01)

        response = self.client.post(
            reverse(
                "object_management:submit_for_review",
                kwargs={
                    "content_type_id": ContentType.objects.get_for_model(Collection).pk,
                    "object_id": self.collection.pk,
                },
            ),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.collection.refresh_from_db()

        self.client.force_login(self.moderator)
        response = self.client.get(
            reverse(
                "object_management:review_item_detail",
                kwargs={
                    "content_type_id": ContentType.objects.get_for_model(Collection).pk,
                    "object_id": self.collection.pk,
                },
            )
        )
        self.assertEqual(response.status_code, 200)

        self.assertIn("review_submitted_action", response.context)
        submitted_action = response.context["review_submitted_action"]
        self.assertIsNotNone(submitted_action)
        self.assertEqual(submitted_action.action, ReviewAction.ACTION_SUBMITTED)

        latest_action = (
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(Collection),
                object_id=self.collection.pk,
                action=ReviewAction.ACTION_SUBMITTED,
            )
            .order_by("-created_at", "-id")
            .first()
        )
        self.assertEqual(submitted_action.pk, latest_action.pk)

        time_diff = abs(submitted_action.created_at - self.collection.submitted_at)
        self.assertLess(time_diff.total_seconds(), 1.0)

    def test_approval_preserves_submission_timestamp(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse(
                "object_management:submit_for_review",
                kwargs={
                    "content_type_id": ContentType.objects.get_for_model(Collection).pk,
                    "object_id": self.collection.pk,
                },
            ),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.collection.refresh_from_db()
        submitted_at_before = self.collection.submitted_at

        self.client.force_login(self.moderator)
        response = self.client.post(
            reverse(
                "object_management:approve_item",
                kwargs={
                    "content_type_id": ContentType.objects.get_for_model(Collection).pk,
                    "object_id": self.collection.pk,
                },
            ),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.collection.refresh_from_db()

        self.assertEqual(self.collection.submitted_at, submitted_at_before)

        latest_action = (
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(Collection),
                object_id=self.collection.pk,
                action=ReviewAction.ACTION_SUBMITTED,
            )
            .order_by("-created_at", "-id")
            .first()
        )
        time_diff = abs(self.collection.submitted_at - latest_action.created_at)
        self.assertLess(time_diff.total_seconds(), 1.0)
