"""Test CollectionPropertyValue in review dashboard."""

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save, pre_save
from django.test import TestCase
from django.urls import reverse
from factory.django import mute_signals

from case_studies.soilcom.models import Collection, CollectionPropertyValue
from utils.object_management.models import UserCreatedObject
from utils.properties.models import Property, Unit


class CollectionPropertyValueReviewDashboardTest(TestCase):
    """Test that CollectionPropertyValue items appear correctly in review dashboard."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        # Create users
        cls.staff_user = User.objects.create_user(
            username="staff", password="test123", is_staff=True
        )
        cls.owner_user = User.objects.create_user(username="owner", password="test123")

        # Create a unit and property for the CPV
        cls.unit = Unit.objects.create(
            name="kg",
        )
        cls.property = Property.objects.create(
            name="Test Property",
            unit="kg",
        )

        # Create test collection and CPV in review
        with mute_signals(post_save, pre_save):
            cls.collection = Collection.objects.create(
                name="Test Collection",
                owner=cls.owner_user,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )

            # Create CPV in review status
            cls.cpv = CollectionPropertyValue.objects.create(
                name="Test CPV",
                property=cls.property,
                unit=cls.unit,
                collection=cls.collection,
                average=100.0,
                owner=cls.owner_user,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )

    def test_cpv_appears_in_unfiltered_dashboard(self):
        """Test that CPV items appear in the dashboard without filters."""
        self.client.force_login(self.staff_user)
        url = reverse("object_management:review_dashboard")

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        review_items = list(response.context["review_items"])

        # Should contain both the Collection and the CPV
        item_types = [type(item).__name__ for item in review_items]
        self.assertIn("Collection", item_types)
        self.assertIn("CollectionPropertyValue", item_types)

        # Verify the CPV is the one we created
        cpvs = [
            item for item in review_items if isinstance(item, CollectionPropertyValue)
        ]
        self.assertEqual(len(cpvs), 1)
        self.assertEqual(cpvs[0].id, self.cpv.id)

    def test_filtering_by_cpv_model_type(self):
        """Test filtering dashboard to show only CollectionPropertyValue items."""
        self.client.force_login(self.staff_user)
        url = reverse("object_management:review_dashboard")

        # Get ContentType for CPV
        cpv_ct = ContentType.objects.get_for_model(CollectionPropertyValue)

        # Filter by CPV model type
        response = self.client.get(url, {"model_type": cpv_ct.id})
        self.assertEqual(response.status_code, 200)

        review_items = list(response.context["review_items"])

        # Should only contain CPV items
        for item in review_items:
            self.assertIsInstance(item, CollectionPropertyValue)

        # Should have our test CPV
        self.assertEqual(len(review_items), 1)
        self.assertEqual(review_items[0].id, self.cpv.id)

    def test_cpv_model_appears_in_filter_options(self):
        """Test that CollectionPropertyValue appears as a filter option."""
        self.client.force_login(self.staff_user)
        url = reverse("object_management:review_dashboard")

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Check that the filter form includes CPV
        filter_obj = response.context["filter"]
        model_type_choices = filter_obj.filters["model_type"].queryset

        # Should include CollectionPropertyValue ContentType
        cpv_ct = ContentType.objects.get_for_model(CollectionPropertyValue)
        self.assertIn(cpv_ct, model_type_choices)
