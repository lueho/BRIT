from datetime import date

from rest_framework import status
from rest_framework.test import APITestCase

from case_studies.soilcom.models import (
    Collection,
    CollectionCatchment,
    CollectionSystem,
    WasteCategory,
    WasteStream,
)
from maps.models import Region


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
