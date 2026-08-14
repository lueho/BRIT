"""Structural invariants of the stored Waste Atlas map configurations.

Configuration *content* (titles, legend labels, category colors) is seeded by
migration and edited at runtime by maintainers through the configuration UI, so
it is deliberately not asserted here.  These tests only cover the structure the
renderer and the selector rely on.
"""

from django.template import Context
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
from sources.waste_collection.waste_atlas.models import (
    WasteAtlasMapConfiguration,
    WasteAtlasRenderingSettings,
)
from sources.waste_collection.waste_atlas.pages import MAP_PAGES, MAP_SET_COUNTRIES
from sources.waste_collection.waste_atlas.templatetags.atlas_tags import (
    atlas_js_config,
)

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
    DOOR_TO_DOOR_BIOWASTE_THEMES = {
        "biowaste_collection_count",
        "biowaste_fee_system",
        "biowaste_frequency",
        "biowaste_min_bin_size",
        "biowaste_required_bin_capacity",
        "collection_count_ratio",
        "combined_collection_count",
        "combined_fee_system",
        "combined_frequency",
        "connection_rate",
        "min_bin_size_ratio",
        "rp_biowaste_collection_count",
        "rp_collection_count_ratio",
    }
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
                    self.assertIn("label", entry)
                    # A fill is either literal or a reference to a shared colour.
                    self.assertTrue("color" in entry or "colorRef" in entry)
                    self.assertTrue("value" in entry or "classValue" in entry)

    def test_door_to_door_biowaste_maps_use_the_specific_absence_label(self):
        expected = "No separate door-to-door biowaste collection"
        for config_key in self.DOOR_TO_DOOR_BIOWASTE_THEMES:
            config = MAP_CONFIGS[config_key]
            matching = [
                entry
                for entry in config["categories"]
                if (entry.get("value") or entry.get("classValue"))
                in {"no_bio", "no_d2d", "no_door_to_door", "no_bio_collection"}
            ]
            with self.subTest(config_key=config_key):
                self.assertEqual(len(matching), 1)
                self.assertEqual(matching[0]["label"], expected)

    def test_biowaste_fee_map_classifies_non_door_to_door_systems(self):
        config = MAP_CONFIGS["biowaste_fee_system"]

        self.assertEqual(config["transformName"], "biowasteFeeSystem")
        self.assertEqual(config["dataField"], "_classified")
        self.assertIn(
            "no_door_to_door",
            [entry["value"] for entry in config["categories"]],
        )

    def test_every_quartile_special_case_defines_the_field_it_classifies(self):
        """Quartile special cases key off a feature field, not a category value."""
        for config_key, config in MAP_CONFIGS.items():
            for entry in config.get("quartileSpecialCases", []):
                with self.subTest(config_key=config_key, entry=entry.get("label")):
                    self.assertLessEqual(
                        {"field", "classValue", "label", "color"},
                        set(entry),
                    )

    def test_connection_rate_uses_fixed_percentage_bands(self):
        config = MAP_CONFIGS["connection_rate"]

        self.assertTrue(config["enableQuartiles"])
        self.assertFalse(config["quartileDefaultEnabled"])
        self.assertEqual(
            [category["value"] for category in config["categories"][:5]],
            ["full_connection", "75-99", "50-74", "25-49", "0-24"],
        )
        self.assertNotIn(
            "full_connection",
            [
                special_case["classValue"]
                for special_case in config.get("quartileSpecialCases", [])
            ],
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
                    if "colorRef" in entry:
                        self.assertEqual(entry["colorRef"], "no_collection")
                        continue
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

    def test_rp_collection_maps_use_their_own_stored_configurations(self):
        """The RLP legends are staff-editable data, not page-level Python.

        Their classes differ from the shared themes, so each of those pages
        points at its own stored configuration instead of overriding the shared
        one in ``pages.py``.
        """
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

        for theme, page in pages.items():
            with self.subTest(theme=theme):
                self.assertEqual(page["config_key"], f"rp_{theme}")
                overrides = page.get("overrides") or {}
                self.assertNotIn("categories", overrides)
                self.assertNotIn("legendTitle", overrides)
                self.assertNotIn("transformName", overrides)

        frequency = MAP_CONFIGS["rp_combined_frequency"]
        self.assertEqual(
            frequency["legendTitle"],
            "Collection frequency structure: Biowaste / Residual waste",
        )
        self.assertEqual(frequency["legendColumns"], 2)
        self.assertEqual(frequency["exportLegendColumns"], 2)
        self.assertEqual(frequency["exportLegendItemFlow"], "row")
        self.assertTrue(frequency["showOnlyPresentCategories"])
        self.assertEqual(frequency["transformName"], "combinedFrequency")

        ratio = MAP_CONFIGS["rp_collection_count_ratio"]
        self.assertEqual(
            ratio["legendTitle"],
            "Annual collection count ratio - Biowaste : Residual waste",
        )
        self.assertEqual(ratio["transformName"], "rpCollectionCountRatio")
        self.assertEqual(
            [entry["label"] for entry in ratio["categories"]],
            [
                "2:1",
                "< 2:1 > 1:1",
                "1:1",
                "< 1:1",
                "No separate door-to-door biowaste collection",
            ],
        )

        for theme, transform in (
            ("biowaste_collection_count", "rpBiowasteCollectionCount"),
            ("residual_collection_count", "rpResidualCollectionCount"),
        ):
            with self.subTest(theme=theme):
                config = MAP_CONFIGS[f"rp_{theme}"]
                self.assertEqual(config["transformName"], transform)
                self.assertFalse(config["enableQuartiles"])
                self.assertTrue(config["showOnlyPresentCategories"])
                self.assertEqual(
                    [
                        entry["label"]
                        for entry in config["categories"]
                        if entry["value"] != "no_door_to_door"
                    ],
                    [
                        "< 13",
                        "13",
                        "14 - 25",
                        "26",
                        "27 - 39",
                        "40 - 51",
                        "52",
                        "> 52",
                    ],
                )

        self.assertEqual(
            MAP_CONFIGS["rp_biowaste_collection_count"]["categories"][-1]["label"],
            "No separate door-to-door biowaste collection",
        )
        self.assertNotIn(
            "no_door_to_door",
            {
                entry["value"]
                for entry in MAP_CONFIGS["rp_residual_collection_count"]["categories"]
            },
        )

    def test_rp_count_maps_keep_the_numeric_field_of_their_shared_theme(self):
        """The year-comparison map needs it to report by how much a count moved."""
        for theme in ("biowaste_collection_count", "residual_collection_count"):
            with self.subTest(theme=theme):
                self.assertEqual(
                    MAP_CONFIGS[f"rp_{theme}"]["numericField"],
                    MAP_CONFIGS[theme]["numericField"],
                )

    def test_rp_ratio_map_renders_the_stored_legend_title_and_labels(self):
        """Editing the stored configuration must reach the rendered map.

        Regression: the page overrode ``legendTitle`` and ``categories`` in
        Python, so the legend ignored what maintainers configured.
        """
        page = next(
            entry
            for entry in MAP_PAGES
            if entry["region"] == "rp" and entry["theme"] == "collection_count_ratio"
        )
        stored = WasteAtlasMapConfiguration.objects.get(key=page["config_key"])
        stored.configuration = {
            **stored.configuration,
            "legendTitle": "Edited legend title",
            "categories": [
                {"value": "two_to_one", "label": "Edited label", "color": "#111111"}
            ],
        }
        stored.save(update_fields=["configuration"])

        config = atlas_js_config(self._page_context(page), page["config_key"])

        self.assertEqual(config["legendTitle"], "Edited legend title")
        self.assertEqual(
            [entry["label"] for entry in config["categories"]], ["Edited label"]
        )

    def test_legends_take_the_no_collection_color_from_the_setting(self):
        """A ``colorRef`` entry must follow the admin-editable shared fill."""
        settings = WasteAtlasRenderingSettings.load()
        settings.no_collection_color = "#123456"
        settings.save()

        checked = 0
        for page in MAP_PAGES:
            config = atlas_js_config(self._page_context(page), page["config_key"])
            for entry in self._all_entries(config):
                if not self._is_biowaste_no_collection_entry(entry):
                    continue
                if entry["color"] != "#123456":
                    continue
                checked += 1
                with self.subTest(page=page["name"], entry=entry["label"]):
                    self.assertNotIn("colorRef", entry)

        self.assertTrue(checked)

    @staticmethod
    def _page_context(page):
        return Context(
            {
                "map_config_overrides": page.get("overrides") or {},
                "atlas_page_selector_set": page.get("selector_set"),
                "atlas_active_theme": page["theme"],
            }
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
