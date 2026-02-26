from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIRequestFactory, APITestCase

from case_studies.soilcom.derived_values import clear_derived_value_config_cache
from case_studies.soilcom.importers import CollectionImporter
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
from maps.models import Attribute, Region, RegionAttributeValue
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

    @patch("case_studies.soilcom.filters.ConnectionRateFilter.set_min_max")
    def test_version_endpoint_skips_filter_min_max_initialization(
        self, mock_set_min_max
    ):
        """Version endpoint should avoid expensive range-widget min/max queries."""
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse("api-waste-collection-version"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_set_min_max.assert_not_called()

    @patch("case_studies.soilcom.filters.ConnectionRateFilter.set_min_max")
    def test_geojson_endpoint_skips_filter_min_max_initialization(
        self, mock_set_min_max
    ):
        """GeoJSON endpoint should avoid expensive range-widget min/max queries."""
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse("api-waste-collection-geojson"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_set_min_max.assert_not_called()

    @patch("case_studies.soilcom.filters.ConnectionRateFilter.set_min_max")
    def test_collection_filterset_still_initializes_min_max_by_default(
        self, mock_set_min_max
    ):
        """Default CollectionFilterSet initialization should still prepare form widgets."""
        from case_studies.soilcom.filters import CollectionFilterSet

        CollectionFilterSet(queryset=Collection.objects.all())
        mock_set_min_max.assert_called_once()

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
        cls.catchment = CollectionCatchment.objects.create(
            name="Importer Test Catchment"
        )
        cls.collection_system = CollectionSystem.objects.create(
            name="Importer Test System"
        )
        cls.waste_category = WasteCategory.objects.create(name="Importer Test Category")
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

        cls.green_stream = WasteStream.objects.create(category=cls.green_category)
        cls.bio_stream = WasteStream.objects.create(category=cls.bio_category)

        cls._create_collection(
            catchment=cls.catchment_a,
            waste_stream=cls.green_stream,
            collection_system=cls.d2d,
            year=2024,
        )
        cls._create_collection(
            catchment=cls.catchment_a,
            waste_stream=cls.green_stream,
            collection_system=cls.bring_point,
            year=2024,
        )
        # Duplicate system should not increase distinct system count.
        cls._create_collection(
            catchment=cls.catchment_a,
            waste_stream=cls.green_stream,
            collection_system=cls.bring_point,
            year=2024,
        )

        cls._create_collection(
            catchment=cls.catchment_b,
            waste_stream=cls.green_stream,
            collection_system=cls.recycling,
            year=2024,
        )
        # Non-green category in the same catchment must be ignored.
        cls._create_collection(
            catchment=cls.catchment_b,
            waste_stream=cls.bio_stream,
            collection_system=cls.d2d,
            year=2024,
        )
        # Different year must be ignored for year=2024 filter.
        cls._create_collection(
            catchment=cls.catchment_b,
            waste_stream=cls.green_stream,
            collection_system=cls.bring_point,
            year=2022,
        )

    @classmethod
    def _create_collection(cls, *, catchment, waste_stream, collection_system, year):
        """Create a collection row for atlas endpoint test data."""
        return Collection.objects.create(
            name=f"{catchment.name}-{collection_system.name}-{year}",
            catchment=catchment,
            waste_stream=waste_stream,
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
        cls.green_stream = WasteStream.objects.create(category=cls.green_category)
        cls.bio_stream = WasteStream.objects.create(category=cls.bio_category)

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
            waste_stream=cls.green_stream,
            collection_system=cls.d2d,
            year=2024,
        )
        cls.agg_collection_b = cls._create_collection(
            catchment=cls.catchment_agg,
            waste_stream=cls.green_stream,
            collection_system=cls.bring_point,
            year=2024,
        )

        cls.specific_collection = cls._create_collection(
            catchment=cls.catchment_specific,
            waste_stream=cls.green_stream,
            collection_system=cls.d2d,
            year=2024,
        )
        cls.total_collection = cls._create_collection(
            catchment=cls.catchment_total,
            waste_stream=cls.green_stream,
            collection_system=cls.d2d,
            year=2024,
        )
        cls.agg_total_collection = cls._create_collection(
            catchment=cls.catchment_agg_total,
            waste_stream=cls.green_stream,
            collection_system=cls.d2d,
            year=2024,
        )
        cls.no_collection_collection = cls._create_collection(
            catchment=cls.catchment_no_collection,
            waste_stream=cls.green_stream,
            collection_system=cls.no_collection,
            year=2024,
        )
        cls._create_collection(
            catchment=cls.catchment_ignored,
            waste_stream=cls.bio_stream,
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
    def _create_collection(cls, *, catchment, waste_stream, collection_system, year):
        """Create a collection row for green-waste amount endpoint test data."""
        return Collection.objects.create(
            name=f"{catchment.name}-{collection_system.name}-{year}",
            catchment=catchment,
            waste_stream=waste_stream,
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

        cls.bio_stream = WasteStream.objects.create(category=cls.bio_category)
        cls.residual_stream = WasteStream.objects.create(category=cls.residual_category)
        cls.green_stream = WasteStream.objects.create(category=cls.green_category)

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
            waste_stream=cls.bio_stream,
            collection_system=cls.d2d,
            valid_from=date(2024, 1, 1),
            min_bin_size=80,
            required_bin_capacity=10,
            required_bin_capacity_reference="person",
        )
        cls.residual_col = Collection.objects.create(
            name="BinSize residual col",
            catchment=cls.catchment_residual,
            waste_stream=cls.residual_stream,
            collection_system=cls.d2d,
            valid_from=date(2024, 1, 1),
            min_bin_size=120,
            required_bin_capacity=40,
            required_bin_capacity_reference="household",
        )
        Collection.objects.create(
            name="BinSize no bin col",
            catchment=cls.catchment_no_bin,
            waste_stream=cls.bio_stream,
            collection_system=cls.d2d,
            valid_from=date(2024, 1, 1),
        )
        Collection.objects.create(
            name="BinSize bring point col",
            catchment=cls.catchment_ignored,
            waste_stream=cls.bio_stream,
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

        cls.bio_stream = WasteStream.objects.create(category=cls.bio_category)
        cls.green_stream = WasteStream.objects.create(category=cls.green_category)
        cls.residual_stream = WasteStream.objects.create(category=cls.residual_category)

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
            waste_stream=cls.bio_stream,
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
            waste_stream=cls.green_stream,
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
            waste_stream=cls.residual_stream,
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
            waste_stream=cls.bio_stream,
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
            waste_stream=cls.green_stream,
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
            waste_stream=cls.residual_stream,
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
