from unittest.mock import patch

from django.urls import reverse
from rest_framework import status

from sources.waste_collection.models import Collection
from sources.waste_collection.tests.test_viewsets import CollectionViewSetTestCase


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
