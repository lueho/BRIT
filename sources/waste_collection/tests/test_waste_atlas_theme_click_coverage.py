"""Every atlas map theme built from collections is clickable.

A reader who sees a value on a map wants the record behind it. Themes derived
from one primary collection open it directly; themes combining several streams
hand over every contributing collection. Only themes computed from region or
collector properties have no collection to open at all.
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
from sources.waste_collection.waste_atlas.pages import MAP_PAGES

CATCHMENT_GEOJSON_URL = "/waste_collection/api/waste-atlas/catchment/geojson/"

# Themes whose value describes a region or a collector, not a collection.
THEMES_WITHOUT_A_COLLECTION = {
    "population_density",
    "orga_level",
}


class ThemeClickCoverageTests(SimpleTestCase):
    """No map theme is left without a click target by accident."""

    def test_every_theme_except_region_properties_opens_a_collection(self):
        unclickable = {
            page["theme"]
            for page in MAP_PAGES
            if not collection_detail_categories_for_theme(page["theme"])
        }

        self.assertEqual(unclickable, THEMES_WITHOUT_A_COLLECTION)

    def test_single_stream_themes_open_the_collection_behind_the_value(self):
        expected = {
            "biowaste_collection_count": ("biowaste",),
            "biowaste_min_bin_size": ("biowaste",),
            "biowaste_required_bin_capacity": ("biowaste",),
            "collection_orga_level": ("all",),
            "connection_rate": ("biowaste",),
            "green_waste_collection_system_count": ("green_waste",),
            "residual_collection_count": ("residual",),
            "residual_min_bin_size": ("residual",),
            "residual_required_bin_capacity": ("residual",),
        }
        for theme, categories in expected.items():
            with self.subTest(theme=theme):
                self.assertEqual(
                    collection_detail_categories_for_theme(theme), categories
                )

    def test_combined_themes_offer_every_contributing_stream(self):
        expected = {
            "collection_point_count_ratio": ("biowaste", "residual"),
            "combined_collection_system": ("biowaste", "residual"),
            "min_bin_size_ratio": ("biowaste", "residual"),
            "system_access_control": ("biowaste", "residual"),
            "organic_waste_ratio": ("biowaste", "green_waste", "residual"),
        }
        for theme, categories in expected.items():
            with self.subTest(theme=theme):
                self.assertEqual(
                    collection_detail_categories_for_theme(theme), categories
                )


class ThreeStreamCollectionPickerTests(APITestCase):
    """A value built from three streams offers all three collections."""

    @classmethod
    def setUpTestData(cls):
        borders = GeoPolygon.objects.create(
            geom="MULTIPOLYGON(((0 0, 0 1, 1 1, 1 0, 0 0)))",
        )
        region = Region.objects.create(
            name="Ratio Region", country="DE", borders=borders
        )
        cls.catchment = CollectionCatchment.objects.create(
            name="Ratio Catchment", region=region
        )
        cls.user = User.objects.create_user(username="ratio-atlas-user")
        system = CollectionSystem.objects.create(name="Door to door")
        cls.collections = {}
        for category_name in ("Biowaste", "Green waste", "Residual waste"):
            category = WasteCategory.objects.create(name=category_name)
            cls.collections[category_name] = Collection.objects.create(
                name=f"Ratio {category_name} Collection",
                owner=cls.user,
                catchment=cls.catchment,
                waste_category=category,
                collection_system=system,
                valid_from=date(2024, 1, 1),
                publication_status="published",
            )

    def test_organic_waste_ratio_categories_expose_all_three_collections(self):
        response = self.client.get(
            CATCHMENT_GEOJSON_URL,
            {
                "country": "DE",
                "year": 2024,
                "collection_detail_category": ",".join(
                    collection_detail_categories_for_theme("organic_waste_ratio")
                ),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        properties = next(
            feature["properties"]
            for feature in response.data["features"]
            if feature["properties"]["catchment_id"] == self.catchment.id
        )

        self.assertEqual(
            [detail["url"] for detail in properties["collection_details"]],
            [
                reverse("collection-detail", kwargs={"pk": collection.pk})
                for collection in (
                    self.collections["Biowaste"],
                    self.collections["Green waste"],
                    self.collections["Residual waste"],
                )
            ],
        )
