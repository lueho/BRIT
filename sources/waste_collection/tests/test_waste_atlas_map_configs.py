"""Structural invariants of the stored Waste Atlas map configurations.

Configuration *content* (titles, legend labels, category colors) is seeded by
migration and edited at runtime by maintainers through the configuration UI, so
it is deliberately not asserted here.  These tests only cover the structure the
renderer and the selector rely on.
"""

from django.test import TestCase
from django.urls import Resolver404, resolve

from sources.waste_collection.waste_atlas.map_configs import (
    BIOWASTE_NO_COLLECTION_COLOR,
    MAP_CONFIGS,
    NO_DATA_COLOR,
)
from sources.waste_collection.waste_atlas.map_selection import (
    build_map_selection_context,
)
from sources.waste_collection.waste_atlas.pages import MAP_SET_COUNTRIES

# Keys the choropleth renderer reads for every map.
REQUIRED_CONFIG_KEYS = frozenset(
    {
        "title",
        "dataUrl",
        "dataField",
        "categories",
        "noDataColor",
        "legendTitle",
        "fileBase",
    }
)

# Configuration keys holding an API endpoint the client fetches.
URL_CONFIG_KEYS = (
    "dataUrl",
    "catchmentDataUrl",
    "conflictUrl",
    "outlineGeoJsonUrl",
)


class WasteAtlasMapConfigStructureTests(TestCase):
    def test_configurations_are_seeded(self):
        self.assertTrue(len(MAP_CONFIGS))

    def test_every_configuration_defines_the_keys_the_renderer_needs(self):
        for config_key, config in MAP_CONFIGS.items():
            with self.subTest(config_key=config_key):
                self.assertLessEqual(REQUIRED_CONFIG_KEYS, set(config))
                self.assertIsInstance(config["categories"], list)

    def test_every_category_defines_a_value_label_and_color(self):
        for config_key, config in MAP_CONFIGS.items():
            for entry in config["categories"]:
                with self.subTest(config_key=config_key, entry=entry.get("label")):
                    self.assertLessEqual({"label", "color"}, set(entry))
                    self.assertTrue("value" in entry or "classValue" in entry)

    def test_every_quartile_special_case_defines_the_field_it_classifies(self):
        """Quartile special cases key off a feature field, not a category value."""
        for config_key, config in MAP_CONFIGS.items():
            for entry in config.get("quartileSpecialCases", []):
                with self.subTest(config_key=config_key, entry=entry.get("label")):
                    self.assertLessEqual(
                        {"field", "classValue", "label", "color"},
                        set(entry),
                    )

    def test_configured_api_urls_resolve_to_a_served_route(self):
        """A typo in a stored endpoint must fail here, not silently in the browser."""
        for config_key, config in MAP_CONFIGS.items():
            for url_key in URL_CONFIG_KEYS:
                url = config.get(url_key)
                if not url:
                    continue
                with self.subTest(config_key=config_key, url_key=url_key, url=url):
                    try:
                        resolve(url)
                    except Resolver404:
                        self.fail(f"{config_key}.{url_key} does not resolve: {url}")

    def test_no_data_entries_share_the_shared_no_data_color(self):
        for config_key, config in MAP_CONFIGS.items():
            with self.subTest(config_key=config_key, entry="fallback"):
                self.assertEqual(config["noDataColor"], NO_DATA_COLOR)

            for entry in self._all_entries(config):
                if not self._is_no_data_entry(entry):
                    continue
                with self.subTest(config_key=config_key, entry=entry.get("label")):
                    self.assertEqual(entry["color"], NO_DATA_COLOR)

    def test_biowaste_no_collection_entries_share_the_shared_color(self):
        for config_key, config in MAP_CONFIGS.items():
            for entry in self._all_entries(config):
                if not self._is_biowaste_no_collection_entry(entry):
                    continue
                with self.subTest(config_key=config_key, entry=entry.get("label")):
                    self.assertEqual(entry["color"], BIOWASTE_NO_COLLECTION_COLOR)

    @staticmethod
    def _all_entries(config):
        return [
            *config.get("categories", []),
            *config.get("quartileSpecialCases", []),
        ]

    @staticmethod
    def _is_no_data_entry(entry):
        return (
            entry.get("value") == "no_data"
            or "no data" in entry.get("label", "").lower()
        )

    @staticmethod
    def _is_biowaste_no_collection_entry(entry):
        label = entry.get("label", "").lower()
        value = entry.get("value") or entry.get("classValue")
        return (
            "no separate biowaste collection" in label
            or "no separate door-to-door collection" in label
            or value in {"no_bio", "no_door_to_door", "no_bio_collection"}
        )


class WasteAtlasMapSelectionTests(TestCase):
    @staticmethod
    def _context(**kwargs):
        return build_map_selection_context(
            lambda route_name, args=None: f"/{route_name}/{'/'.join(args or [])}",
            **kwargs,
        )

    def test_every_map_set_entry_carries_its_region_scope(self):
        context = self._context()

        self.assertTrue(context["map_selection_map_sets"])
        for entry in context["map_selection_map_sets"]:
            with self.subTest(map_set=entry["value"]):
                self.assertEqual(entry["country"], MAP_SET_COUNTRIES[entry["value"]])
                self.assertIn("nuts_prefix", entry)
                self.assertIn("nuts_level", entry)

    def test_theme_labels_are_unique_per_map_set_and_waste_category(self):
        """Ambiguous selector entries would be indistinguishable to the user."""
        context = self._context()

        for map_set, themes in context["map_selection_themes_by_map_set"].items():
            by_waste_category = {}
            for theme in themes:
                by_waste_category.setdefault(theme["waste_category"], []).append(
                    theme["label"]
                )

            for waste_category, labels in by_waste_category.items():
                with self.subTest(map_set=map_set, waste_category=waste_category):
                    self.assertEqual(sorted(labels), sorted(set(labels)))
