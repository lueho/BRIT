from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIRequestFactory, APITestCase

from bibliography.models import Source
from distributions.models import TemporalDistribution, Timestep
from maps.models import Attribute, GeoPolygon, NutsRegion, Region, RegionAttributeValue
from materials.models import Material
from sources.waste_collection.derived_values import clear_derived_value_config_cache
from sources.waste_collection.importers import CollectionImporter
from sources.waste_collection.models import (
    AggregatedCollectionPropertyValue,
    Catchment,
    Collection,
    CollectionCatchment,
    CollectionCountOptions,
    CollectionFrequency,
    CollectionPropertyValue,
    CollectionSystem,
    Collector,
    FeeSystem,
    SortingMethod,
    WasteCategory,
    WasteFlyer,
)
from sources.waste_collection.viewsets import CollectionViewSet
from utils.object_management.models import ReviewAction, UserCreatedObject
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
            waste_category=cls.waste_category,
            collection_system=cls.collection_system,
            publication_status=publication_status,
            collector=cls.collector,
            fee_system=cls.fee_system,
            frequency=cls.frequency,
        )

    def setUp(self):
        self.factory = APIRequestFactory()
        self.viewset = CollectionViewSet()

    @staticmethod
    def _response_results(response):
        if isinstance(response.data, dict):
            return response.data.get("results", response.data.get("summaries", []))
        return response.data

    def _get_collection_cache_key(self, params=None, user=None):
        """Build a CollectionViewSet cache key from request query params."""
        request = self.factory.get("/", params or {})
        request.query_params = request.GET
        request.user = user or self.regular_user
        return self.viewset.get_cache_key(request)

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

    def test_geojson_defaults_to_latest_visible_collection_version(self):
        """Map endpoint should hide older versions when no temporal/id filter is provided."""
        predecessor = self._create_collection(
            name="Versioned Collection 2021",
            owner=self.regular_user,
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
        )
        predecessor.valid_from = date(2021, 1, 1)
        predecessor.valid_until = date(2021, 12, 31)
        predecessor.save(update_fields=["valid_from", "valid_until"])

        successor = self._create_collection(
            name="Versioned Collection 2022",
            owner=self.regular_user,
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
        )
        successor.valid_from = date(2022, 1, 1)
        successor.save(update_fields=["valid_from"])
        successor.add_predecessor(predecessor)

        self.client.force_login(self.regular_user)
        url = reverse("api-waste-collection-geojson")
        response = self.client.get(url, {"scope": "published"})

        feature_ids = {f["properties"]["id"] for f in response.data["features"]}
        self.assertIn(successor.pk, feature_ids)
        self.assertNotIn(predecessor.pk, feature_ids)

    def test_geojson_with_valid_on_includes_historical_versions(self):
        """Historical filters should bypass latest-only version suppression."""
        predecessor = self._create_collection(
            name="Temporal Collection 2021",
            owner=self.regular_user,
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
        )
        predecessor.valid_from = date(2021, 1, 1)
        predecessor.valid_until = date(2021, 12, 31)
        predecessor.save(update_fields=["valid_from", "valid_until"])

        successor = self._create_collection(
            name="Temporal Collection 2022",
            owner=self.regular_user,
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
        )
        successor.valid_from = date(2022, 1, 1)
        successor.save(update_fields=["valid_from"])
        successor.add_predecessor(predecessor)

        self.client.force_login(self.regular_user)
        url = reverse("api-waste-collection-geojson")
        response = self.client.get(
            url,
            {
                "scope": "published",
                "valid_on": "2021-06-01",
            },
        )

        feature_ids = {f["properties"]["id"] for f in response.data["features"]}
        self.assertIn(predecessor.pk, feature_ids)
        self.assertNotIn(successor.pk, feature_ids)

    def test_geojson_published_predecessor_not_hidden_by_review_successor(self):
        """A published collection must not be hidden when its successor is still in review.

        Regression test: before the fix, the subquery used the scope-filtered outer
        queryset.  For staff or unscoped requests that include review collections,
        the 2024 review successor would cause the 2022 published predecessor to be
        suppressed even though no *published* replacement exists yet.
        """
        predecessor = self._create_collection(
            name="Published 2022",
            owner=self.regular_user,
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
        )
        successor = self._create_collection(
            name="Review 2024",
            owner=self.regular_user,
            publication_status=UserCreatedObject.STATUS_REVIEW,
        )
        successor.add_predecessor(predecessor)

        self.client.force_login(self.regular_user)
        url = reverse("api-waste-collection-geojson")
        response = self.client.get(url, {"scope": "published"})

        feature_ids = {f["properties"]["id"] for f in response.data["features"]}
        self.assertIn(predecessor.pk, feature_ids)
        self.assertNotIn(successor.pk, feature_ids)

    def test_geojson_with_id_filter_allows_explicit_historical_version(self):
        """Explicit ID selection should return requested historical version."""
        predecessor = self._create_collection(
            name="Pinned Collection 2021",
            owner=self.regular_user,
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
        )
        predecessor.valid_from = date(2021, 1, 1)
        predecessor.valid_until = date(2021, 12, 31)
        predecessor.save(update_fields=["valid_from", "valid_until"])

        successor = self._create_collection(
            name="Pinned Collection 2022",
            owner=self.regular_user,
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
        )
        successor.valid_from = date(2022, 1, 1)
        successor.save(update_fields=["valid_from"])
        successor.add_predecessor(predecessor)

        self.client.force_login(self.regular_user)
        url = reverse("api-waste-collection-geojson")
        response = self.client.get(
            url,
            {
                "scope": "published",
                "id": [str(predecessor.pk)],
            },
        )

        feature_ids = {f["properties"]["id"] for f in response.data["features"]}
        self.assertEqual(feature_ids, {predecessor.pk})

    def test_list_endpoint_includes_research_metadata_fields(self):
        predecessor = self._create_collection(
            name="Research Predecessor",
            owner=self.regular_user,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )
        successor = self._create_collection(
            name="Research Successor",
            owner=self.regular_user,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )
        successor.add_predecessor(predecessor)

        self.client.force_login(self.regular_user)
        response = self.client.get(
            reverse("api-waste-collection-list"),
            {"scope": "private", "id": [successor.pk]},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self._response_results(response)
        result = next(item for item in results if item["id"] == successor.pk)

        self.assertEqual(result["publication_status"], UserCreatedObject.STATUS_PRIVATE)
        self.assertEqual(result["collection_system_id"], self.collection_system.pk)
        self.assertEqual(result["frequency_id"], self.frequency.pk)
        self.assertEqual(result["predecessor_ids"], [predecessor.pk])
        self.assertEqual(result["successor_ids"], [])

    def test_summaries_endpoint_returns_own_private_collection_without_scope(self):
        self.client.force_login(self.regular_user)

        response = self.client.get(
            reverse("api-waste-collection-summaries"),
            {"id": [self.private_collection.pk]},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        summaries = self._response_results(response)
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0]["id"], self.private_collection.pk)
        self.assertEqual(
            summaries[0]["Publication status"],
            UserCreatedObject.STATUS_PRIVATE,
        )

    def test_summaries_endpoint_hides_other_users_private_collection(self):
        self.client.force_login(self.regular_user)

        response = self.client.get(
            reverse("api-waste-collection-summaries"),
            {"id": [self.other_user_private_collection.pk]},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._response_results(response), [])

    def test_frequencies_action_supports_exact_name_lookup(self):
        CollectionFrequency.objects.create(
            name="Agent Frequency Private",
            owner=self.regular_user,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )
        published_frequency = CollectionFrequency.objects.create(
            name="Weekly Research Frequency",
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
        )

        self.client.force_login(self.regular_user)
        response = self.client.get(
            reverse("api-waste-collection-frequencies"),
            {"exact_name": "Weekly Research Frequency"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self._response_results(response)
        self.assertEqual(
            results,
            [
                {
                    "id": published_frequency.pk,
                    "name": published_frequency.name,
                    "type": published_frequency.type,
                }
            ],
        )

    def test_create_permission_denied_without_model_permission(self):
        """User without add_collection permission cannot create collections."""
        data = {
            "catchment": self.catchment.pk,
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

    def test_published_scope_cache_key_normalization_and_externalities(self):
        """Ensure published scope is normalized while other key dimensions remain intact.

        Fix 1 target:
        - `scope=published` should map to the same cache key as omitting scope.

        Externalities:
        - warmup key should match request-time published key
        - non-scope filters must still affect the key
        - private/review scope keys must remain distinct from published
        """
        from maps.utils import build_collection_cache_key

        published_default_key = self._get_collection_cache_key()
        published_explicit_key = self._get_collection_cache_key({"scope": "published"})
        self.assertEqual(
            published_default_key,
            published_explicit_key,
            "Explicit scope=published should not create a different cache key",
        )

        warmup_key = build_collection_cache_key(scope="published")
        self.assertEqual(
            published_default_key,
            warmup_key,
            "Published request cache key must match warmup cache key",
        )

        filtered_without_scope = self._get_collection_cache_key({"collector": "1"})
        filtered_with_scope = self._get_collection_cache_key(
            {"collector": "1", "scope": "published"}
        )
        filtered_other = self._get_collection_cache_key(
            {"collector": "2", "scope": "published"}
        )
        self.assertEqual(
            filtered_without_scope,
            filtered_with_scope,
            "Adding scope=published must not alter filtered cache keys",
        )
        self.assertNotEqual(
            filtered_with_scope,
            filtered_other,
            "Non-scope filter changes must still produce a different cache key",
        )

        private_key = self._get_collection_cache_key({"scope": "private"})
        review_key = self._get_collection_cache_key({"scope": "review"})
        self.assertNotEqual(
            published_default_key,
            private_key,
            "Private scope must stay isolated from published cache entries",
        )
        self.assertNotEqual(
            published_default_key,
            review_key,
            "Review scope must stay isolated from published cache entries",
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

    @patch("sources.waste_collection.filters.ConnectionRateFilter.set_min_max")
    def test_version_endpoint_skips_filter_min_max_initialization(
        self, mock_set_min_max
    ):
        """Version endpoint should avoid expensive range-widget min/max queries."""
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse("api-waste-collection-version"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_set_min_max.assert_not_called()

    @patch("sources.waste_collection.filters.ConnectionRateFilter.set_min_max")
    def test_geojson_endpoint_skips_filter_min_max_initialization(
        self, mock_set_min_max
    ):
        """GeoJSON endpoint should avoid expensive range-widget min/max queries."""
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse("api-waste-collection-geojson"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_set_min_max.assert_not_called()

    @patch("sources.waste_collection.filters.ConnectionRateFilter.set_min_max")
    def test_collection_filterset_still_initializes_min_max_by_default(
        self, mock_set_min_max
    ):
        """Default CollectionFilterSet initialization should still prepare form widgets."""
        from sources.waste_collection.filters import CollectionFilterSet

        CollectionFilterSet(queryset=Collection.objects.all())
        mock_set_min_max.assert_called_once()

    def test_geojson_uses_simplified_geometry_annotation(self):
        """Verify that GeoJSON serializer uses simplified_geom annotation when present.

        This test ensures the GeometrySerializerMethodField is correctly
        using the simplified geometry from the queryset annotation.
        """
        from unittest.mock import MagicMock

        from sources.waste_collection.serializers import (
            WasteCollectionGeometrySerializer,
        )

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

        from sources.waste_collection.serializers import (
            WasteCollectionGeometrySerializer,
        )

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
            waste_category=self.waste_category,
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


class CollectionImporterWorkflowTestCase(APITestCase):
    """Verify CollectionImporter uses the proper submit_for_review workflow.

    When publication_status='review', collections must be created as private
    and then submitted via submit_for_review(), so that submitted_at is set
    and a ReviewAction(submitted) is created — identical to the UI workflow.
    """

    @classmethod
    def setUpTestData(cls):
        import datetime

        cls.owner = User.objects.create_user(username="importer-owner")
        cls.staff_owner = User.objects.create_user(
            username="importer-staff", is_staff=True
        )
        cls.catchment = CollectionCatchment.objects.create(
            name="Importer Test Catchment"
        )
        cls.collection_system = CollectionSystem.objects.create(
            name="Importer Test System"
        )
        cls.waste_category = WasteCategory.objects.create(name="Importer Test Category")
        cls.allowed_material = Material.objects.create(
            name="Importer Allowed Material",
            owner=cls.owner,
        )
        cls.forbidden_material = Material.objects.create(
            name="Importer Forbidden Material",
            owner=cls.owner,
        )
        cls.valid_from = datetime.date(2099, 6, 1)

    def _make_record(self):
        return {
            "nuts_or_lau_id": None,
            "catchment_name": self.catchment.name,
            "collection_system": self.collection_system.name,
            "waste_category": self.waste_category.name,
            "valid_from": self.valid_from,
            "valid_until": None,
            "collector": None,
            "fee_system": None,
            "frequency": None,
            "connection_type": None,
            "min_bin_size": None,
            "required_bin_capacity": None,
            "required_bin_capacity_reference": None,
            "allowed_materials": "",
            "forbidden_materials": "",
            "description": "",
            "property_values": [],
            "flyer_urls": [],
        }

    def test_import_as_private_stays_private(self):
        """Collections imported with publication_status='private' have no ReviewAction."""
        importer = CollectionImporter(owner=self.owner, publication_status="private")
        stats = importer.run([self._make_record()])
        self.assertEqual(stats["created"], 1)

        collection = Collection.objects.get(
            owner=self.owner,
            valid_from=self.valid_from,
            collection_system=self.collection_system,
        )
        self.assertEqual(collection.publication_status, "private")
        self.assertIsNone(collection.submitted_at)
        self.assertFalse(
            ReviewAction.for_object(collection)
            .filter(action=ReviewAction.ACTION_SUBMITTED)
            .exists()
        )
        collection.delete()

    def test_import_as_review_uses_submit_workflow(self):
        """Collections imported with publication_status='review' go through submit_for_review()."""
        importer = CollectionImporter(owner=self.owner, publication_status="review")
        stats = importer.run([self._make_record()])
        self.assertEqual(stats["created"], 1)

        collection = Collection.objects.get(
            owner=self.owner,
            valid_from=self.valid_from,
            collection_system=self.collection_system,
        )
        self.assertEqual(collection.publication_status, "review")
        self.assertIsNotNone(collection.submitted_at)
        self.assertTrue(
            ReviewAction.for_object(collection)
            .filter(action=ReviewAction.ACTION_SUBMITTED)
            .exists()
        )
        collection.delete()

    def test_import_dry_run_creates_no_records(self):
        """Dry run must not persist any collection or ReviewAction."""
        importer = CollectionImporter(owner=self.owner, publication_status="review")
        stats = importer.run([self._make_record()], dry_run=True)
        self.assertEqual(stats["created"], 1)

        self.assertFalse(
            Collection.objects.filter(
                owner=self.owner,
                valid_from=self.valid_from,
                collection_system=self.collection_system,
            ).exists()
        )

    def test_bulk_import_endpoint_preserves_material_lists(self):
        self.client.force_login(self.staff_owner)

        response = self.client.post(
            reverse("api-waste-collection-bulk-import"),
            {
                "records": [
                    self._make_record()
                    | {
                        "allowed_materials": self.allowed_material.name,
                        "forbidden_materials": self.forbidden_material.name,
                    }
                ],
                "publication_status": "private",
                "dry_run": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        collection = Collection.objects.get(
            owner=self.staff_owner,
            valid_from=self.valid_from,
            collection_system=self.collection_system,
        )
        self.assertEqual(
            list(collection.allowed_materials.values_list("name", flat=True)),
            [self.allowed_material.name],
        )
        self.assertEqual(
            list(collection.forbidden_materials.values_list("name", flat=True)),
            [self.forbidden_material.name],
        )


class CollectionMutationApiTestCase(APITestCase):
    """Tests for programmatic collection creation and new-version endpoints."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="agent-owner")
        cls.other_user = User.objects.create_user(username="agent-other")
        cls.staff = User.objects.create_user(username="agent-staff", is_staff=True)

        collection_content_type = ContentType.objects.get_for_model(Collection)
        cls.add_collection_permission, _ = Permission.objects.get_or_create(
            content_type=collection_content_type,
            codename="add_collection",
            defaults={"name": "Can add collection"},
        )
        frequency_content_type = ContentType.objects.get_for_model(CollectionFrequency)
        cls.add_collection_frequency_permission, _ = Permission.objects.get_or_create(
            content_type=frequency_content_type,
            codename="add_collectionfrequency",
            defaults={"name": "Can add collection frequency"},
        )
        cls.owner.user_permissions.add(cls.add_collection_permission)
        cls.owner.user_permissions.add(cls.add_collection_frequency_permission)
        cls.other_user.user_permissions.add(cls.add_collection_permission)

        cls.months_distribution = TemporalDistribution.objects.get(
            name="Months of the year"
        )
        cls.march = Timestep.objects.get(
            distribution=cls.months_distribution,
            name="March",
        )
        cls.october = Timestep.objects.get(
            distribution=cls.months_distribution,
            name="October",
        )
        cls.november = Timestep.objects.get(
            distribution=cls.months_distribution,
            name="November",
        )
        cls.february = Timestep.objects.get(
            distribution=cls.months_distribution,
            name="February",
        )

        cls.catchment = CollectionCatchment.objects.create(name="Agent Catchment")
        cls.collection_system = CollectionSystem.objects.create(name="Agent System")
        cls.waste_category = WasteCategory.objects.create(name="Agent Waste")
        cls.collector = Collector.objects.create(name="Agent Collector")
        cls.frequency = CollectionFrequency.objects.create(name="Agent Frequency")
        cls.fee_system = FeeSystem.objects.create(name="Agent Fee")
        cls.sorting_method = SortingMethod.objects.create(name="Agent Sorting")
        cls.allowed_material = Material.objects.create(
            name="Agent Allowed Material", owner=cls.owner
        )
        cls.updated_collector = Collector.objects.create(name="Updated Agent Collector")
        cls.updated_allowed_material = Material.objects.create(
            name="Agent Updated Allowed Material", owner=cls.owner
        )
        cls.forbidden_material = Material.objects.create(
            name="Agent Forbidden Material", owner=cls.owner
        )
        cls.source = Source.objects.create(
            owner=cls.owner,
            title="Agent Source",
            abbreviation="AgentSource",
            url="https://example.com/source",
        )

        cls.predecessor = Collection.objects.create(
            owner=cls.owner,
            publication_status="published",
            catchment=cls.catchment,
            collector=cls.collector,
            collection_system=cls.collection_system,
            waste_category=cls.waste_category,
            frequency=cls.frequency,
            fee_system=cls.fee_system,
            sorting_method=cls.sorting_method,
            valid_from=date(2024, 1, 1),
            description="predecessor",
        )
        cls.predecessor.allowed_materials.add(cls.allowed_material)
        cls.predecessor.forbidden_materials.add(cls.forbidden_material)
        cls.private_predecessor = Collection.objects.create(
            owner=cls.owner,
            publication_status="private",
            catchment=cls.catchment,
            collector=cls.collector,
            collection_system=cls.collection_system,
            waste_category=cls.waste_category,
            frequency=cls.frequency,
            fee_system=cls.fee_system,
            sorting_method=cls.sorting_method,
            valid_from=date(2024, 6, 1),
            description="private predecessor",
        )
        cls.private_predecessor.allowed_materials.add(cls.allowed_material)
        cls.private_predecessor.forbidden_materials.add(cls.forbidden_material)
        cls.predecessor.sources.add(cls.source)
        cls.predecessor_flyer = WasteFlyer.objects.create(
            owner=cls.owner,
            title="Predecessor flyer",
            publication_status="private",
            url="https://example.com/predecessor-flyer",
        )
        cls.predecessor.flyers.add(cls.predecessor_flyer)

    def _seasonal_frequency_payload(self, *, name="", submit_for_review=True):
        return {
            "name": name,
            "description": "Nordwestmecklenburg GER seasonal cadence.",
            "submit_for_review": submit_for_review,
            "rows": [
                {
                    "distribution": self.months_distribution.pk,
                    "first_timestep": self.march.pk,
                    "last_timestep": self.october.pk,
                    "standard_cadence": "every_two_weeks",
                },
                {
                    "distribution": self.months_distribution.pk,
                    "first_timestep": self.november.pk,
                    "last_timestep": self.february.pk,
                    "standard_cadence": "every_four_weeks",
                },
            ],
        }

    def test_create_endpoint_requires_add_permission(self):
        user = User.objects.create_user(username="agent-no-perm")
        self.client.force_login(user)

        response = self.client.post(
            reverse("api-waste-collection-create"),
            {
                "catchment": self.catchment.pk,
                "waste_category": self.waste_category.pk,
                "collection_system": self.collection_system.pk,
                "valid_from": "2025-01-01",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_endpoint_private_draft_when_submit_disabled(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("api-waste-collection-create"),
            {
                "catchment": self.catchment.pk,
                "waste_category": self.waste_category.pk,
                "collection_system": self.collection_system.pk,
                "collector": self.collector.pk,
                "frequency": self.frequency.pk,
                "fee_system": self.fee_system.pk,
                "sorting_method": self.sorting_method.pk,
                "allowed_materials": [self.allowed_material.pk],
                "forbidden_materials": [self.forbidden_material.pk],
                "sources": [self.source.pk],
                "flyer_urls": ["https://example.com/new-flyer"],
                "valid_from": "2025-01-01",
                "description": "Agent draft",
                "submit_for_review": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data["submitted"])

        collection = Collection.objects.get(pk=response.data["id"])
        self.assertEqual(collection.publication_status, "private")
        self.assertIsNone(collection.submitted_at)
        self.assertEqual(collection.sources.count(), 1)
        self.assertEqual(collection.flyers.count(), 1)
        self.assertFalse(
            ReviewAction.for_object(collection)
            .filter(action=ReviewAction.ACTION_SUBMITTED)
            .exists()
        )

    def test_create_endpoint_submits_for_review(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("api-waste-collection-create"),
            {
                "catchment": self.catchment.pk,
                "waste_category": self.waste_category.pk,
                "collection_system": self.collection_system.pk,
                "valid_from": "2025-02-01",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["submitted"])

        collection = Collection.objects.get(pk=response.data["id"])
        self.assertEqual(collection.publication_status, "review")
        self.assertIsNotNone(collection.submitted_at)
        self.assertTrue(
            ReviewAction.for_object(collection)
            .filter(action=ReviewAction.ACTION_SUBMITTED)
            .exists()
        )

    def test_create_endpoint_validates_dates(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("api-waste-collection-create"),
            {
                "catchment": self.catchment.pk,
                "waste_category": self.waste_category.pk,
                "collection_system": self.collection_system.pk,
                "valid_from": "2025-02-01",
                "valid_until": "2025-01-01",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("valid_until", response.data)

    def test_create_frequency_endpoint_requires_add_permission(self):
        user = User.objects.create_user(username="agent-no-frequency-perm")
        self.client.force_login(user)

        response = self.client.post(
            reverse("api-waste-collection-frequency-create"),
            self._seasonal_frequency_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_frequency_endpoint_creates_exact_schedule_and_submits(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("api-waste-collection-frequency-create"),
            self._seasonal_frequency_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["created"])
        self.assertTrue(response.data["submitted"])
        self.assertEqual(
            response.data["name"],
            "Seasonal; 1 per 2 weeks from March-October; 1 per 4 weeks from November-February",
        )

        frequency = CollectionFrequency.objects.get(pk=response.data["id"])
        self.assertEqual(frequency.owner, self.owner)
        self.assertEqual(frequency.publication_status, "review")
        self.assertEqual(frequency.type, "Seasonal")
        self.assertEqual(
            frequency.name,
            "Seasonal; 1 per 2 weeks from March-October; 1 per 4 weeks from November-February",
        )
        self.assertTrue(
            ReviewAction.for_object(frequency)
            .filter(action=ReviewAction.ACTION_SUBMITTED)
            .exists()
        )

        rows = list(
            CollectionCountOptions.objects.filter(frequency=frequency)
            .select_related("season__first_timestep", "season__last_timestep")
            .order_by("season__first_timestep__order")
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            [
                (
                    row.season.first_timestep.name,
                    row.season.last_timestep.name,
                    row.standard,
                    row.publication_status,
                )
                for row in rows
            ],
            [
                ("March", "October", 17, "review"),
                ("November", "February", 4, "review"),
            ],
        )

    def test_create_frequency_endpoint_reuses_existing_visible_frequency(self):
        existing_frequency = CollectionFrequency.objects.create(
            owner=self.owner,
            publication_status="private",
            name="Seasonal; 1 per 2 weeks from March-October; 1 per 4 weeks from November-February",
            type="Seasonal",
        )

        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("api-waste-collection-frequency-create"),
            self._seasonal_frequency_payload(submit_for_review=False),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["created"])
        self.assertEqual(response.data["id"], existing_frequency.pk)
        self.assertEqual(
            CollectionCountOptions.objects.filter(frequency=existing_frequency).count(),
            0,
        )

    def test_update_endpoint_denies_non_owner(self):
        self.client.force_login(self.other_user)

        response = self.client.post(
            reverse(
                "api-waste-collection-update",
                kwargs={"pk": self.private_predecessor.pk},
            ),
            {
                "expected_catchment": str(self.private_predecessor.catchment),
                "expected_waste_category": str(
                    self.private_predecessor.effective_waste_category
                ),
                "expected_collection_system": str(
                    self.private_predecessor.collection_system
                ),
                "expected_publication_status": self.private_predecessor.publication_status,
                "expected_valid_from": self.private_predecessor.valid_from.isoformat(),
                "description": "intruder update",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_endpoint_rejects_identity_mismatch(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse(
                "api-waste-collection-update",
                kwargs={"pk": self.private_predecessor.pk},
            ),
            {
                "expected_catchment": "Wrong Catchment",
                "expected_waste_category": str(
                    self.private_predecessor.effective_waste_category
                ),
                "expected_collection_system": str(
                    self.private_predecessor.collection_system
                ),
                "expected_publication_status": self.private_predecessor.publication_status,
                "expected_valid_from": self.private_predecessor.valid_from.isoformat(),
                "description": "mismatch update",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("mismatches", response.data)
        self.private_predecessor.refresh_from_db()
        self.assertEqual(self.private_predecessor.description, "private predecessor")

    def test_update_endpoint_enriches_existing_collection(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse(
                "api-waste-collection-update",
                kwargs={"pk": self.private_predecessor.pk},
            ),
            {
                "expected_catchment": str(self.private_predecessor.catchment),
                "expected_waste_category": str(
                    self.private_predecessor.effective_waste_category
                ),
                "expected_collection_system": str(
                    self.private_predecessor.collection_system
                ),
                "expected_publication_status": self.private_predecessor.publication_status,
                "expected_valid_from": self.private_predecessor.valid_from.isoformat(),
                "allowed_materials": [self.updated_allowed_material.pk],
                "description": "updated in place",
                "sources": [self.source.pk],
                "flyer_urls": ["https://example.com/updated-flyer"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["updated"])

        self.private_predecessor.refresh_from_db()
        self.assertEqual(self.private_predecessor.description, "updated in place")
        self.assertEqual(
            list(
                self.private_predecessor.allowed_materials.values_list(
                    "name", flat=True
                )
            ),
            [self.updated_allowed_material.name],
        )
        self.assertTrue(
            self.private_predecessor.sources.filter(pk=self.source.pk).exists()
        )
        self.assertTrue(
            self.private_predecessor.flyers.filter(
                url="https://example.com/updated-flyer"
            ).exists()
        )

    def test_update_endpoint_replaces_sources_when_provided(self):
        self.client.force_login(self.owner)
        stale_source = Source.objects.create(
            owner=self.owner,
            title="Stale Agent Source",
            abbreviation="StaleAgentSource",
            url="https://example.com/stale-source",
        )
        stale_flyer = WasteFlyer.objects.create(
            owner=self.owner,
            title="Stale Agent Flyer",
            publication_status="private",
            url="https://example.com/stale-flyer",
        )
        self.private_predecessor.sources.add(stale_source)
        self.private_predecessor.flyers.add(stale_flyer)

        response = self.client.post(
            reverse(
                "api-waste-collection-update",
                kwargs={"pk": self.private_predecessor.pk},
            ),
            {
                "expected_catchment": str(self.private_predecessor.catchment),
                "expected_waste_category": str(
                    self.private_predecessor.effective_waste_category
                ),
                "expected_collection_system": str(
                    self.private_predecessor.collection_system
                ),
                "expected_publication_status": self.private_predecessor.publication_status,
                "expected_valid_from": self.private_predecessor.valid_from.isoformat(),
                "sources": [self.source.pk],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.private_predecessor.refresh_from_db()
        self.assertEqual(
            list(self.private_predecessor.sources.values_list("pk", flat=True)),
            [self.source.pk],
        )
        self.assertEqual(
            list(self.private_predecessor.flyers.values_list("pk", flat=True)),
            [stale_flyer.pk],
        )

    def test_update_endpoint_replaces_flyers_when_provided(self):
        self.client.force_login(self.owner)
        stale_source = Source.objects.create(
            owner=self.owner,
            title="Stale Agent Source",
            abbreviation="StaleAgentSource2",
            url="https://example.com/stale-source-2",
        )
        stale_flyer = WasteFlyer.objects.create(
            owner=self.owner,
            title="Stale Agent Flyer",
            publication_status="private",
            url="https://example.com/stale-flyer-2",
        )
        self.private_predecessor.sources.add(stale_source)
        self.private_predecessor.flyers.add(stale_flyer)

        response = self.client.post(
            reverse(
                "api-waste-collection-update",
                kwargs={"pk": self.private_predecessor.pk},
            ),
            {
                "expected_catchment": str(self.private_predecessor.catchment),
                "expected_waste_category": str(
                    self.private_predecessor.effective_waste_category
                ),
                "expected_collection_system": str(
                    self.private_predecessor.collection_system
                ),
                "expected_publication_status": self.private_predecessor.publication_status,
                "expected_valid_from": self.private_predecessor.valid_from.isoformat(),
                "flyer_urls": ["https://example.com/replacement-flyer"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.private_predecessor.refresh_from_db()
        self.assertEqual(
            list(self.private_predecessor.sources.values_list("pk", flat=True)),
            [stale_source.pk],
        )
        self.assertEqual(
            list(self.private_predecessor.flyers.values_list("url", flat=True)),
            ["https://example.com/replacement-flyer"],
        )

    def test_update_endpoint_accepts_id_identity_comments_alias_and_string_flyers(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse(
                "api-waste-collection-update",
                kwargs={"pk": self.private_predecessor.pk},
            ),
            {
                "expected_catchment_id": self.private_predecessor.catchment_id,
                "expected_waste_category_id": self.private_predecessor.waste_category_id,
                "expected_collection_system_id": (
                    self.private_predecessor.collection_system_id
                ),
                "expected_publication_status": self.private_predecessor.publication_status,
                "expected_valid_from": self.private_predecessor.valid_from.isoformat(),
                "collector": self.updated_collector.pk,
                "comments": "updated via comments alias",
                "flyer_urls": "https://example.com/alias-flyer-a, https://example.com/alias-flyer-b",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["updated"])

        self.private_predecessor.refresh_from_db()
        self.assertEqual(self.private_predecessor.collector, self.updated_collector)
        self.assertEqual(
            self.private_predecessor.description, "updated via comments alias"
        )
        self.assertTrue(
            self.private_predecessor.flyers.filter(
                url="https://example.com/alias-flyer-a"
            ).exists()
        )
        self.assertTrue(
            self.private_predecessor.flyers.filter(
                url="https://example.com/alias-flyer-b"
            ).exists()
        )

    def test_create_endpoint_accepts_comments_alias_and_string_flyers(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("api-waste-collection-create"),
            {
                "catchment": self.catchment.pk,
                "waste_category": self.waste_category.pk,
                "collection_system": self.collection_system.pk,
                "valid_from": "2025-05-01",
                "comments": "created via comments alias",
                "flyer_urls": "https://example.com/create-flyer-a, https://example.com/create-flyer-b",
                "submit_for_review": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        collection = Collection.objects.get(pk=response.data["id"])
        self.assertEqual(collection.description, "created via comments alias")
        self.assertTrue(
            collection.flyers.filter(url="https://example.com/create-flyer-a").exists()
        )
        self.assertTrue(
            collection.flyers.filter(url="https://example.com/create-flyer-b").exists()
        )

    def test_new_version_with_add_permission_succeeds(self):
        self.client.force_login(self.other_user)

        response = self.client.post(
            reverse(
                "api-waste-collection-new-version",
                kwargs={"pk": self.predecessor.pk},
            ),
            {
                "valid_from": "2025-03-01",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        successor = Collection.objects.get(pk=response.data["id"])
        self.assertEqual(successor.owner, self.other_user)
        self.assertTrue(successor.predecessors.filter(pk=self.predecessor.pk).exists())

    def test_new_version_without_add_permission_is_denied_for_published_predecessor(
        self,
    ):
        user = User.objects.create_user(username="agent-no-add-version")
        self.client.force_login(user)

        response = self.client.post(
            reverse(
                "api-waste-collection-new-version",
                kwargs={"pk": self.predecessor.pk},
            ),
            {"valid_from": "2025-03-15"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_new_version_rejects_private_predecessor_of_other_user(self):
        user = User.objects.create_user(username="agent-private-denied")
        user.user_permissions.add(self.add_collection_permission)
        self.client.force_login(user)

        response = self.client.post(
            reverse(
                "api-waste-collection-new-version",
                kwargs={"pk": self.private_predecessor.pk},
            ),
            {"valid_from": "2025-04-01"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_new_version_allows_own_private_predecessor_with_add_permission(self):
        user = User.objects.create_user(username="agent-own-private")
        user.user_permissions.add(self.add_collection_permission)
        own_predecessor = Collection.objects.create(
            owner=user,
            publication_status="private",
            catchment=self.catchment,
            collector=self.collector,
            collection_system=self.collection_system,
            waste_category=self.waste_category,
            frequency=self.frequency,
            fee_system=self.fee_system,
            sorting_method=self.sorting_method,
            valid_from=date(2024, 7, 1),
            description="own private predecessor",
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse(
                "api-waste-collection-new-version",
                kwargs={"pk": own_predecessor.pk},
            ),
            {"valid_from": "2025-04-02"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        successor = Collection.objects.get(pk=response.data["id"])
        self.assertEqual(successor.owner, user)
        self.assertTrue(successor.predecessors.filter(pk=own_predecessor.pk).exists())

    def test_new_version_creates_predecessor_link_and_submits(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse(
                "api-waste-collection-new-version",
                kwargs={"pk": self.predecessor.pk},
            ),
            {
                "valid_from": "2025-03-01",
                "description": "agent successor",
                "submit_for_review": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["predecessor_id"], self.predecessor.pk)
        self.assertTrue(response.data["submitted"])

        successor = Collection.objects.get(pk=response.data["id"])
        self.assertTrue(successor.predecessors.filter(pk=self.predecessor.pk).exists())
        self.assertEqual(successor.publication_status, "review")
        self.assertIsNotNone(successor.submitted_at)
        self.assertEqual(successor.sources.count(), 1)
        self.assertTrue(successor.flyers.filter(pk=self.predecessor_flyer.pk).exists())
        self.assertTrue(
            ReviewAction.for_object(successor)
            .filter(action=ReviewAction.ACTION_SUBMITTED)
            .exists()
        )

    def test_new_version_accepts_comments_alias_and_string_flyers(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse(
                "api-waste-collection-new-version",
                kwargs={"pk": self.predecessor.pk},
            ),
            {
                "valid_from": "2025-04-01",
                "comments": "successor via comments alias",
                "flyer_urls": "https://example.com/version-flyer-a, https://example.com/version-flyer-b",
                "submit_for_review": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        successor = Collection.objects.get(pk=response.data["id"])
        self.assertEqual(successor.description, "successor via comments alias")
        self.assertTrue(
            successor.flyers.filter(url="https://example.com/version-flyer-a").exists()
        )
        self.assertTrue(
            successor.flyers.filter(url="https://example.com/version-flyer-b").exists()
        )


class GreenWasteCollectionSystemCountViewSetTests(APITestCase):
    """Tests for Green Waste collection-system count atlas endpoint."""

    endpoint = "/waste_collection/api/waste-atlas/green-waste-collection-system-count/"

    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(name="Region DE", country="DE")
        cls.catchment_a = CollectionCatchment.objects.create(
            name="Catchment A",
            region=cls.region,
        )
        cls.catchment_b = CollectionCatchment.objects.create(
            name="Catchment B",
            region=cls.region,
        )

        cls.d2d = CollectionSystem.objects.create(name="Door to door")
        cls.bring_point = CollectionSystem.objects.create(name="Bring point")
        cls.recycling = CollectionSystem.objects.create(name="Recycling centre")

        cls.green_category = WasteCategory.objects.create(name="Green waste")
        cls.bio_category = WasteCategory.objects.create(name="Biowaste")

        cls._create_collection(
            catchment=cls.catchment_a,
            waste_category=cls.green_category,
            collection_system=cls.d2d,
            year=2024,
        )
        cls._create_collection(
            catchment=cls.catchment_a,
            waste_category=cls.green_category,
            collection_system=cls.bring_point,
            year=2024,
        )
        # Duplicate system should not increase distinct system count.
        cls._create_collection(
            catchment=cls.catchment_a,
            waste_category=cls.green_category,
            collection_system=cls.bring_point,
            year=2024,
        )

        cls._create_collection(
            catchment=cls.catchment_b,
            waste_category=cls.green_category,
            collection_system=cls.recycling,
            year=2024,
        )
        # Non-green category in the same catchment must be ignored.
        cls._create_collection(
            catchment=cls.catchment_b,
            waste_category=cls.bio_category,
            collection_system=cls.d2d,
            year=2024,
        )
        # Different year must be ignored for year=2024 filter.
        cls._create_collection(
            catchment=cls.catchment_b,
            waste_category=cls.green_category,
            collection_system=cls.bring_point,
            year=2022,
        )

    @classmethod
    def _create_collection(cls, *, catchment, waste_category, collection_system, year):
        """Create a collection row for atlas endpoint test data."""
        return Collection.objects.create(
            name=f"{catchment.name}-{collection_system.name}-{year}",
            catchment=catchment,
            waste_category=waste_category,
            collection_system=collection_system,
            valid_from=date(year, 1, 1),
        )

    def test_returns_distinct_green_waste_system_count_per_catchment(self):
        """It counts distinct systems for Green waste category only."""
        response = self.client.get(self.endpoint, {"country": "DE", "year": 2024})

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        count_by_catchment = {
            row["catchment_id"]: row["collection_system_count"] for row in response.data
        }

        self.assertEqual(count_by_catchment[self.catchment_a.id], 2)
        self.assertEqual(count_by_catchment[self.catchment_b.id], 1)
        self.assertEqual(len(count_by_catchment), 2)


class SortingMethodViewSetTests(APITestCase):
    """Tests for sorting-method atlas endpoint."""

    endpoint = "/waste_collection/api/waste-atlas/sorting-method/"

    @classmethod
    def setUpTestData(cls):
        cls.region_se = Region.objects.create(name="Region SE", country="SE")
        cls.region_de = Region.objects.create(name="Region DE", country="DE")

        cls.catchment_a = CollectionCatchment.objects.create(
            name="SE Catchment A",
            region=cls.region_se,
        )
        cls.catchment_b = CollectionCatchment.objects.create(
            name="SE Catchment B",
            region=cls.region_se,
        )
        cls.catchment_c = CollectionCatchment.objects.create(
            name="SE Catchment C",
            region=cls.region_se,
        )
        cls.catchment_other_country = CollectionCatchment.objects.create(
            name="DE Catchment",
            region=cls.region_de,
        )

        cls.d2d = CollectionSystem.objects.create(name="Door to door")
        cls.bring_point = CollectionSystem.objects.create(name="Bring point")
        cls.no_collection = CollectionSystem.objects.create(
            name="No separate collection"
        )

        cls.separate_bins = SortingMethod.objects.create(name="Separate bins")
        cls.optical_sorting = SortingMethod.objects.create(name="Optical bag sorting")

        cls.food_category = WasteCategory.objects.create(name="Food waste")

        cls._create_collection(
            catchment=cls.catchment_a,
            collection_system=cls.d2d,
            sorting_method=cls.separate_bins,
            year=2023,
        )
        # Lower-priority system must not override the door-to-door sorting method.
        cls._create_collection(
            catchment=cls.catchment_a,
            collection_system=cls.bring_point,
            sorting_method=cls.optical_sorting,
            year=2023,
        )
        cls._create_collection(
            catchment=cls.catchment_b,
            collection_system=cls.no_collection,
            sorting_method=None,
            year=2023,
        )
        cls._create_collection(
            catchment=cls.catchment_c,
            collection_system=cls.d2d,
            sorting_method=None,
            year=2023,
        )
        cls._create_collection(
            catchment=cls.catchment_other_country,
            collection_system=cls.d2d,
            sorting_method=cls.optical_sorting,
            year=2023,
        )
        cls._create_collection(
            catchment=cls.catchment_a,
            collection_system=cls.d2d,
            sorting_method=cls.optical_sorting,
            year=2024,
        )

    @classmethod
    def _create_collection(
        cls,
        *,
        catchment,
        collection_system,
        sorting_method,
        year,
    ):
        """Create a collection row for sorting-method endpoint tests."""
        return Collection.objects.create(
            name=f"{catchment.name}-{collection_system.name}-{year}",
            catchment=catchment,
            waste_category=cls.food_category,
            collection_system=collection_system,
            sorting_method=sorting_method,
            valid_from=date(year, 1, 1),
        )

    def test_returns_sorting_method_with_expected_fallbacks(self):
        """Endpoint returns primary sorting method, no-collection and no-data fallbacks."""
        response = self.client.get(self.endpoint, {"country": "SE", "year": 2023})

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        by_catchment = {
            row["catchment_id"]: row["sorting_method"] for row in response.data
        }
        self.assertEqual(by_catchment[self.catchment_a.id], "Separate bins")
        self.assertEqual(by_catchment[self.catchment_b.id], "No separate collection")
        self.assertEqual(by_catchment[self.catchment_c.id], "no_data")
        self.assertNotIn(self.catchment_other_country.id, by_catchment)


class NutsPrefixAtlasFilteringTests(APITestCase):
    """Regression tests for nuts_prefix filtering across Waste Atlas endpoints."""

    @classmethod
    def setUpTestData(cls):
        cls.be1_region = NutsRegion.objects.create(
            name="Brussels",
            country="BE",
            cntr_code="BE",
            nuts_id="BE1",
            levl_code=1,
            borders=GeoPolygon.objects.create(),
        )
        cls.be2_region = NutsRegion.objects.create(
            name="Flanders",
            country="BE",
            cntr_code="BE",
            nuts_id="BE2",
            levl_code=1,
            borders=GeoPolygon.objects.create(),
        )
        cls.be3_region = NutsRegion.objects.create(
            name="Wallonia",
            country="BE",
            cntr_code="BE",
            nuts_id="BE3",
            levl_code=1,
            borders=GeoPolygon.objects.create(),
        )

        cls.catchment_be1 = CollectionCatchment.objects.create(
            name="Brussels Catchment",
            region=cls.be1_region,
        )
        cls.catchment_be2 = CollectionCatchment.objects.create(
            name="Flanders Catchment",
            region=cls.be2_region,
        )
        cls.catchment_be3 = CollectionCatchment.objects.create(
            name="Wallonia Catchment",
            region=cls.be3_region,
        )

        cls.d2d = CollectionSystem.objects.create(name="Door to door")
        cls.biowaste_category = WasteCategory.objects.create(name="Biowaste")

        for catchment in (cls.catchment_be1, cls.catchment_be2, cls.catchment_be3):
            Collection.objects.create(
                name=f"{catchment.name} 2022",
                catchment=catchment,
                waste_category=cls.biowaste_category,
                collection_system=cls.d2d,
                valid_from=date(2022, 1, 1),
            )

    def test_collection_system_endpoint_respects_nuts_prefix(self):
        response = self.client.get(
            "/waste_collection/api/waste-atlas/collection-system/",
            {
                "country": "BE",
                "year": 2022,
                "nuts_prefix": "BE1,BE2",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        catchment_ids = {row["catchment_id"] for row in response.data}

        self.assertEqual(catchment_ids, {self.catchment_be1.id, self.catchment_be2.id})

    def test_catchment_geojson_endpoint_respects_nuts_prefix(self):
        response = self.client.get(
            "/waste_collection/api/waste-atlas/catchment/geojson/",
            {
                "country": "BE",
                "year": 2022,
                "nuts_prefix": "BE1,BE2",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        feature_ids = {
            feature["properties"]["catchment_id"]
            for feature in response.data["features"]
        }

        self.assertEqual(feature_ids, {self.catchment_be1.id, self.catchment_be2.id})


@override_settings(
    SOILCOM_SPECIFIC_WASTE_PROPERTY_ID=None,
    SOILCOM_TOTAL_WASTE_PROPERTY_ID=None,
    SOILCOM_SPECIFIC_WASTE_UNIT_ID=None,
    SOILCOM_TOTAL_WASTE_UNIT_ID=None,
    SOILCOM_POPULATION_ATTRIBUTE_ID=None,
    SOILCOM_SPECIFIC_WASTE_PROPERTY_NAME="specific waste collected [green-atlas-test]",
    SOILCOM_TOTAL_WASTE_PROPERTY_NAME="total waste collected [green-atlas-test]",
    SOILCOM_SPECIFIC_WASTE_UNIT_NAME="kg/(cap.*a) [green-atlas-test]",
    SOILCOM_TOTAL_WASTE_UNIT_NAME="Mg/a [green-atlas-test]",
    SOILCOM_POPULATION_ATTRIBUTE_NAME="Population [green-atlas-test]",
)
class GreenWasteCollectionAmountViewSetTests(APITestCase):
    """Tests for Green Waste collection amount atlas endpoint."""

    endpoint = "/waste_collection/api/waste-atlas/green-waste-collection-amount/"

    @classmethod
    def setUpTestData(cls):
        cls.specific_property = Property.objects.create(
            name="specific waste collected [green-atlas-test]"
        )
        cls.total_property = Property.objects.create(
            name="total waste collected [green-atlas-test]"
        )
        cls.specific_unit = Unit.objects.create(name="kg/(cap.*a) [green-atlas-test]")
        cls.total_unit = Unit.objects.create(name="Mg/a [green-atlas-test]")
        cls.population_attribute = Attribute.objects.create(
            name="Population [green-atlas-test]",
            unit="cap",
        )

        cls.region = Region.objects.create(name="Region DE Amount", country="DE")
        cls.green_category, _ = WasteCategory.objects.get_or_create(name="Green waste")
        cls.bio_category, _ = WasteCategory.objects.get_or_create(name="Biowaste")

        cls.d2d, _ = CollectionSystem.objects.get_or_create(name="Door to door")
        cls.bring_point, _ = CollectionSystem.objects.get_or_create(name="Bring point")
        cls.no_collection, _ = CollectionSystem.objects.get_or_create(
            name="No separate collection"
        )

        cls.catchment_agg = CollectionCatchment.objects.create(
            name="GW Amount Aggregated",
            region=cls.region,
        )
        cls.catchment_specific = CollectionCatchment.objects.create(
            name="GW Amount Specific",
            region=cls.region,
        )
        cls.catchment_total = CollectionCatchment.objects.create(
            name="GW Amount Total",
            region=cls.region,
        )
        cls.catchment_agg_total = CollectionCatchment.objects.create(
            name="GW Amount Aggregated Total",
            region=cls.region,
        )
        cls.catchment_no_collection = CollectionCatchment.objects.create(
            name="GW Amount No Collection",
            region=cls.region,
        )
        cls.catchment_ignored = CollectionCatchment.objects.create(
            name="GW Amount Ignored",
            region=cls.region,
        )

        cls.agg_collection_a = cls._create_collection(
            catchment=cls.catchment_agg,
            waste_category=cls.green_category,
            collection_system=cls.d2d,
            year=2024,
        )
        cls.agg_collection_b = cls._create_collection(
            catchment=cls.catchment_agg,
            waste_category=cls.green_category,
            collection_system=cls.bring_point,
            year=2024,
        )

        cls.specific_collection = cls._create_collection(
            catchment=cls.catchment_specific,
            waste_category=cls.green_category,
            collection_system=cls.d2d,
            year=2024,
        )
        cls.total_collection = cls._create_collection(
            catchment=cls.catchment_total,
            waste_category=cls.green_category,
            collection_system=cls.d2d,
            year=2024,
        )
        cls.agg_total_collection = cls._create_collection(
            catchment=cls.catchment_agg_total,
            waste_category=cls.green_category,
            collection_system=cls.d2d,
            year=2024,
        )
        cls.no_collection_collection = cls._create_collection(
            catchment=cls.catchment_no_collection,
            waste_category=cls.green_category,
            collection_system=cls.no_collection,
            year=2024,
        )
        cls._create_collection(
            catchment=cls.catchment_ignored,
            waste_category=cls.bio_category,
            collection_system=cls.d2d,
            year=2024,
        )

        cls._create_cpv(
            collection=cls.agg_collection_a,
            property_obj=cls.specific_property,
            unit_obj=cls.specific_unit,
            year=2024,
            average=80.0,
        )
        cls._create_agg_value(
            collections=[cls.agg_collection_a, cls.agg_collection_b],
            property_obj=cls.specific_property,
            unit_obj=cls.specific_unit,
            year=2024,
            average=120.0,
        )

        cls._create_cpv(
            collection=cls.specific_collection,
            property_obj=cls.specific_property,
            unit_obj=cls.specific_unit,
            year=2024,
            average=90.0,
        )

        cls._create_cpv(
            collection=cls.total_collection,
            property_obj=cls.total_property,
            unit_obj=cls.total_unit,
            year=2024,
            average=50.0,
        )

        cls._create_agg_value(
            collections=[cls.agg_total_collection],
            property_obj=cls.total_property,
            unit_obj=cls.total_unit,
            year=2024,
            average=30.0,
        )

        RegionAttributeValue.objects.create(
            name="Population GW Amount",
            region=cls.region,
            attribute=cls.population_attribute,
            date=date(2024, 1, 1),
            value=1000,
        )

    def setUp(self):
        """Clear derived-value config cache before each test."""
        clear_derived_value_config_cache()

    def tearDown(self):
        """Clear derived-value config cache after each test."""
        clear_derived_value_config_cache()

    @classmethod
    def _create_collection(cls, *, catchment, waste_category, collection_system, year):
        """Create a collection row for green-waste amount endpoint test data."""
        return Collection.objects.create(
            name=f"{catchment.name}-{collection_system.name}-{year}",
            catchment=catchment,
            waste_category=waste_category,
            collection_system=collection_system,
            valid_from=date(year, 1, 1),
        )

    @classmethod
    def _create_cpv(cls, *, collection, property_obj, unit_obj, year, average):
        """Create one collection property value for a collection and year."""
        return CollectionPropertyValue.objects.create(
            name=f"CPV {collection.id} {property_obj.id} {year}",
            collection=collection,
            property=property_obj,
            unit=unit_obj,
            year=year,
            average=average,
            is_derived=False,
            publication_status="published",
        )

    @classmethod
    def _create_agg_value(cls, *, collections, property_obj, unit_obj, year, average):
        """Create one aggregated collection property value linked to collections."""
        agg = AggregatedCollectionPropertyValue.objects.create(
            name=f"ACPV {property_obj.id} {year} {average}",
            property=property_obj,
            unit=unit_obj,
            year=year,
            average=average,
            publication_status="published",
        )
        agg.collections.set(collections)
        return agg

    def test_returns_green_waste_amount_with_aggregation_and_fallbacks(self):
        """It prefers aggregated specific values and falls back to specific/total."""
        response = self.client.get(self.endpoint, {"country": "DE", "year": 2024})

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data_by_catchment = {row["catchment_id"]: row for row in response.data}

        self.assertEqual(data_by_catchment[self.catchment_agg.id]["amount"], 120.0)
        self.assertEqual(data_by_catchment[self.catchment_specific.id]["amount"], 90.0)
        self.assertEqual(data_by_catchment[self.catchment_total.id]["amount"], 50.0)
        self.assertEqual(data_by_catchment[self.catchment_agg_total.id]["amount"], 30.0)

        self.assertTrue(
            data_by_catchment[self.catchment_no_collection.id]["no_collection"]
        )
        self.assertIsNone(data_by_catchment[self.catchment_no_collection.id]["amount"])

        self.assertNotIn(self.catchment_ignored.id, data_by_catchment)


class BinSizeViewSetTests(APITestCase):
    """Regression tests for Karte 23-26 min bin size and required bin capacity endpoints."""

    @classmethod
    def setUpTestData(cls):
        cls.bio_category, _ = WasteCategory.objects.get_or_create(name="Biowaste")
        cls.residual_category, _ = WasteCategory.objects.get_or_create(
            name="Residual waste"
        )
        cls.green_category, _ = WasteCategory.objects.get_or_create(name="Green waste")

        cls.d2d, _ = CollectionSystem.objects.get_or_create(name="Door to door")
        cls.bring_point, _ = CollectionSystem.objects.get_or_create(name="Bring point")

        cls.region = Region.objects.create(name="Region BinSize DE", country="DE")

        cls.catchment_bio = CollectionCatchment.objects.create(
            name="BinSize Bio", region=cls.region
        )
        cls.catchment_residual = CollectionCatchment.objects.create(
            name="BinSize Residual", region=cls.region
        )
        cls.catchment_no_bin = CollectionCatchment.objects.create(
            name="BinSize NoBin", region=cls.region
        )
        cls.catchment_ignored = CollectionCatchment.objects.create(
            name="BinSize Ignored", region=cls.region
        )

        cls.bio_col = Collection.objects.create(
            name="BinSize bio col",
            catchment=cls.catchment_bio,
            waste_category=cls.bio_category,
            collection_system=cls.d2d,
            valid_from=date(2024, 1, 1),
            min_bin_size=80,
            required_bin_capacity=10,
            required_bin_capacity_reference="person",
        )
        cls.residual_col = Collection.objects.create(
            name="BinSize residual col",
            catchment=cls.catchment_residual,
            waste_category=cls.residual_category,
            collection_system=cls.d2d,
            valid_from=date(2024, 1, 1),
            min_bin_size=120,
            required_bin_capacity=40,
            required_bin_capacity_reference="household",
        )
        Collection.objects.create(
            name="BinSize no bin col",
            catchment=cls.catchment_no_bin,
            waste_category=cls.bio_category,
            collection_system=cls.d2d,
            valid_from=date(2024, 1, 1),
        )
        Collection.objects.create(
            name="BinSize bring point col",
            catchment=cls.catchment_ignored,
            waste_category=cls.bio_category,
            collection_system=cls.bring_point,
            valid_from=date(2024, 1, 1),
            min_bin_size=60,
        )

    def test_biowaste_min_bin_size_returns_d2d_collections(self):
        """Karte 23 returns min_bin_size for D2D biowaste catchments."""
        response = self.client.get(
            "/waste_collection/api/waste-atlas/biowaste-min-bin-size/",
            {"country": "DE", "year": 2024},
        )
        self.assertEqual(response.status_code, 200)
        by_catchment = {r["catchment_id"]: r for r in response.data}
        self.assertEqual(by_catchment[self.catchment_bio.id]["min_bin_size"], 80.0)
        self.assertIn(self.catchment_no_bin.id, by_catchment)
        self.assertIsNone(by_catchment[self.catchment_no_bin.id]["min_bin_size"])
        self.assertNotIn(self.catchment_residual.id, by_catchment)

    def test_biowaste_min_bin_size_excludes_non_d2d(self):
        """Karte 23 excludes bring-point and other non-D2D collections."""
        response = self.client.get(
            "/waste_collection/api/waste-atlas/biowaste-min-bin-size/",
            {"country": "DE", "year": 2024},
        )
        by_catchment = {r["catchment_id"]: r for r in response.data}
        self.assertNotIn(self.catchment_ignored.id, by_catchment)

    def test_residual_min_bin_size_returns_d2d_collections(self):
        """Karte 24 returns min_bin_size for D2D residual catchments."""
        response = self.client.get(
            "/waste_collection/api/waste-atlas/residual-min-bin-size/",
            {"country": "DE", "year": 2024},
        )
        self.assertEqual(response.status_code, 200)
        by_catchment = {r["catchment_id"]: r for r in response.data}
        self.assertEqual(
            by_catchment[self.catchment_residual.id]["min_bin_size"], 120.0
        )
        self.assertNotIn(self.catchment_bio.id, by_catchment)

    def test_biowaste_required_bin_capacity_returns_value_and_reference(self):
        """Karte 25 returns required_bin_capacity and reference for biowaste D2D."""
        response = self.client.get(
            "/waste_collection/api/waste-atlas/biowaste-required-bin-capacity/",
            {"country": "DE", "year": 2024},
        )
        self.assertEqual(response.status_code, 200)
        by_catchment = {r["catchment_id"]: r for r in response.data}
        row = by_catchment[self.catchment_bio.id]
        self.assertEqual(row["required_bin_capacity"], 10.0)
        self.assertEqual(row["required_bin_capacity_reference"], "person")
        self.assertNotIn(self.catchment_residual.id, by_catchment)

    def test_biowaste_required_bin_capacity_null_when_not_set(self):
        """Karte 25 returns null capacity for catchments without the field set."""
        response = self.client.get(
            "/waste_collection/api/waste-atlas/biowaste-required-bin-capacity/",
            {"country": "DE", "year": 2024},
        )
        by_catchment = {r["catchment_id"]: r for r in response.data}
        row = by_catchment[self.catchment_no_bin.id]
        self.assertIsNone(row["required_bin_capacity"])
        self.assertIsNone(row["required_bin_capacity_reference"])

    def test_residual_required_bin_capacity_returns_value_and_reference(self):
        """Karte 26 returns required_bin_capacity and reference for residual D2D."""
        response = self.client.get(
            "/waste_collection/api/waste-atlas/residual-required-bin-capacity/",
            {"country": "DE", "year": 2024},
        )
        self.assertEqual(response.status_code, 200)
        by_catchment = {r["catchment_id"]: r for r in response.data}
        row = by_catchment[self.catchment_residual.id]
        self.assertEqual(row["required_bin_capacity"], 40.0)
        self.assertEqual(row["required_bin_capacity_reference"], "household")
        self.assertNotIn(self.catchment_bio.id, by_catchment)


@override_settings(
    SOILCOM_SPECIFIC_WASTE_PROPERTY_ID=None,
    SOILCOM_TOTAL_WASTE_PROPERTY_ID=None,
    SOILCOM_SPECIFIC_WASTE_UNIT_ID=None,
    SOILCOM_TOTAL_WASTE_UNIT_ID=None,
    SOILCOM_POPULATION_ATTRIBUTE_ID=None,
    SOILCOM_SPECIFIC_WASTE_PROPERTY_NAME="specific waste collected [organic-atlas-test]",
    SOILCOM_TOTAL_WASTE_PROPERTY_NAME="total waste collected [organic-atlas-test]",
    SOILCOM_SPECIFIC_WASTE_UNIT_NAME="kg/(cap.*a) [organic-atlas-test]",
    SOILCOM_TOTAL_WASTE_UNIT_NAME="Mg/a [organic-atlas-test]",
    SOILCOM_POPULATION_ATTRIBUTE_NAME="Population [organic-atlas-test]",
)
class OrganicAmountViewSetTests(APITestCase):
    """Regression tests for Karte 27 (organic amount) and Karte 28 (organic ratio)."""

    @classmethod
    def setUpTestData(cls):
        clear_derived_value_config_cache()

        cls.specific_property = Property.objects.create(
            name="specific waste collected [organic-atlas-test]"
        )
        cls.total_property = Property.objects.create(
            name="total waste collected [organic-atlas-test]"
        )
        cls.specific_unit = Unit.objects.create(name="kg/(cap.*a) [organic-atlas-test]")
        cls.total_unit = Unit.objects.create(name="Mg/a [organic-atlas-test]")
        cls.population_attribute = Attribute.objects.create(
            name="Population [organic-atlas-test]",
            unit="cap",
        )

        cls.bio_category, _ = WasteCategory.objects.get_or_create(name="Biowaste")
        cls.green_category, _ = WasteCategory.objects.get_or_create(name="Green waste")
        cls.residual_category, _ = WasteCategory.objects.get_or_create(
            name="Residual waste"
        )

        cls.d2d, _ = CollectionSystem.objects.get_or_create(name="Door to door")

        cls.region = Region.objects.create(name="Region Organic DE", country="DE")

        cls.catchment_both = CollectionCatchment.objects.create(
            name="Organic Both", region=cls.region
        )
        cls.catchment_bio_only = CollectionCatchment.objects.create(
            name="Organic Bio Only", region=cls.region
        )
        cls.catchment_green_only = CollectionCatchment.objects.create(
            name="Organic Green Only", region=cls.region
        )
        cls.catchment_residual_only = CollectionCatchment.objects.create(
            name="Organic Residual Only", region=cls.region
        )

        bio_col_both = Collection.objects.create(
            name="Organic bio both",
            catchment=cls.catchment_both,
            waste_category=cls.bio_category,
            collection_system=cls.d2d,
            valid_from=date(2024, 1, 1),
        )
        CollectionPropertyValue.objects.create(
            collection=bio_col_both,
            property=cls.specific_property,
            unit=cls.specific_unit,
            year=2024,
            average=100.0,
        )

        green_col_both = Collection.objects.create(
            name="Organic green both",
            catchment=cls.catchment_both,
            waste_category=cls.green_category,
            collection_system=cls.d2d,
            valid_from=date(2024, 1, 1),
        )
        acpv = AggregatedCollectionPropertyValue.objects.create(
            name="Organic green ACPV both",
            property=cls.specific_property,
            unit=cls.specific_unit,
            year=2024,
            average=80.0,
            publication_status="published",
        )
        acpv.collections.set([green_col_both])

        residual_col_both = Collection.objects.create(
            name="Organic residual both",
            catchment=cls.catchment_both,
            waste_category=cls.residual_category,
            collection_system=cls.d2d,
            valid_from=date(2024, 1, 1),
        )
        CollectionPropertyValue.objects.create(
            collection=residual_col_both,
            property=cls.specific_property,
            unit=cls.specific_unit,
            year=2024,
            average=200.0,
        )

        bio_col_bio_only = Collection.objects.create(
            name="Organic bio only col",
            catchment=cls.catchment_bio_only,
            waste_category=cls.bio_category,
            collection_system=cls.d2d,
            valid_from=date(2024, 1, 1),
        )
        CollectionPropertyValue.objects.create(
            collection=bio_col_bio_only,
            property=cls.specific_property,
            unit=cls.specific_unit,
            year=2024,
            average=60.0,
        )

        green_col_green_only = Collection.objects.create(
            name="Organic green only col",
            catchment=cls.catchment_green_only,
            waste_category=cls.green_category,
            collection_system=cls.d2d,
            valid_from=date(2024, 1, 1),
        )
        CollectionPropertyValue.objects.create(
            collection=green_col_green_only,
            property=cls.specific_property,
            unit=cls.specific_unit,
            year=2024,
            average=50.0,
        )

        residual_col_only = Collection.objects.create(
            name="Organic residual only col",
            catchment=cls.catchment_residual_only,
            waste_category=cls.residual_category,
            collection_system=cls.d2d,
            valid_from=date(2024, 1, 1),
        )
        CollectionPropertyValue.objects.create(
            collection=residual_col_only,
            property=cls.specific_property,
            unit=cls.specific_unit,
            year=2024,
            average=150.0,
        )

    def setUp(self):
        clear_derived_value_config_cache()

    def test_organic_amount_sums_bio_and_green(self):
        """Karte 27 returns the sum of bio + green waste amounts per catchment."""
        response = self.client.get(
            "/waste_collection/api/waste-atlas/organic-collection-amount/",
            {"country": "DE", "year": 2024},
        )
        self.assertEqual(response.status_code, 200)
        by_catchment = {r["catchment_id"]: r for r in response.data}
        self.assertAlmostEqual(by_catchment[self.catchment_both.id]["amount"], 180.0)

    def test_organic_amount_bio_only_catchment(self):
        """Karte 27 includes catchments with only bio waste."""
        response = self.client.get(
            "/waste_collection/api/waste-atlas/organic-collection-amount/",
            {"country": "DE", "year": 2024},
        )
        by_catchment = {r["catchment_id"]: r for r in response.data}
        self.assertAlmostEqual(by_catchment[self.catchment_bio_only.id]["amount"], 60.0)

    def test_organic_amount_green_only_catchment(self):
        """Karte 27 includes catchments with only green waste."""
        response = self.client.get(
            "/waste_collection/api/waste-atlas/organic-collection-amount/",
            {"country": "DE", "year": 2024},
        )
        by_catchment = {r["catchment_id"]: r for r in response.data}
        self.assertAlmostEqual(
            by_catchment[self.catchment_green_only.id]["amount"], 50.0
        )

    def test_organic_amount_excludes_residual_only_catchment(self):
        """Karte 27 does not include catchments with residual waste only."""
        response = self.client.get(
            "/waste_collection/api/waste-atlas/organic-collection-amount/",
            {"country": "DE", "year": 2024},
        )
        by_catchment = {r["catchment_id"]: r for r in response.data}
        self.assertNotIn(self.catchment_residual_only.id, by_catchment)

    def test_organic_ratio_computed_correctly(self):
        """Karte 28 computes organic / (organic + residual) for catchments with both."""
        response = self.client.get(
            "/waste_collection/api/waste-atlas/organic-waste-ratio/",
            {"country": "DE", "year": 2024},
        )
        self.assertEqual(response.status_code, 200)
        by_catchment = {r["catchment_id"]: r for r in response.data}
        row = by_catchment[self.catchment_both.id]
        self.assertAlmostEqual(row["organic_amount"], 180.0)
        self.assertAlmostEqual(row["residual_amount"], 200.0)
        self.assertAlmostEqual(row["ratio"], 180.0 / 380.0, places=4)

    def test_organic_ratio_null_when_only_organic(self):
        """Karte 28 returns null ratio for catchments without residual data."""
        response = self.client.get(
            "/waste_collection/api/waste-atlas/organic-waste-ratio/",
            {"country": "DE", "year": 2024},
        )
        by_catchment = {r["catchment_id"]: r for r in response.data}
        self.assertIsNone(by_catchment[self.catchment_bio_only.id]["ratio"])

    def test_organic_ratio_includes_residual_only_catchment(self):
        """Karte 28 includes residual-only catchments (null ratio)."""
        response = self.client.get(
            "/waste_collection/api/waste-atlas/organic-waste-ratio/",
            {"country": "DE", "year": 2024},
        )
        by_catchment = {r["catchment_id"]: r for r in response.data}
        self.assertIn(self.catchment_residual_only.id, by_catchment)
        self.assertIsNone(by_catchment[self.catchment_residual_only.id]["ratio"])
