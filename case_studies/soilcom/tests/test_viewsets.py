from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIRequestFactory, APITestCase

from case_studies.soilcom.models import (
    AggregatedCollectionPropertyValue,
    Catchment,
    Collection,
    CollectionCatchment,
    CollectionFrequency,
    CollectionPropertyValue,
    CollectionSystem,
    Collector,
    FeeSystem,
    WasteCategory,
    WasteStream,
)
from case_studies.soilcom.viewsets import CollectionViewSet
from utils.object_management.models import UserCreatedObject
from utils.properties.models import Property, Unit


class CollectionViewSetTestCase(APITestCase):
    """
    Integration tests for CollectionViewSet with GeoJSONMixin and UserCreatedObjectViewSet.
    Covers GeoJSON endpoint filtering and model permission enforcement for creation.
    """

    @classmethod
    def setUpTestData(cls):
        cls.regular_user = User.objects.create_user(username="testuser")
        cls.staff_user = User.objects.create_user(username="staffuser", is_staff=True)

        cls.catchment = Catchment.objects.create(name="Test Catchment")
        cls.collector = Collector.objects.create(name="Test Collector")
        cls.fee_system = FeeSystem.objects.create(name="Test Fee System")
        cls.frequency = CollectionFrequency.objects.create(name="Test Frequency")
        cls.collection_system = CollectionSystem.objects.create(
            name="Test Collection System"
        )
        cls.waste_category = WasteCategory.objects.create(name="Test Waste Category")
        cls.waste_stream = WasteStream.objects.create(
            name="Test Waste Stream", category=cls.waste_category
        )

        cls.private_collection = cls._create_collection(
            name="Private Collection",
            owner=cls.regular_user,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )
        cls.review_collection = cls._create_collection(
            name="Review Collection",
            owner=cls.regular_user,
            publication_status=UserCreatedObject.STATUS_REVIEW,
        )
        cls.published_collection = cls._create_collection(
            name="Published Collection",
            owner=cls.regular_user,
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
        )
        cls.other_user_private_collection = cls._create_collection(
            name="Other User Collection",
            owner=cls.staff_user,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )
        cls.other_user_review_collection = cls._create_collection(
            name="Other User Review Collection",
            owner=cls.staff_user,
            publication_status=UserCreatedObject.STATUS_REVIEW,
        )
        cls.other_user_published_collection = cls._create_collection(
            name="Other User Published Collection",
            owner=cls.staff_user,
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
        )

    @classmethod
    def _create_collection(cls, name, owner, publication_status):
        return Collection.objects.create(
            name=name,
            owner=owner,
            catchment=cls.catchment,
            waste_stream=cls.waste_stream,
            collection_system=cls.collection_system,
            publication_status=publication_status,
            collector=cls.collector,
            fee_system=cls.fee_system,
            frequency=cls.frequency,
        )

    def setUp(self):
        self.factory = APIRequestFactory()
        self.viewset = CollectionViewSet()

    def test_geojson_endpoint_with_published_scope(self):
        """Should return only published collections for 'published' scope."""
        self.client.force_login(self.regular_user)
        url = reverse("api-waste-collection-geojson")
        response = self.client.get(f"{url}?scope=published")
        self.assertEqual(len(response.data["features"]), 2)
        feature_ids = [f["properties"]["id"] for f in response.data["features"]]
        self.assertIn(self.published_collection.pk, feature_ids)
        self.assertIn(self.other_user_published_collection.pk, feature_ids)

    def test_geojson_endpoint_with_private_scope(self):
        """Should return only the user's collections (private, review, published) for 'private' scope."""
        self.client.force_login(self.regular_user)
        url = reverse("api-waste-collection-geojson")
        response = self.client.get(f"{url}?scope=private")
        self.assertEqual(len(response.data["features"]), 3)
        feature_ids = [f["properties"]["id"] for f in response.data["features"]]
        self.assertIn(self.private_collection.pk, feature_ids)
        self.assertIn(self.review_collection.pk, feature_ids)
        self.assertIn(self.published_collection.pk, feature_ids)
        self.assertNotIn(self.other_user_private_collection.pk, feature_ids)
        self.assertNotIn(self.other_user_review_collection.pk, feature_ids)
        self.assertNotIn(self.other_user_published_collection.pk, feature_ids)

    def test_create_permission_denied_without_model_permission(self):
        """User without add_collection permission cannot create collections."""
        data = {
            "name": "New Collection",
            "collector": self.collector.id,
            "fee_system": self.fee_system.id,
            "frequency": self.frequency.id,
        }
        request = self.factory.post("/", data)
        request.user = self.regular_user
        self.viewset.request = request
        self.viewset.action = "create"
        has_permission = self.viewset.get_permissions()[0].has_permission(
            request, self.viewset
        )
        self.assertFalse(has_permission)

    def test_create_permission_granted_with_model_permission(self):
        """User with add_collection permission can create collections."""
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        data = {
            "name": "New Collection",
            "collector": self.collector.id,
            "fee_system": self.fee_system.id,
            "frequency": self.frequency.id,
        }
        ct = ContentType.objects.get_for_model(Collection)
        permission, _ = Permission.objects.get_or_create(
            content_type=ct,
            codename="add_collection",
            defaults={"name": "Can add collection"},
        )
        self.regular_user.user_permissions.add(permission)
        self.regular_user.refresh_from_db()
        request = self.factory.post("/", data)
        request.user = self.regular_user
        self.viewset.request = request
        self.viewset.action = "create"
        has_permission = self.viewset.get_permissions()[0].has_permission(
            request, self.viewset
        )
        self.assertTrue(has_permission)

    def test_cache_key_differs_for_different_users_private_scope(self):
        """Verify cache keys are user-specific for private scope.

        This ensures that private collections cannot leak between users
        via shared cache keys.
        """
        from maps.utils import build_collection_cache_key

        # Build cache keys for different users with private scope
        key_user1 = build_collection_cache_key(
            scope="private", user=self.regular_user, filters=None
        )
        key_user2 = build_collection_cache_key(
            scope="private", user=self.staff_user, filters=None
        )

        # Keys should be different for different users
        self.assertNotEqual(
            key_user1,
            key_user2,
            "Cache keys for private scope should be user-specific",
        )

    def test_cache_key_same_for_published_scope(self):
        """Verify cache keys are shared for published scope (public data)."""
        from maps.utils import build_collection_cache_key

        # Build cache keys for different users with published scope
        key_user1 = build_collection_cache_key(
            scope="published", user=self.regular_user, filters=None
        )
        key_user2 = build_collection_cache_key(
            scope="published", user=self.staff_user, filters=None
        )

        # Keys should be the same for published data (shared cache)
        self.assertEqual(
            key_user1,
            key_user2,
            "Cache keys for published scope should be shared across users",
        )

    def test_private_scope_data_isolation(self):
        """Verify that private scope requests return only user's own data.

        This is a data isolation test to ensure one user cannot see
        another user's private collections, even with caching.
        """
        url = reverse("api-waste-collection-geojson")

        # User 1 requests private scope
        self.client.force_login(self.regular_user)
        response1 = self.client.get(f"{url}?scope=private")
        user1_ids = {f["properties"]["id"] for f in response1.data["features"]}

        # User 2 requests private scope
        self.client.force_login(self.staff_user)
        response2 = self.client.get(f"{url}?scope=private")
        user2_ids = {f["properties"]["id"] for f in response2.data["features"]}

        # Each user should only see their own collections
        self.assertIn(self.private_collection.pk, user1_ids)
        self.assertNotIn(self.other_user_private_collection.pk, user1_ids)

        self.assertIn(self.other_user_private_collection.pk, user2_ids)
        self.assertNotIn(self.private_collection.pk, user2_ids)

        # No overlap in private data
        user1_private_ids = user1_ids - {
            self.published_collection.pk,
            self.review_collection.pk,
        }
        user2_private_ids = user2_ids - {
            self.other_user_published_collection.pk,
            self.other_user_review_collection.pk,
        }
        self.assertEqual(
            len(user1_private_ids & user2_private_ids),
            0,
            "Private collections should not be shared between users",
        )

    def test_geojson_uses_simplified_geometry_annotation(self):
        """Verify that GeoJSON serializer uses simplified_geom annotation when present.

        This test ensures the GeometrySerializerMethodField is correctly
        using the simplified geometry from the queryset annotation.
        """
        from unittest.mock import MagicMock

        from case_studies.soilcom.serializers import WasteCollectionGeometrySerializer

        # Create a mock instance with both original and simplified geometry
        mock_instance = MagicMock()
        mock_instance.geom = "original_geom"
        mock_instance.simplified_geom = "simplified_geom"

        serializer = WasteCollectionGeometrySerializer()

        # The get_geom method should return simplified_geom when available
        result = serializer.get_geom(mock_instance)
        self.assertEqual(result, "simplified_geom")

    def test_geojson_falls_back_to_original_geometry(self):
        """Verify serializer falls back to original geom when simplified is not available."""
        from unittest.mock import MagicMock

        from case_studies.soilcom.serializers import WasteCollectionGeometrySerializer

        # Create a mock instance without simplified geometry
        mock_instance = MagicMock(spec=["geom"])
        mock_instance.geom = "original_geom"

        serializer = WasteCollectionGeometrySerializer()

        # The get_geom method should fall back to original geometry
        result = serializer.get_geom(mock_instance)
        self.assertEqual(result, "original_geom")


class CollectionReviewActionApiTestCase(APITestCase):
    """Ensure review action API endpoints trigger collection cascade behavior."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner")
        cls.other_owner = User.objects.create_user(username="other-owner")
        cls.staff = User.objects.create_user(username="staff", is_staff=True)

        cls.catchment = CollectionCatchment.objects.create(name="Test Catchment")
        cls.collector = Collector.objects.create(name="Test Collector")
        cls.collection_system = CollectionSystem.objects.create(
            name="Test Collection System"
        )
        cls.waste_category = WasteCategory.objects.create(name="Test Waste Category")
        cls.waste_stream = WasteStream.objects.create(
            name="Test Waste Stream", category=cls.waste_category
        )
        cls.frequency = CollectionFrequency.objects.create(name="Test Frequency")
        cls.fee_system = FeeSystem.objects.create(name="Test Fee System")

        cls.unit = Unit.objects.create(name="Test Unit", publication_status="published")
        cls.property = Property.objects.create(
            name="Test Property",
            unit="kg",
            publication_status="published",
        )
        cls.property.allowed_units.add(cls.unit)

    def _create_collection(self, name, owner, publication_status):
        return Collection.objects.create(
            name=name,
            owner=owner,
            catchment=self.catchment,
            waste_stream=self.waste_stream,
            collection_system=self.collection_system,
            publication_status=publication_status,
            collector=self.collector,
            fee_system=self.fee_system,
            frequency=self.frequency,
        )

    def _create_cpv(self, collection, owner, status, year=2020):
        return CollectionPropertyValue.objects.create(
            collection=collection,
            property=self.property,
            unit=self.unit,
            owner=owner,
            publication_status=status,
            year=year,
            average=10.0,
        )

    def _create_acpv(self, collections, owner, status, year=2020):
        acpv = AggregatedCollectionPropertyValue.objects.create(
            property=self.property,
            unit=self.unit,
            owner=owner,
            publication_status=status,
            year=year,
            average=20.0,
        )
        acpv.collections.set(collections)
        return acpv

    def test_register_for_review_cascades_property_values(self):
        collection = self._create_collection(
            "Collection Submit",
            owner=self.owner,
            publication_status="private",
        )
        cpv_private = self._create_cpv(collection, self.owner, "private")
        cpv_declined = self._create_cpv(collection, self.owner, "declined", year=2021)
        cpv_published = self._create_cpv(collection, self.owner, "published", year=2022)
        acpv_private = self._create_acpv([collection], self.owner, "private")

        self.client.force_login(self.owner)
        url = reverse(
            "api-waste-collection-register-for-review", kwargs={"pk": collection.pk}
        )
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        collection.refresh_from_db()
        cpv_private.refresh_from_db()
        cpv_declined.refresh_from_db()
        cpv_published.refresh_from_db()
        acpv_private.refresh_from_db()

        self.assertEqual(collection.publication_status, "review")
        self.assertEqual(cpv_private.publication_status, "review")
        self.assertEqual(cpv_declined.publication_status, "review")
        self.assertEqual(cpv_published.publication_status, "published")
        self.assertEqual(acpv_private.publication_status, "review")

    def test_approve_cascades_property_values(self):
        collection = self._create_collection(
            "Collection Approve",
            owner=self.owner,
            publication_status="review",
        )
        cpv_owner = self._create_cpv(collection, self.owner, "review")
        cpv_other = self._create_cpv(collection, self.other_owner, "review", year=2021)
        acpv_review = self._create_acpv([collection], self.owner, "review")

        self.client.force_login(self.staff)
        url = reverse("api-waste-collection-approve", kwargs={"pk": collection.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        collection.refresh_from_db()
        cpv_owner.refresh_from_db()
        cpv_other.refresh_from_db()
        acpv_review.refresh_from_db()

        self.assertEqual(collection.publication_status, "published")
        self.assertEqual(cpv_owner.publication_status, "published")
        self.assertEqual(cpv_other.publication_status, "published")
        self.assertEqual(cpv_owner.approved_by, self.staff)
        self.assertEqual(cpv_other.approved_by, self.staff)
        self.assertEqual(acpv_review.publication_status, "published")
        self.assertEqual(acpv_review.approved_by, self.staff)
