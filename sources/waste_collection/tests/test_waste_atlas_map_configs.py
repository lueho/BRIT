from pathlib import Path

from django.test import SimpleTestCase

from sources.waste_collection.waste_atlas.map_configs import (
    BIOWASTE_NO_COLLECTION_COLOR,
    MAP_CONFIGS,
    NO_DATA_COLOR,
)
from sources.waste_collection.waste_atlas.map_selection import (
    MAP_SELECTION_THEME_ORDER,
    MAP_SELECTION_WASTE_CATEGORY_OVERRIDES,
    THEME_LABELS,
    WASTE_ATLAS_MAP_SELECTIONS,
)
from sources.waste_collection.waste_atlas.pages import MAP_PAGES


class WasteAtlasMapConfigTests(SimpleTestCase):
    UNIT_LABEL_FORBIDDEN_TOKENS = {
        "kg/cap/a": ("kg/cap/a", " kg"),
        "%": ("%",),
        "L": (" L",),
        "L/unit": ("L/unit", " L"),
    }

    def test_no_data_entries_share_the_same_gray_color(self):
        for config_key, config in MAP_CONFIGS.items():
            with self.subTest(config_key=config_key, entry="fallback"):
                self.assertEqual(config["noDataColor"], NO_DATA_COLOR)

            for entry in [
                *config.get("categories", []),
                *config.get("quartileSpecialCases", []),
            ]:
                if not self._is_no_data_entry(entry):
                    continue

                with self.subTest(config_key=config_key, entry=entry.get("label")):
                    self.assertEqual(entry["color"], NO_DATA_COLOR)

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

    def test_biowaste_no_collection_entries_share_the_same_color(self):
        for config_key, config in MAP_CONFIGS.items():
            for entry in [
                *config.get("categories", []),
                *config.get("quartileSpecialCases", []),
            ]:
                if not self._is_biowaste_no_collection_entry(entry):
                    continue

                with self.subTest(config_key=config_key, entry=entry.get("label")):
                    self.assertEqual(entry["color"], BIOWASTE_NO_COLLECTION_COLOR)

    def test_legacy_europe_amount_legend_labels_do_not_repeat_units(self):
        template_path = (
            Path(__file__).resolve().parents[1]
            / "waste_atlas"
            / "templates"
            / "waste_atlas"
            / "karte41_europe_biowaste_collection_amount.html"
        )

        template = template_path.read_text()

        self.assertIn(".text('kg/cap/a');", template)
        self.assertNotIn("label: '151+ kg/cap/a'", template)
        self.assertNotIn("label: '101 – 150 kg/cap/a'", template)
        self.assertNotIn("label: '51 – 100 kg/cap/a'", template)
        self.assertNotIn("label: '0 – 50 kg/cap/a'", template)

    def test_selector_keeps_matching_theme_group_when_region_or_category_changes(self):
        script_path = (
            Path(__file__).resolve().parents[1]
            / "waste_atlas"
            / "static"
            / "js"
            / "waste_atlas_choropleth.js"
        )

        script = script_path.read_text()

        self.assertIn("function selectedThemeGroup()", script)
        self.assertIn("function findThemeOption(", script)
        self.assertIn("selectedThemeGroup", script)
        self.assertIn("data-theme-group", script)

    def test_participation_policy_map_config_displays_connection_type(self):
        config = MAP_CONFIGS["connection_type"]

        self.assertEqual(config["title"], "Participation Policy")
        self.assertEqual(
            config["dataUrl"], "/waste_collection/api/waste-atlas/connection-type/"
        )
        self.assertEqual(config["dataField"], "connection_type")
        self.assertEqual(config["legendTitle"], "Participation Policy")
        self.assertEqual(config["fileBase"], "connection_type")
        self.assertEqual(
            [entry["value"] for entry in config["categories"]],
            [
                "MANDATORY",
                "MANDATORY_WITH_HOME_COMPOSTER_EXCEPTION",
                "VOLUNTARY",
                "not_specified",
            ],
        )

    def test_participation_policy_map_pages_match_connection_rate_scopes(self):
        connection_rate_pages = {
            page["region"]: page
            for page in MAP_PAGES
            if page["theme"] == "connection_rate"
        }
        connection_type_pages = {
            page["region"]: page
            for page in MAP_PAGES
            if page["theme"] == "connection_type"
        }

        self.assertEqual(connection_type_pages.keys(), connection_rate_pages.keys())
        self.assertEqual(
            connection_type_pages["nrw"]["path"], "map/nrw/participation-policy/"
        )
        self.assertEqual(
            connection_type_pages["nrw"]["name"],
            "waste-atlas-nrw-participation-policy-map",
        )
        for page in connection_type_pages.values():
            with self.subTest(region=page["region"]):
                self.assertEqual(page["title"], "Participation Policy")
                self.assertEqual(page["config_key"], "connection_type")

    def test_participation_policy_map_is_available_as_biowaste_theme(self):
        self.assertEqual(THEME_LABELS["connection_type"], "Participation Policy")
        self.assertEqual(
            MAP_SELECTION_WASTE_CATEGORY_OVERRIDES["connection_type"], "biowaste"
        )
        self.assertLess(
            MAP_SELECTION_THEME_ORDER["connection_rate"],
            MAP_SELECTION_THEME_ORDER["connection_type"],
        )

        for map_set in ("DE", "DE-NW", "DE-BW-RP", "ES-CT"):
            with self.subTest(map_set=map_set):
                self.assertIn(
                    "connection_type", WASTE_ATLAS_MAP_SELECTIONS[map_set]["themes"]
                )

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
