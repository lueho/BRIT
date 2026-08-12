"""Composite atlas themes offer every collection behind the displayed value.

Themes such as ``waste_ratio`` combine a biowaste and a residual collection into
one number, so there is no single collection a click could open. Those maps used
to be unclickable; they now hand the reader both collections to choose from.
"""

from datetime import date
from pathlib import Path

from django.contrib.auth.models import Group, User
from django.test import RequestFactory, SimpleTestCase, TestCase
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
    COMPOSITE_COLLECTION_DETAIL_CATEGORIES_BY_THEME,
    collection_detail_categories_for_theme,
)

WASTE_ATLAS_DIR = Path(__file__).resolve().parents[1] / "waste_atlas"
CHOROPLETH_SCRIPT = WASTE_ATLAS_DIR / "static" / "js" / "waste_atlas_choropleth.js"
ATLAS_STYLESHEET = WASTE_ATLAS_DIR / "static" / "css" / "waste_atlas.css"

CATCHMENT_GEOJSON_URL = "/waste_collection/api/waste-atlas/catchment/geojson/"


class CompositeCollectionDetailCategoryTests(SimpleTestCase):
    """Resolving a theme to the collection categories a click may open."""

    BIO_RESIDUAL_THEMES = (
        "collection_count_ratio",
        "combined_collection_count",
        "combined_fee_system",
        "combined_frequency",
        "waste_ratio",
    )
    COMPOSITE_THEMES = BIO_RESIDUAL_THEMES + ("organic_collection_amount",)

    def test_composite_themes_resolve_to_both_streams(self):
        for theme in self.BIO_RESIDUAL_THEMES:
            with self.subTest(theme=theme):
                self.assertEqual(
                    collection_detail_categories_for_theme(theme),
                    ("biowaste", "residual"),
                )

    def test_every_composite_theme_is_registered(self):
        self.assertEqual(
            sorted(COMPOSITE_COLLECTION_DETAIL_CATEGORIES_BY_THEME),
            sorted(self.COMPOSITE_THEMES),
        )

    def test_single_stream_themes_keep_their_one_category(self):
        self.assertEqual(
            collection_detail_categories_for_theme("collection_system"),
            ("biowaste",),
        )
        self.assertEqual(
            collection_detail_categories_for_theme("residual_frequency"),
            ("residual",),
        )
        self.assertEqual(
            collection_detail_categories_for_theme("collection_point_count"),
            ("all",),
        )

    def test_themes_without_any_collection_resolve_to_nothing(self):
        # Region-property themes have no collection to open at all.
        self.assertEqual(collection_detail_categories_for_theme("orga_level"), ())
        self.assertEqual(collection_detail_categories_for_theme("unknown_theme"), ())
        self.assertEqual(collection_detail_categories_for_theme(None), ())


class CompositeCatchmentGeoJSONTests(APITestCase):
    """The catchment GeoJSON exposes one option per contributing stream."""

    @classmethod
    def setUpTestData(cls):
        borders = GeoPolygon.objects.create(
            geom="MULTIPOLYGON(((0 0, 0 1, 1 1, 1 0, 0 0)))",
        )
        cls.region = Region.objects.create(
            name="Composite Region", country="DE", borders=borders
        )
        cls.catchment = CollectionCatchment.objects.create(
            name="Composite Catchment", region=cls.region
        )
        cls.user = User.objects.create_user(username="composite-atlas-user")

        cls.d2d = CollectionSystem.objects.create(name="Door to door")
        cls.bring_point = CollectionSystem.objects.create(name="Bring point")
        cls.biowaste = WasteCategory.objects.create(name="Biowaste")
        cls.residual = WasteCategory.objects.create(name="Residual waste")

        cls.biowaste_collection = Collection.objects.create(
            name="Composite Biowaste Collection",
            owner=cls.user,
            catchment=cls.catchment,
            waste_category=cls.biowaste,
            collection_system=cls.d2d,
            valid_from=date(2024, 1, 1),
            publication_status="published",
        )
        cls.residual_collection = Collection.objects.create(
            name="Composite Residual Collection",
            owner=cls.user,
            catchment=cls.catchment,
            waste_category=cls.residual,
            collection_system=cls.bring_point,
            valid_from=date(2024, 1, 1),
            publication_status="published",
        )

    def _feature(self, **params):
        response = self.client.get(
            CATCHMENT_GEOJSON_URL,
            {"country": "DE", "year": 2024, **params},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return next(
            feature
            for feature in response.data["features"]
            if feature["properties"]["catchment_id"] == self.catchment.id
        )

    def test_composite_request_offers_one_option_per_stream(self):
        properties = self._feature(collection_detail_category="biowaste,residual")[
            "properties"
        ]

        self.assertEqual(
            [option["url"] for option in properties["collection_details"]],
            [
                reverse(
                    "collection-detail", kwargs={"pk": self.biowaste_collection.id}
                ),
                reverse(
                    "collection-detail", kwargs={"pk": self.residual_collection.id}
                ),
            ],
        )

    def test_options_are_labelled_by_waste_category_and_system(self):
        properties = self._feature(collection_detail_category="biowaste,residual")[
            "properties"
        ]

        self.assertEqual(
            [option["label"] for option in properties["collection_details"]],
            ["Biowaste — Door to door", "Residual waste — Bring point"],
        )

    def test_single_category_request_offers_only_that_stream(self):
        properties = self._feature(collection_detail_category="biowaste")["properties"]

        self.assertEqual(len(properties["collection_details"]), 1)
        self.assertEqual(
            properties["collection_details"][0]["url"],
            reverse("collection-detail", kwargs={"pk": self.biowaste_collection.id}),
        )

    def test_detail_url_stays_available_for_single_option_maps(self):
        """The existing one-click behaviour must not regress."""
        properties = self._feature(collection_detail_category="biowaste")["properties"]

        self.assertEqual(
            properties["collection_detail_url"],
            reverse("collection-detail", kwargs={"pk": self.biowaste_collection.id}),
        )

    def test_no_category_yields_no_options(self):
        properties = self._feature()["properties"]

        self.assertEqual(properties["collection_details"], [])
        self.assertIsNone(properties["collection_detail_url"])

    def test_unknown_categories_are_ignored(self):
        properties = self._feature(collection_detail_category="biowaste,bogus")[
            "properties"
        ]

        self.assertEqual(len(properties["collection_details"]), 1)


class CompositeMapPageTests(TestCase):
    """A composite map page must ask the API for both streams."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="composite-page-user", password="secret"
        )
        group, _ = Group.objects.get_or_create(name="waste_atlas")
        cls.user.groups.add(group)

    def _render(self, theme, config_key):
        from sources.waste_collection.waste_atlas.views import AtlasMapView

        request = RequestFactory().get("/")
        request.user = self.user
        page = {
            "region": "generic",
            "theme": theme,
            "title": "Composite test map",
            "path": "map/test/",
            "name": "waste-atlas-test-map",
            "config_key": config_key,
            "selector_set": None,
            "country": "DE",
            "year": "2024",
            "lock": False,
        }
        return AtlasMapView.as_view(page=page)(request).render().content.decode("utf-8")

    def test_waste_ratio_page_requests_both_streams(self):
        content = self._render("waste_ratio", "waste_ratio")

        self.assertIn('"collectionDetailCategory": "biowaste,residual"', content)

    def test_single_stream_page_is_unchanged(self):
        content = self._render("collection_system", "collection_system")

        self.assertIn('"collectionDetailCategory": "biowaste"', content)

    def test_region_property_page_asks_for_no_collection(self):
        content = self._render("orga_level", "orga_level")

        self.assertNotIn("collectionDetailCategory", content)


class CollectionPickerRendererTests(SimpleTestCase):
    """The renderer offers a choice instead of guessing one collection."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.script = CHOROPLETH_SCRIPT.read_text()
        cls.stylesheet = ATLAS_STYLESHEET.read_text()

    def test_options_come_from_the_serialized_list(self):
        self.assertIn("function _collectionOptions(", self.script)
        self.assertIn("properties.collection_details", self.script)

    def test_a_single_option_still_navigates_directly(self):
        """No picker for the common case: one collection, one click."""
        self.assertIn("function _collectionDetailUrl(", self.script)
        self.assertIn("window.location.assign(detailUrl)", self.script)

    def test_several_options_open_a_picker(self):
        self.assertIn("function _openCollectionPicker(", self.script)
        self.assertIn("function _closeCollectionPicker(", self.script)
        self.assertIn("atlas-collection-picker", self.script)

    def test_picker_is_dismissable(self):
        self.assertIn("Escape", self.script)
        picker = self.script.split("function _openCollectionPicker(")[1]
        picker = picker.split("function _observeContainerResize(")[0]
        self.assertIn("addEventListener", picker)

    def test_picker_closes_when_the_map_moves_underneath_it(self):
        render_body = self.script.split("function _render(data, cfg, options)")[1]
        render_body = render_body.split("function _drawExportLegendItem")[0]
        self.assertIn("_closeCollectionPicker()", render_body)

        zoom_body = self.script.split("function _applyZoomTransform(")[1]
        zoom_body = zoom_body.split("function _zoomBy(")[0]
        self.assertIn("_closeCollectionPicker()", zoom_body)

    def test_stylesheet_styles_the_picker(self):
        self.assertIn(".atlas-collection-picker", self.stylesheet)
        self.assertIn(".atlas-collection-picker-link", self.stylesheet)
