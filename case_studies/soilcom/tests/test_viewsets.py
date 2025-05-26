from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIRequestFactory, APITestCase

from case_studies.soilcom.models import (
    Catchment,
    Collection,
    CollectionFrequency,
    CollectionSystem,
    Collector,
    FeeSystem,
    WasteCategory,
    WasteStream,
)
from case_studies.soilcom.viewsets import CollectionViewSet
from utils.models import UserCreatedObject

User = get_user_model()


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
        permission = Permission.objects.get(content_type=ct, codename="add_collection")
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

    def test_geojson_endpoint_with_published_scope(self):
        """Test geojson endpoint with 'published' scope parameter."""
        self.client.force_login(self.regular_user)
        url = reverse("api-waste-collection-geojson")
        response = self.client.get(f"{url}?scope=published")

        # Should only contain published collections
        self.assertEqual(len(response.data["features"]), 2)
        feature_ids = [
            feature["properties"]["id"] for feature in response.data["features"]
        ]
        self.assertIn(self.published_collection.pk, feature_ids)

    def test_geojson_endpoint_with_private_scope(self):
        """Test geojson endpoint with 'private' scope parameter."""
        self.client.force_login(self.regular_user)
        url = reverse("api-waste-collection-geojson")
        response = self.client.get(f"{url}?scope=private")

        self.assertEqual(len(response.data["features"]), 3)
        feature_ids = [
            feature["properties"]["id"] for feature in response.data["features"]
        ]
        self.assertIn(self.private_collection.pk, feature_ids)
        self.assertIn(self.review_collection.pk, feature_ids)
        self.assertIn(self.published_collection.pk, feature_ids)
        self.assertNotIn(self.other_user_private_collection.pk, feature_ids)
        self.assertNotIn(self.other_user_review_collection.pk, feature_ids)
        self.assertNotIn(self.other_user_published_collection.pk, feature_ids)

    def test_create_permission_denied_without_model_permission(self):
        """Test that a user without add_collection permission cannot create collections."""
        data = {
            "name": "New Collection",
            "collector": self.collector.id,
            "fee_system": self.fee_system.id,
            "frequency": self.frequency.id,
        }
        request = self.factory.post(
            "/",
            data,
            QUERY_STRING="foo=bar",
        )
        request.query_params = {"foo": "bar"}
        request.user = self.regular_user

        self.viewset.request = request
        self.viewset.action = "create"
        has_permission = self.viewset.get_permissions()[0].has_permission(
            request, self.viewset
        )
        self.assertFalse(has_permission)

    def test_create_permission_granted_with_model_permission(self):
        """Test that a user with add_collection permission can create collections."""
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        data = {
            "name": "New Collection",
            "collector": self.collector.id,
            "fee_system": self.fee_system.id,
            "frequency": self.frequency.id,
        }

        ct = ContentType.objects.get_for_model(Collection)
        permission = Permission.objects.get(content_type=ct, codename="add_collection")
        self.regular_user = User.objects.get(pk=self.regular_user.pk)
        self.regular_user.user_permissions.add(permission)
        self.regular_user.refresh_from_db()

        request = self.factory.post(
            "/",
            data,
            QUERY_STRING="foo=bar",
        )
        request.query_params = {"foo": "bar"}
        request.user = self.regular_user

        self.viewset.request = request
        self.viewset.action = "create"
        has_permission = self.viewset.get_permissions()[0].has_permission(
            request, self.viewset
        )
        self.assertTrue(has_permission)
