from django.contrib.auth import get_user_model
from django.db.models import Q
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIRequestFactory, force_authenticate
from unittest import skip

from case_studies.soilcom.models import (
    Collection,
    CollectionFrequency,
    Collector,
    FeeSystem,
    Material,
)
from case_studies.soilcom.serializers import WasteCollectionGeometrySerializer
from case_studies.soilcom.viewsets import CollectionViewSet
from utils.models import UserCreatedObject

User = get_user_model()


class CollectionViewSetTestCase(TestCase):
    """Test the integration of CollectionViewSet with GeoJSONMixin and UserCreatedObjectViewSet."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.viewset = CollectionViewSet()

        # Create users
        self.regular_user = User.objects.create_user(username="testuser")
        self.staff_user = User.objects.create_user(username="staffuser", is_staff=True)

        # Create test data
        self.collector = Collector.objects.create(name="Test Collector")
        self.fee_system = FeeSystem.objects.create(name="Test Fee System")
        self.frequency = CollectionFrequency.objects.create(name="Test Frequency")

        # Create collections with different publication statuses
        self.private_collection = Collection.objects.create(
            name="Private Collection",
            owner=self.regular_user,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
            collector=self.collector,
            fee_system=self.fee_system,
            frequency=self.frequency,
        )

        self.review_collection = Collection.objects.create(
            name="Review Collection",
            owner=self.regular_user,
            publication_status=UserCreatedObject.STATUS_REVIEW,
            collector=self.collector,
            fee_system=self.fee_system,
            frequency=self.frequency,
        )

        self.published_collection = Collection.objects.create(
            name="Published Collection",
            owner=self.regular_user,
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
            collector=self.collector,
            fee_system=self.fee_system,
            frequency=self.frequency,
        )

        self.other_user_collection = Collection.objects.create(
            name="Other User Collection",
            owner=self.staff_user,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
            collector=self.collector,
            fee_system=self.fee_system,
            frequency=self.frequency,
        )

    def test_geojson_endpoint_with_published_scope(self):
        """Test geojson endpoint with 'published' scope parameter."""
        url = reverse("api-waste-collection-geojson")
        request = self.factory.get(f"{url}?scope=published")
        request.user = self.regular_user

        self.viewset.request = request
        self.viewset.format_kwarg = None
        response = self.viewset.geojson(request)

        # Should only contain published collections
        self.assertEqual(len(response.data["features"]), 1)
        feature_ids = [feature["id"] for feature in response.data["features"]]
        self.assertIn(self.published_collection.pk, feature_ids)

    def test_geojson_endpoint_with_private_scope(self):
        """Test geojson endpoint with 'private' scope parameter."""
        url = reverse("api-waste-collection-geojson")
        request = self.factory.get(f"{url}?scope=private")
        request.user = self.regular_user

        self.viewset.request = request
        self.viewset.format_kwarg = None
        response = self.viewset.geojson(request)

        # Should contain user's own collections + published
        self.assertEqual(len(response.data["features"]), 3)
        feature_ids = [feature["id"] for feature in response.data["features"]]
        self.assertIn(self.private_collection.pk, feature_ids)
        self.assertIn(self.review_collection.pk, feature_ids)
        self.assertIn(self.published_collection.pk, feature_ids)
        self.assertNotIn(self.other_user_collection.pk, feature_ids)

    def test_create_permission(self):
        """Test that users with proper permissions can create collections."""
        # Add permission to the user
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        ct = ContentType.objects.get_for_model(Collection)
        permission = Permission.objects.get(content_type=ct, codename="add_collection")
        self.regular_user.user_permissions.add(permission)

        request = self.factory.post(
            "/",
            {
                "name": "New Collection",
                "collector": self.collector.id,
                "fee_system": self.fee_system.id,
                "frequency": self.frequency.id,
            },
        )
        request.user = self.regular_user

        # This will be handled by the perform_create method
        # For testing, we're just checking that the permission check passes
        self.viewset.request = request
        self.viewset.action = "create"
        has_permission = self.viewset.get_permissions()[0].has_permission(
            request, self.viewset
        )
        self.assertTrue(has_permission)
