from datetime import date
from unittest.mock import patch

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status

from maps.models import (
    LauRegion,
    NutsRegion,
    RegionAttributeValue,
    RegionProperty,
)
from sources.waste_collection.models import (
    Collection,
    CollectionCatchment,
)
from sources.waste_collection.tests.test_viewsets import CollectionViewSetTestCase
from utils.object_management.models import UserCreatedObject


class CollectionResearchPerformanceTests(CollectionViewSetTestCase):
    def test_list_endpoint_skips_expensive_collection_metrics(self):
        self.client.force_login(self.regular_user)

        with (
            patch.object(
                Collection,
                "collectionpropertyvalues_for_display",
                side_effect=AssertionError("collection metrics should not be loaded"),
            ),
            patch.object(
                Collection,
                "aggregatedcollectionpropertyvalues_for_display",
                side_effect=AssertionError(
                    "aggregated collection metrics should not be loaded"
                ),
            ),
        ):
            response = self.client.get(
                reverse("api-waste-collection-list"),
                {"scope": "private", "id": [self.private_collection.pk]},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self._response_results(response)
        result = next(
            item for item in results if item["id"] == self.private_collection.pk
        )
        self.assertNotIn("specific_waste_collected_2024", result)
        self.assertNotIn("connection_rate_2024", result)

    def _create_nuts_backed_collection(self, name, nuts_node):
        catchment = CollectionCatchment.objects.create(
            name=f"{name} Catchment", region=nuts_node.region_ptr
        )
        return Collection.objects.create(
            name=name,
            owner=self.regular_user,
            catchment=catchment,
            waste_category=self.waste_category,
            collection_system=self.collection_system,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
            collector=self.collector,
            fee_system=self.fee_system,
            frequency=self.frequency,
        )

    def test_list_endpoint_omits_export_only_dynamic_columns(self):
        nuts0 = NutsRegion.objects.create(
            name="Germany",
            country="DE",
            nuts_id="DE",
            levl_code=0,
            cntr_code="DE",
        )
        nuts3 = NutsRegion.objects.create(
            name="München, Landkreis",
            country="DE",
            nuts_id="DE212",
            levl_code=3,
            cntr_code="DE",
            parent=nuts0,
        )
        collection = self._create_nuts_backed_collection("NUTS3 Research", nuts3)
        population = RegionProperty.objects.create(name="Population", unit="")
        RegionAttributeValue.objects.create(
            region=nuts3.region_ptr,
            property=population,
            date=date(2020, 1, 1),
            value=1000,
        )

        self.client.force_login(self.regular_user)
        response = self.client.get(
            reverse("api-waste-collection-list"),
            {"scope": "private", "id": [collection.pk]},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = next(
            item
            for item in self._response_results(response)
            if item["id"] == collection.pk
        )
        self.assertIn("nuts_or_lau_id", result)
        self.assertIn("country", result)
        for key in (
            "nuts_0_id",
            "nuts_0_name",
            "nuts_3_id",
            "population_2020",
            "population_2020_unit",
        ):
            self.assertNotIn(key, result)

    def test_list_endpoint_does_not_walk_region_hierarchies_per_row(self):
        nuts0 = NutsRegion.objects.create(
            name="Germany",
            country="DE",
            nuts_id="DE",
            levl_code=0,
            cntr_code="DE",
        )
        nuts3 = NutsRegion.objects.create(
            name="München, Landkreis",
            country="DE",
            nuts_id="DE212",
            levl_code=3,
            cntr_code="DE",
            parent=nuts0,
        )
        self._create_nuts_backed_collection("NUTS3 Research", nuts3)

        lau = LauRegion.objects.create(
            name="München Stadt",
            country="DE",
            lau_id="09162000",
            nuts_parent=nuts3,
        )
        lau_catchment = CollectionCatchment.objects.create(
            name="LAU Catchment", region=lau.region_ptr
        )
        Collection.objects.create(
            name="LAU Research",
            owner=self.regular_user,
            catchment=lau_catchment,
            waste_category=self.waste_category,
            collection_system=self.collection_system,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )

        self.client.force_login(self.regular_user)
        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(
                reverse("api-waste-collection-list"), {"scope": "private"}
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        hierarchy_tables = (
            'FROM "maps_nutsregion"',
            'FROM "maps_lauregion"',
            'FROM "maps_regionattributevalue"',
        )
        hierarchy_queries = [
            query["sql"]
            for query in captured
            if any(table in query["sql"] for table in hierarchy_tables)
        ]
        self.assertEqual(hierarchy_queries, [])
