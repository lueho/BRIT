"""Structural invariants of the stored Waste Atlas map configurations.

Configuration *content* (titles, legend labels, category colors) is seeded by
migration and edited at runtime by maintainers through the configuration UI, so
it is deliberately not asserted here.  These tests only cover the structure the
renderer and the selector rely on.
"""

from django.test import TestCase
from django.urls import Resolver404, resolve

from sources.waste_collection.waste_atlas.map_configs import (
    MAP_CONFIGS,
    no_collection_color,
    no_data_color,
)
from sources.waste_collection.waste_atlas.map_selection import (
    MAP_SELECTION_THEME_ORDER,
    MAP_SELECTION_WASTE_CATEGORY_OVERRIDES,
    THEME_LABELS,
    WASTE_ATLAS_MAP_SELECTIONS,
    build_map_selection_context,
)
from sources.waste_collection.waste_atlas.pages import MAP_PAGES, MAP_SET_COUNTRIES

# Keys the choropleth renderer reads for every map.
REQUIRED_CONFIG_KEYS = frozenset(
    {
        "title",
        "dataUrl",
        "dataField",
        "categories",
        "legendTitle",
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
    UNIT_LABEL_FORBIDDEN_TOKENS = {
        "kg/cap/a": ("kg/cap/a", " kg"),
        "%": ("%",),
        "L": (" L",),
        "L/unit": ("L/unit", " L"),
    }

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

    def test_amount_maps_mark_aggregated_values(self):
        for config_key in (
            "biowaste_collection_amount",
            "residual_collection_amount",
        ):
            with self.subTest(config_key=config_key):
                config = MAP_CONFIGS[config_key]
                self.assertEqual(config["overlayPatternField"], "_has_acpv_overlay")
                self.assertIn("acpv-outline-geojson/", config["outlineGeoJsonUrl"])
                self.assertEqual(
                    config["overlayPatternLegendLabel"],
                    "Hatched = aggregated value",
                )

    def test_waste_ratio_marks_values_that_include_aggregated_amounts(self):
        config = MAP_CONFIGS["waste_ratio"]

        self.assertEqual(config["overlayPatternField"], "uses_aggregated_amount")
        self.assertEqual(
            config["overlayPatternLegendLabel"],
            "Hatched = includes aggregated value",
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
                self.assertEqual(
                    config.get("noDataColor", no_data_color()), no_data_color()
                )

            for entry in self._all_entries(config):
                if not self._is_no_data_entry(entry):
                    continue
                with self.subTest(config_key=config_key, entry=entry.get("label")):
                    self.assertEqual(entry["color"], no_data_color())

    def test_biowaste_no_collection_entries_share_the_shared_color(self):
        for config_key, config in MAP_CONFIGS.items():
            for entry in self._all_entries(config):
                if not self._is_biowaste_no_collection_entry(entry):
                    continue
                with self.subTest(config_key=config_key, entry=entry.get("label")):
                    self.assertEqual(entry["color"], no_collection_color())

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

    def test_category_labels_do_not_repeat_units_from_legend_title(self):
        for config_key, config in MAP_CONFIGS.items():
            forbidden_tokens = self._forbidden_unit_tokens(
                config.get("legendTitle", "")
            )
            if not forbidden_tokens:
                continue

            for entry in [
                *config.get("categories", []),
                *config.get("quartileSpecialCases", []),
            ]:
                label = entry.get("label", "")
                for token in forbidden_tokens:
                    with self.subTest(
                        config_key=config_key,
                        label=label,
                        token=token,
                    ):
                        self.assertNotIn(token, label)

    def test_map_selection_context_includes_region_scope_per_map_set(self):
        """Each map-set entry must carry its full region scope."""
        from sources.waste_collection.waste_atlas.pages import MAP_SET_COUNTRIES

        context = build_map_selection_context(
            lambda route_name, args=None: f"/{route_name}/{'/'.join(args or [])}"
        )

        for entry in context["map_selection_map_sets"]:
            with self.subTest(map_set=entry["value"]):
                self.assertIn("country", entry)
                self.assertEqual(entry["country"], MAP_SET_COUNTRIES[entry["value"]])
                self.assertIn("nuts_prefix", entry)
                self.assertIn("nuts_level", entry)

        map_sets_by_value = {
            entry["value"]: entry for entry in context["map_selection_map_sets"]
        }
        self.assertEqual(map_sets_by_value["DE-NW"]["country"], "DE")
        self.assertEqual(map_sets_by_value["DE-NW"]["nuts_prefix"], "DEA")
        self.assertEqual(map_sets_by_value["DE-NW"]["nuts_level"], "1")
        self.assertEqual(map_sets_by_value["SE"]["country"], "SE")
        self.assertEqual(map_sets_by_value["SE"]["nuts_prefix"], "")
        self.assertEqual(map_sets_by_value["SE"]["nuts_level"], "")

    def test_participation_policy_map_pages_match_connection_rate_scopes(self):
        connection_rate_pages = {
            page["region"]: page
            for page in MAP_PAGES
            if page["theme"] == "connection_rate"
        }
        participation_policy_pages = {
            page["region"]: page
            for page in MAP_PAGES
            if page["theme"] == "participation_policy"
        }

        self.assertEqual(
            set(participation_policy_pages),
            set(connection_rate_pages) - {"sweden"},
        )
        self.assertEqual(
            participation_policy_pages["nrw"]["path"], "map/nrw/participation-policy/"
        )
        self.assertEqual(
            participation_policy_pages["nrw"]["name"],
            "waste-atlas-nrw-participation-policy-map",
        )
        for page in participation_policy_pages.values():
            with self.subTest(region=page["region"]):
                self.assertEqual(page["title"], "Participation Policy")
                self.assertEqual(page["config_key"], "participation_policy")

    def test_participation_policy_map_is_available_as_biowaste_theme(self):
        self.assertEqual(THEME_LABELS["participation_policy"], "Participation Policy")
        self.assertEqual(
            MAP_SELECTION_WASTE_CATEGORY_OVERRIDES["participation_policy"], "biowaste"
        )
        self.assertLess(
            MAP_SELECTION_THEME_ORDER["connection_rate"],
            MAP_SELECTION_THEME_ORDER["participation_policy"],
        )

        for map_set in ("DE", "DE-NW", "DE-BW-RP", "DE-BW", "DE-RP", "ES-CT"):
            with self.subTest(map_set=map_set):
                self.assertIn(
                    "participation_policy",
                    WASTE_ATLAS_MAP_SELECTIONS[map_set]["themes"],
                )

    def test_sweden_query_maps_are_dedicated_selector_pages(self):
        expected_themes = {
            "collection_system": "waste-atlas-sweden-collection-system-map",
            "connection_rate": "waste-atlas-sweden-connection-rate-map",
            "paper_bags": "waste-atlas-sweden-paper-bags-map",
            "plastic_bags": "waste-atlas-sweden-plastic-bags-map",
            "collection_support": "waste-atlas-sweden-collection-support-map",
            "residual_collection_amount": (
                "waste-atlas-sweden-residual-collection-amount-map"
            ),
            "biowaste_collection_amount": (
                "waste-atlas-sweden-biowaste-collection-amount-map"
            ),
            "waste_ratio": "waste-atlas-sweden-waste-ratio-map",
            "organic_collection_amount": (
                "waste-atlas-sweden-organic-collection-amount-map"
            ),
            "organic_waste_ratio": ("waste-atlas-sweden-organic-waste-ratio-map"),
        }
        sweden_themes = WASTE_ATLAS_MAP_SELECTIONS["SE"]["themes"]
        pages_by_route = {page["name"]: page for page in MAP_PAGES}

        for theme, route_name in expected_themes.items():
            with self.subTest(theme=theme):
                self.assertIn(theme, sweden_themes)
                self.assertEqual(sweden_themes[theme]["route_name"], route_name)
                self.assertEqual(pages_by_route[route_name]["year"], "2024")

    def test_rp_collection_maps_use_requested_region_specific_legends(self):
        pages = {
            page["theme"]: page
            for page in MAP_PAGES
            if page["region"] == "rp"
            and page["theme"]
            in {
                "combined_frequency",
                "biowaste_collection_count",
                "residual_collection_count",
                "collection_count_ratio",
            }
        }

        frequency = pages["combined_frequency"]["overrides"]
        self.assertEqual(
            frequency["legendTitle"],
            "Collection frequency structure: Biowaste / Residual waste",
        )
        self.assertEqual(frequency["legendColumns"], 2)
        self.assertEqual(frequency["exportLegendColumns"], 2)
        self.assertEqual(frequency["exportLegendItemFlow"], "row")
        self.assertTrue(frequency["showOnlyPresentCategories"])
        self.assertTrue(
            all(
                entry["label"] == entry["label"].upper()
                for entry in frequency["categories"]
            )
        )

        ratio = pages["collection_count_ratio"]["overrides"]
        self.assertEqual(
            ratio["legendTitle"],
            "Annual collection count ratio - Biowaste : Residual waste",
        )
        self.assertEqual(
            [entry["label"] for entry in ratio["categories"]],
            [
                "2:1",
                "< 2:1 > 1:1",
                "1:1",
                "No separate door-to-door biowaste collection",
            ],
        )

        for theme in ("biowaste_collection_count", "residual_collection_count"):
            with self.subTest(theme=theme):
                categories = pages[theme]["overrides"]["categories"]
                self.assertEqual(
                    [entry["label"] for entry in categories[:6]],
                    ["13", "14 - 25", "26", "27 - 39", "40 - 51", "52"],
                )

        self.assertEqual(
            pages["biowaste_collection_count"]["overrides"]["categories"][-1]["label"],
            "No separate door-to-door biowaste collection",
        )

    def test_collection_system_config_opts_into_conflict_aid(self):
        """The collection_system theme exposes the maintainer conflict aid."""
        config = MAP_CONFIGS["collection_system"]
        self.assertEqual(config["conflictTheme"], "collection_system")
        self.assertTrue(config["conflictUrl"].endswith("/collection-conflicts/"))
        self.assertTrue(config["conflictOverlayLabel"])

    def test_conflict_aid_url_matches_registered_router_endpoint(self):
        """The configured conflict URL must match a registered waste-atlas route."""
        from sources.waste_collection.waste_atlas.router import router

        registered = {
            f"/waste_collection/api/waste-atlas/{prefix}/"
            for prefix, _viewset, _basename in router.registry
        }
        for config in MAP_CONFIGS.values():
            url = config.get("conflictUrl")
            if not url:
                continue
            with self.subTest(url=url):
                self.assertIn(url, registered)

    def _forbidden_unit_tokens(self, legend_title):
        for unit, forbidden_tokens in self.UNIT_LABEL_FORBIDDEN_TOKENS.items():
            if f"({unit})" in legend_title:
                return forbidden_tokens
        return ()

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
