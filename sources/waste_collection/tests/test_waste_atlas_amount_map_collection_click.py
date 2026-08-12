"""Collected-amount maps open the collection behind the displayed amount.

Every amount theme resolves its value from one primary collection per waste
stream, so a click has an unambiguous target: one collection for the single
stream maps, one per stream for the aggregated organic map.
"""

from datetime import date

from django.contrib.auth.models import User
from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from maps.models import GeoPolygon, Region
from sources.waste_collection.models import (
    Collection,
    CollectionCatchment,
    CollectionSystem,
    WasteCategory,
)
from sources.waste_collection.waste_atlas.map_selection import (
    collection_detail_categories_for_theme,
)

CATCHMENT_GEOJSON_URL = "/waste_collection/api/waste-atlas/catchment/geojson/"


class AmountThemeCollectionDetailCategoryTests(SimpleTestCase):
    """Amount themes resolve to the streams contributing the amount."""

    def test_single_stream_amount_themes_open_their_own_stream(self):
        self.assertEqual(
            collection_detail_categories_for_theme("biowaste_collection_amount"),
            ("biowaste",),
        )
        self.assertEqual(
            collection_detail_categories_for_theme("residual_collection_amount"),
            ("residual",),
        )
        self.assertEqual(
            collection_detail_categories_for_theme("green_waste_collection_amount"),
            ("green_waste",),
        )

    def test_organic_amount_theme_offers_both_contributing_streams(self):
        self.assertEqual(
            collection_detail_categories_for_theme("organic_collection_amount"),
            ("biowaste", "green_waste"),
        )


class GreenWasteCollectionDetailCategoryTests(APITestCase):
    """The GeoJSON understands the green waste stream as a click target."""

    @classmethod
    def setUpTestData(cls):
        borders = GeoPolygon.objects.create(
            geom="MULTIPOLYGON(((0 0, 0 1, 1 1, 1 0, 0 0)))",
        )
        cls.region = Region.objects.create(
            name="Amount Region", country="DE", borders=borders
        )
        cls.catchment = CollectionCatchment.objects.create(
            name="Amount Catchment", region=cls.region
        )
        cls.user = User.objects.create_user(username="amount-atlas-user")
        cls.system = CollectionSystem.objects.create(name="Bring point")
        cls.green_waste = WasteCategory.objects.create(name="Green waste")
        cls.collection = Collection.objects.create(
            name="Amount Green Waste Collection",
            owner=cls.user,
            catchment=cls.catchment,
            waste_category=cls.green_waste,
            collection_system=cls.system,
            valid_from=date(2024, 1, 1),
            publication_status="published",
        )

    def test_green_waste_category_exposes_its_collection(self):
        response = self.client.get(
            CATCHMENT_GEOJSON_URL,
            {
                "country": "DE",
                "year": 2024,
                "collection_detail_category": "green_waste",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        properties = next(
            feature["properties"]
            for feature in response.data["features"]
            if feature["properties"]["catchment_id"] == self.catchment.id
        )

        self.assertEqual(
            properties["collection_detail_url"],
            reverse("collection-detail", kwargs={"pk": self.collection.id}),
        )
