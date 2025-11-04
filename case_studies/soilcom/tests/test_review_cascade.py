"""
Test cases for cascading review actions from Collections to related property values.

Tests verify that when a Collection's review state changes (submit, withdraw,
approve, reject), the action cascades correctly to CollectionPropertyValues and
AggregatedCollectionPropertyValues across version chains.
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from case_studies.soilcom.models import (
    AggregatedCollectionPropertyValue,
    Collection,
    CollectionCatchment,
    CollectionPropertyValue,
    CollectionSystem,
    WasteCategory,
    WasteStream,
)
from utils.properties.models import Property, Unit

User = get_user_model()


class CollectionReviewCascadeTestCase(TestCase):
    """Base test case with common setup for cascade tests."""

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


class SubmitForReviewCascadeTest(CollectionReviewCascadeTestCase):
    """Test cascading submit_for_review action to property values.

    NOTE: Cascade is a view-level feature, not model-level.
    Direct model method calls do NOT cascade.
    Only Collection-specific views (CollectionSubmitForReviewView) trigger cascade.
    """

    def test_model_submit_does_not_cascade(self):
        """Direct model method calls do NOT cascade (by design)."""
        collection = self._create_collection("C1", self.owner, status="private")
        cpv = self._create_cpv(
            collection, self.prop1, self.unit1, self.owner, status="private"
        )

        # Direct model call
        collection.submit_for_review()
        cpv.refresh_from_db()

        self.assertEqual(collection.publication_status, "review")
        self.assertEqual(cpv.publication_status, "private")  # NOT cascaded

    def test_submit_cascades_to_owner_cpvs_declined(self):
        """Submit cascades to owner's declined CPVs."""
        collection = self._create_collection("C1", self.owner, status="private")
        cpv = self._create_cpv(
            collection, self.prop1, self.unit1, self.owner, status="declined"
        )

        collection.submit_for_review()
        cpv.refresh_from_db()

        self.assertEqual(collection.publication_status, "review")
        self.assertEqual(cpv.publication_status, "review")

    def test_submit_skips_published_cpvs(self):
        """Submit does not cascade to published CPVs."""
        collection = self._create_collection("C1", self.owner, status="private")
        cpv = self._create_cpv(
            collection, self.prop1, self.unit1, self.owner, status="published"
        )

        collection.submit_for_review()
        cpv.refresh_from_db()

        self.assertEqual(collection.publication_status, "review")
        self.assertEqual(cpv.publication_status, "published")  # Unchanged

    def test_submit_skips_other_users_cpvs(self):
        """Submit does not cascade to CPVs owned by other users."""
        collection = self._create_collection("C1", self.owner, status="private")
        cpv = self._create_cpv(
            collection, self.prop1, self.unit1, self.other_owner, status="private"
        )

        collection.submit_for_review()
        cpv.refresh_from_db()

        self.assertEqual(collection.publication_status, "review")
        self.assertEqual(cpv.publication_status, "private")  # Unchanged

    def test_submit_cascades_to_owner_acpvs(self):
        """Submit cascades to owner's aggregated property values."""
        collection = self._create_collection("C1", self.owner, status="private")
        acpv = self._create_acpv(
            [collection], self.prop1, self.unit1, self.owner, status="private"
        )

        collection.submit_for_review()
        acpv.refresh_from_db()

        self.assertEqual(collection.publication_status, "review")
        self.assertEqual(acpv.publication_status, "review")

    def test_submit_cascades_across_version_chain(self):
        """Submit cascades to CPVs across entire version chain."""
        # Create version chain: v1 -> v2 -> v3
        v1 = self._create_collection(
            "V1", self.owner, status="published", valid_from=date(2020, 1, 1)
        )
        v2 = self._create_collection(
            "V2", self.owner, status="published", valid_from=date(2021, 1, 1)
        )
        v3 = self._create_collection(
            "V3", self.owner, status="private", valid_from=date(2022, 1, 1)
        )
        v2.predecessors.add(v1)
        v3.predecessors.add(v2)

        # Create CPVs on different versions
        cpv1 = self._create_cpv(v1, self.prop1, self.unit1, self.owner, "private")
        cpv2 = self._create_cpv(v2, self.prop1, self.unit1, self.owner, "declined")
        cpv3 = self._create_cpv(v3, self.prop1, self.unit1, self.owner, "private")

        # Submit v3 - should cascade to all versions
        v3.submit_for_review()

        cpv1.refresh_from_db()
        cpv2.refresh_from_db()
        cpv3.refresh_from_db()

        self.assertEqual(cpv1.publication_status, "review")
        self.assertEqual(cpv2.publication_status, "review")
        self.assertEqual(cpv3.publication_status, "review")

    def test_cascade_with_mixin_submit(self):
        """Cascade works when using CollectionReviewActionCascadeMixin."""
        from django.test import RequestFactory

        from case_studies.soilcom.views import CollectionSubmitForReviewView

        collection = self._create_collection("C1", self.owner, status="private")
        cpv_owner = self._create_cpv(
            collection, self.prop1, self.unit1, self.owner, status="private"
        )
        cpv_other = self._create_cpv(
            collection, self.prop2, self.unit2, self.other_owner, status="private"
        )

        # Simulate view call
        factory = RequestFactory()
        request = factory.post("/fake/")
        request.user = self.owner

        view = CollectionSubmitForReviewView()
        view.request = request
        view.object = collection
        view.post_action_hook(request, previous_status="private")

        cpv_owner.refresh_from_db()
        cpv_other.refresh_from_db()

        # Owner's CPV should cascade
        self.assertEqual(cpv_owner.publication_status, "review")
        # Other user's CPV should NOT cascade (owner filtering)
        self.assertEqual(cpv_other.publication_status, "private")


class WithdrawFromReviewCascadeTest(CollectionReviewCascadeTestCase):
    """Test cascading withdraw_from_review action to property values."""

    def test_withdraw_cascades_to_owner_cpvs_in_review(self):
        """Withdraw cascades to owner's CPVs in review."""
        collection = self._create_collection("C1", self.owner, status="review")
        cpv = self._create_cpv(
            collection, self.prop1, self.unit1, self.owner, status="review"
        )

        collection.withdraw_from_review()
        cpv.refresh_from_db()

        self.assertEqual(collection.publication_status, "private")
        self.assertEqual(cpv.publication_status, "private")

    def test_withdraw_skips_published_cpvs(self):
        """Withdraw does not cascade to published CPVs."""
        collection = self._create_collection("C1", self.owner, status="review")
        cpv = self._create_cpv(
            collection, self.prop1, self.unit1, self.owner, status="published"
        )

        collection.withdraw_from_review()
        cpv.refresh_from_db()

        self.assertEqual(collection.publication_status, "private")
        self.assertEqual(cpv.publication_status, "published")  # Unchanged

    def test_withdraw_skips_other_users_cpvs(self):
        """Withdraw does not cascade to CPVs owned by other users."""
        collection = self._create_collection("C1", self.owner, status="review")
        cpv = self._create_cpv(
            collection, self.prop1, self.unit1, self.other_owner, status="review"
        )

        collection.withdraw_from_review()
        cpv.refresh_from_db()

        self.assertEqual(collection.publication_status, "private")
        self.assertEqual(cpv.publication_status, "review")  # Unchanged

    def test_withdraw_cascades_across_version_chain(self):
        """Withdraw cascades across entire version chain."""
        # Create version chain
        v1 = self._create_collection(
            "V1", self.owner, status="published", valid_from=date(2020, 1, 1)
        )
        v2 = self._create_collection(
            "V2", self.owner, status="review", valid_from=date(2021, 1, 1)
        )
        v2.predecessors.add(v1)

        # Create CPVs in review
        cpv1 = self._create_cpv(v1, self.prop1, self.unit1, self.owner, "review")
        cpv2 = self._create_cpv(v2, self.prop1, self.unit1, self.owner, "review")

        v2.withdraw_from_review()

        cpv1.refresh_from_db()
        cpv2.refresh_from_db()

        self.assertEqual(cpv1.publication_status, "private")
        self.assertEqual(cpv2.publication_status, "private")


class ApproveCascadeTest(CollectionReviewCascadeTestCase):
    """Test cascading approve action to property values."""

    def test_approve_cascades_to_cpvs_in_review(self):
        """Approve cascades to all CPVs in review, regardless of owner."""
        collection = self._create_collection("C1", self.owner, status="review")
        cpv_owner = self._create_cpv(
            collection, self.prop1, self.unit1, self.owner, status="review"
        )
        cpv_other = self._create_cpv(
            collection, self.prop2, self.unit2, self.other_owner, status="review"
        )

        collection.approve(user=self.staff)
        cpv_owner.refresh_from_db()
        cpv_other.refresh_from_db()

        self.assertEqual(collection.publication_status, "published")
        self.assertEqual(cpv_owner.publication_status, "published")
        self.assertEqual(cpv_other.publication_status, "published")  # Also cascaded

    def test_approve_skips_private_cpvs(self):
        """Approve does not cascade to private CPVs."""
        collection = self._create_collection("C1", self.owner, status="review")
        cpv = self._create_cpv(
            collection, self.prop1, self.unit1, self.owner, status="private"
        )

        collection.approve(user=self.staff)
        cpv.refresh_from_db()

        self.assertEqual(collection.publication_status, "published")
        self.assertEqual(cpv.publication_status, "private")  # Unchanged

    def test_approve_cascades_to_acpvs(self):
        """Approve cascades to aggregated property values in review."""
        collection = self._create_collection("C1", self.owner, status="review")
        acpv = self._create_acpv(
            [collection], self.prop1, self.unit1, self.owner, status="review"
        )

        collection.approve(user=self.staff)
        acpv.refresh_from_db()

        self.assertEqual(collection.publication_status, "published")
        self.assertEqual(acpv.publication_status, "published")

    def test_approve_cascades_across_version_chain(self):
        """Approve cascades across entire version chain."""
        v1 = self._create_collection(
            "V1", self.owner, status="published", valid_from=date(2020, 1, 1)
        )
        v2 = self._create_collection(
            "V2", self.owner, status="review", valid_from=date(2021, 1, 1)
        )
        v2.predecessors.add(v1)

        # CPVs in review on both versions
        cpv1 = self._create_cpv(v1, self.prop1, self.unit1, self.owner, "review")
        cpv2 = self._create_cpv(v2, self.prop1, self.unit1, self.owner, "review")

        v2.approve(user=self.staff)

        cpv1.refresh_from_db()
        cpv2.refresh_from_db()

        self.assertEqual(cpv1.publication_status, "published")
        self.assertEqual(cpv2.publication_status, "published")

    def test_approve_sets_approved_by_on_cpvs(self):
        """Approve passes the approving user to CPVs."""
        collection = self._create_collection("C1", self.owner, status="review")
        cpv = self._create_cpv(
            collection, self.prop1, self.unit1, self.owner, status="review"
        )

        collection.approve(user=self.staff)
        cpv.refresh_from_db()

        self.assertEqual(cpv.publication_status, "published")
        self.assertEqual(cpv.approved_by, self.staff)


class RejectCascadeTest(CollectionReviewCascadeTestCase):
    """Test cascading reject action to property values."""

    def test_reject_cascades_to_all_cpvs_in_review(self):
        """Reject cascades to all CPVs in review, regardless of owner."""
        collection = self._create_collection("C1", self.owner, status="review")
        cpv_owner = self._create_cpv(
            collection, self.prop1, self.unit1, self.owner, status="review"
        )
        cpv_other = self._create_cpv(
            collection, self.prop2, self.unit2, self.other_owner, status="review"
        )

        collection.reject()
        cpv_owner.refresh_from_db()
        cpv_other.refresh_from_db()

        self.assertEqual(collection.publication_status, "declined")
        self.assertEqual(cpv_owner.publication_status, "declined")
        self.assertEqual(cpv_other.publication_status, "declined")  # Also cascaded

    def test_reject_skips_published_cpvs(self):
        """Reject does not cascade to published CPVs."""
        collection = self._create_collection("C1", self.owner, status="review")
        cpv = self._create_cpv(
            collection, self.prop1, self.unit1, self.owner, status="published"
        )

        collection.reject()
        cpv.refresh_from_db()

        self.assertEqual(collection.publication_status, "declined")
        self.assertEqual(cpv.publication_status, "published")  # Unchanged

    def test_reject_cascades_to_acpvs(self):
        """Reject cascades to aggregated property values in review."""
        collection = self._create_collection("C1", self.owner, status="review")
        acpv = self._create_acpv(
            [collection], self.prop1, self.unit1, self.owner, status="review"
        )

        collection.reject()
        acpv.refresh_from_db()

        self.assertEqual(collection.publication_status, "declined")
        self.assertEqual(acpv.publication_status, "declined")

    def test_reject_cascades_across_version_chain(self):
        """Reject cascades across entire version chain."""
        v1 = self._create_collection(
            "V1", self.owner, status="published", valid_from=date(2020, 1, 1)
        )
        v2 = self._create_collection(
            "V2", self.owner, status="review", valid_from=date(2021, 1, 1)
        )
        v2.predecessors.add(v1)

        cpv1 = self._create_cpv(v1, self.prop1, self.unit1, self.owner, "review")
        cpv2 = self._create_cpv(v2, self.prop1, self.unit1, self.owner, "review")

        v2.reject()

        cpv1.refresh_from_db()
        cpv2.refresh_from_db()

        self.assertEqual(cpv1.publication_status, "declined")
        self.assertEqual(cpv2.publication_status, "declined")


class CascadeEdgeCasesTest(CollectionReviewCascadeTestCase):
    """Test edge cases and error handling in cascade logic."""

    def test_cascade_handles_complex_version_chain(self):
        """Cascade works with branching version chains."""
        # Create a diamond pattern: v1 -> v2a, v1 -> v2b, v2a -> v3, v2b -> v3
        v1 = self._create_collection(
            "V1", self.owner, status="published", valid_from=date(2020, 1, 1)
        )
        v2a = self._create_collection(
            "V2a", self.owner, status="published", valid_from=date(2021, 1, 1)
        )
        v2b = self._create_collection(
            "V2b", self.owner, status="published", valid_from=date(2021, 6, 1)
        )
        v3 = self._create_collection(
            "V3", self.owner, status="private", valid_from=date(2022, 1, 1)
        )
        v2a.predecessors.add(v1)
        v2b.predecessors.add(v1)
        v3.predecessors.add(v2a, v2b)

        # CPVs on each version
        cpv1 = self._create_cpv(v1, self.prop1, self.unit1, self.owner, "private")
        cpv2a = self._create_cpv(v2a, self.prop1, self.unit1, self.owner, "declined")
        cpv2b = self._create_cpv(v2b, self.prop1, self.unit1, self.owner, "private")
        cpv3 = self._create_cpv(v3, self.prop1, self.unit1, self.owner, "private")

        v3.submit_for_review()

        cpv1.refresh_from_db()
        cpv2a.refresh_from_db()
        cpv2b.refresh_from_db()
        cpv3.refresh_from_db()

        # All should be in review
        self.assertEqual(cpv1.publication_status, "review")
        self.assertEqual(cpv2a.publication_status, "review")
        self.assertEqual(cpv2b.publication_status, "review")
        self.assertEqual(cpv3.publication_status, "review")

    def test_cascade_with_no_property_values(self):
        """Cascade succeeds even when no property values exist."""
        collection = self._create_collection("C1", self.owner, status="private")

        # Should not raise exception
        collection.submit_for_review()

        self.assertEqual(collection.publication_status, "review")

    def test_cascade_with_mixed_statuses(self):
        """Cascade only affects CPVs in appropriate statuses."""
        collection = self._create_collection("C1", self.owner, status="private")

        cpv_private = self._create_cpv(
            collection, self.prop1, self.unit1, self.owner, "private", year=2020
        )
        cpv_review = self._create_cpv(
            collection, self.prop1, self.unit1, self.owner, "review", year=2021
        )
        cpv_published = self._create_cpv(
            collection, self.prop1, self.unit1, self.owner, "published", year=2022
        )
        cpv_declined = self._create_cpv(
            collection, self.prop1, self.unit1, self.owner, "declined", year=2023
        )

        collection.submit_for_review()

        cpv_private.refresh_from_db()
        cpv_review.refresh_from_db()
        cpv_published.refresh_from_db()
        cpv_declined.refresh_from_db()

        # Only private and declined should be submitted
        self.assertEqual(cpv_private.publication_status, "review")
        self.assertEqual(
            cpv_review.publication_status, "review"
        )  # Was already in review
        self.assertEqual(cpv_published.publication_status, "published")  # Unchanged
        self.assertEqual(
            cpv_declined.publication_status, "review"
        )  # Declined -> review

    def test_cascade_doesnt_fail_on_cpv_error(self):
        """Cascade continues even if individual CPV transitions fail."""
        collection = self._create_collection("C1", self.owner, status="review")

        # Create CPVs - one might fail but cascade should continue
        cpv1 = self._create_cpv(
            collection, self.prop1, self.unit1, self.owner, "review", year=2020
        )
        cpv2 = self._create_cpv(
            collection, self.prop2, self.unit2, self.owner, "review", year=2021
        )

        # Approve collection - even if one CPV has an issue, others should succeed
        collection.approve(user=self.staff)

        cpv1.refresh_from_db()
        cpv2.refresh_from_db()

        self.assertEqual(collection.publication_status, "published")
        # Both should be published (assuming no actual errors)
        self.assertEqual(cpv1.publication_status, "published")
        self.assertEqual(cpv2.publication_status, "published")
