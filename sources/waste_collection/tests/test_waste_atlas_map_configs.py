from pathlib import Path

from django.test import TestCase

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
    build_map_selection_context,
)
from sources.waste_collection.waste_atlas.pages import MAP_PAGES


class WasteAtlasMapConfigTests(TestCase):
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

    def test_waste_ratio_legend_labels_define_only_the_outer_ranges(self):
        categories = MAP_CONFIGS["waste_ratio"]["categories"]

        self.assertEqual(
            [category["label"] for category in categories[:4]],
            [
                "> 66 (Biowaste-stream dominant)",
                "51–66",
                "34–50",
                "≤ 33 (Residual-waste-stream dominant)",
            ],
        )

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
        self.assertIn("&country=", script)
        self.assertIn("countrySelect.value", script)
        self.assertIn("&nuts_prefix=", script)
        self.assertIn("&nuts_level=", script)

    def test_selector_navigation_passes_iso_country_code_not_map_set_id(self):
        """The ``country`` query param must be an ISO code, not a map-set ID.

        Regression: navigating from a sub-region page (e.g. DE-NW) to a
        generic fallback theme passed "DE-NW" as ``&country=`` which the
        API cannot resolve.
        """
        script_path = (
            Path(__file__).resolve().parents[1]
            / "waste_atlas"
            / "static"
            / "js"
            / "waste_atlas_choropleth.js"
        )
        script = script_path.read_text()

        self.assertIn("selectedCountryCode", script)
        self.assertIn("data-country", script)

    def test_selector_load_config_clears_missing_nuts_level(self):
        script_path = (
            Path(__file__).resolve().parents[1]
            / "waste_atlas"
            / "static"
            / "js"
            / "waste_atlas_choropleth.js"
        )
        script = script_path.read_text()

        self.assertIn("else delete loadCfg.nutsLevel;", script)

    def test_load_current_uses_passed_country_instead_of_cfg_country(self):
        """The ``loadCurrent`` callback in ``init()`` must use the country
        argument from the selector, not the hard-coded ``cfg.country``.
        """
        script_path = (
            Path(__file__).resolve().parents[1]
            / "waste_atlas"
            / "static"
            / "js"
            / "waste_atlas_choropleth.js"
        )
        script = script_path.read_text()

        init_section = script.split("function init(cfg)")[1]
        init_selector_call = init_section[
            init_section.index("initSelectorControls(") : init_section.index(
                "initSelectorControls("
            )
            + 200
        ]
        self.assertNotIn("cfg.country", init_selector_call)
        self.assertIn("country", init_selector_call)

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

    def test_change_maps_use_numeric_difference_for_numeric_configs(self):
        script_path = (
            Path(__file__).resolve().parents[1]
            / "waste_atlas"
            / "static"
            / "js"
            / "waste_atlas_choropleth.js"
        )

        script = script_path.read_text()

        self.assertIn("function _numericChangeRecords(", script)
        self.assertIn("cfg.numericField", script)
        self.assertIn("change = difference > 0 ? 'increase' : 'decrease'", script)
        self.assertIn("legendTitle: isNumericChange ? 'Difference' : 'Change'", script)

    def test_quartile_legend_labels_show_whole_numbers_only(self):
        """Quartile legend labels must display rounded integers, not decimals.

        e.g. ``41`` instead of ``41.0`` or ``5`` instead of ``5.00``.
        """
        script_path = (
            Path(__file__).resolve().parents[1]
            / "waste_atlas"
            / "static"
            / "js"
            / "waste_atlas_choropleth.js"
        )
        script = script_path.read_text()

        # The fmt() function inside _computeQuartileCategories must not use
        # toFixed — only Math.round for whole-number display.
        quartile_fn = script.split("function _computeQuartileCategories(")[1]
        fmt_section = quartile_fn[: quartile_fn.index("return [")]
        self.assertIn("Math.round(v * displayMultiplier).toString()", fmt_section)
        self.assertNotIn("toFixed", fmt_section)

    def test_separation_rate_quartile_labels_use_percentage_values(self):
        for config_key in (
            "connection_rate",
            "organic_waste_ratio",
            "waste_ratio",
        ):
            with self.subTest(config_key=config_key):
                self.assertEqual(
                    MAP_CONFIGS[config_key]["quartileDisplayMultiplier"], 100
                )

        self.assertIn(
            "baseCfg.quartileDisplayMultiplier",
            Path(
                Path(__file__).resolve().parents[1]
                / "waste_atlas"
                / "static"
                / "js"
                / "waste_atlas_choropleth.js"
            ).read_text(),
        )

    def test_quartile_mode_is_enabled_by_default(self):
        """The quartile toggle must be checked on page load for all KPI maps.

        Users prefer quartile classification over fixed class boundaries, so
        the checkbox starts checked and ``isQuartileMode`` initialises to true
        whenever the config supports quartiles.
        """
        script_path = (
            Path(__file__).resolve().parents[1]
            / "waste_atlas"
            / "static"
            / "js"
            / "waste_atlas_choropleth.js"
        )
        script = script_path.read_text()

        self.assertIn(
            "var isQuartileMode = _isQuartileEnabled(cfg) && !cfg.changeMode;",
            script,
        )
        self.assertIn("toggleCheckbox.checked = true;", script)

    def test_selector_labels_are_unique_per_map_set_and_waste_category(self):
        context = build_map_selection_context(
            lambda route_name, args=None: f"/{route_name}/{'/'.join(args or [])}"
        )

        for map_set, themes in context["map_selection_themes_by_map_set"].items():
            by_waste_category = {}
            for theme in themes:
                by_waste_category.setdefault(theme["waste_category"], []).append(
                    theme["label"]
                )

            for waste_category, labels in by_waste_category.items():
                with self.subTest(map_set=map_set, waste_category=waste_category):
                    self.assertEqual(len(labels), len(set(labels)))

    def test_selector_js_supports_search_status_and_empty_states(self):
        script_path = (
            Path(__file__).resolve().parents[1]
            / "waste_atlas"
            / "static"
            / "js"
            / "waste_atlas_choropleth.js"
        )
        script = script_path.read_text()

        self.assertIn("sel-theme-search", script)
        self.assertIn("atlas-selector-status", script)
        self.assertIn("optionMatchesSearch", script)
        self.assertIn("visibleThemeCount", script)
        self.assertIn("atlas-selector-empty", script)
        self.assertIn("form.addEventListener('submit', navigateOrLoad)", script)

    def test_participation_policy_map_config_displays_participation_policy(self):
        config = MAP_CONFIGS["participation_policy"]

        self.assertEqual(config["title"], "Participation Policy")
        self.assertEqual(
            config["dataUrl"], "/waste_collection/api/waste-atlas/participation-policy/"
        )
        self.assertEqual(config["dataField"], "participation_policy")
        self.assertEqual(config["legendTitle"], "Participation Policy")
        self.assertEqual(config["fileBase"], "participation_policy")
        self.assertEqual(
            [entry["value"] for entry in config["categories"]],
            [
                "no_bio_collection",
                "MANDATORY",
                "MANDATORY_WITH_HOME_COMPOSTER_EXCEPTION",
                "VOLUNTARY",
            ],
        )
        self.assertEqual(
            config["categories"][0],
            {
                "value": "no_bio_collection",
                "label": "No separate biowaste collection",
                "color": BIOWASTE_NO_COLLECTION_COLOR,
            },
        )

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

        for map_set in ("DE", "DE-NW", "DE-BW-RP", "ES-CT"):
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

    def test_nrw_exports_use_two_column_bottom_legends(self):
        nrw_pages = [page for page in MAP_PAGES if page["region"] == "nrw"]

        self.assertTrue(nrw_pages)
        for page in nrw_pages:
            with self.subTest(page=page["name"]):
                self.assertEqual(page["overrides"]["exportLegendBottomColumns"], 2)

    def test_sweden_exports_use_fitted_bottom_right_legends(self):
        expected_overrides = {
            "exportLegendPlacement": "bottom-right",
            "exportLegendWidth": 0.64,
            "exportLegendColumns": 1,
            "exportLegendFitContent": True,
            "exportLegendAvoidMapOverlap": True,
        }
        sweden_pages = [page for page in MAP_PAGES if page["region"] == "sweden"]

        self.assertTrue(sweden_pages)
        for page in sweden_pages:
            with self.subTest(page=page["name"]):
                for key, value in expected_overrides.items():
                    self.assertEqual(page["overrides"][key], value)

        waste_ratio_page = next(
            page for page in sweden_pages if page["theme"] == "waste_ratio"
        )
        self.assertEqual(
            waste_ratio_page["overrides"]["fileBase"], "sweden_waste_ratio"
        )
        residual_amount_page = next(
            page
            for page in sweden_pages
            if page["theme"] == "residual_collection_amount"
        )
        self.assertEqual(
            residual_amount_page["overrides"]["exportLegendTitle"],
            "Collected amount (kg / cap / a)",
        )

        script_path = (
            Path(__file__).resolve().parents[1]
            / "waste_atlas"
            / "static"
            / "js"
            / "waste_atlas_choropleth.js"
        )
        script = script_path.read_text()
        export_layout_fn = script.split("function _exportLayout(data, cfg)")[1].split(
            "// ---- quartile helpers"
        )[0]
        self.assertIn("cfg.exportLegendPlacement", export_layout_fn)
        self.assertIn("cfg.exportLegendWidth", export_layout_fn)
        self.assertIn("cfg.exportLegendColumns", export_layout_fn)
        self.assertIn("cfg.exportLegendFitContent", script)
        self.assertIn("cfg.exportLegendAvoidMapOverlap", export_layout_fn)
        self.assertIn("function _fitExportLegendWidth(", script)
        self.assertIn("function _projectedRightEdgeInBand(", script)
        self.assertIn("d3.geoStream(geometryData, projection.stream(stream))", script)
        self.assertIn("function _fitBottomRightLegend(", script)
        self.assertNotIn("cfg.exportLegendReserveMapSpace", export_layout_fn)

    def test_legend_reordering_helper_exists_in_js(self):
        script_path = (
            Path(__file__).resolve().parents[1]
            / "waste_atlas"
            / "static"
            / "js"
            / "waste_atlas_choropleth.js"
        )
        script = script_path.read_text()

        self.assertIn("function _isNoCollectionCategory(item)", script)
        self.assertIn("label.indexOf('No separate biowaste collection')", script)
        self.assertIn("label.indexOf('No separate door-to-door collection')", script)
        self.assertIn("label.indexOf('No separate collection')", script)
        self.assertIn("label.indexOf('No separate green waste collection')", script)
        self.assertIn("label.indexOf('No door-to-door')", script)

    def test_legend_items_reorders_no_collection_before_no_data(self):
        script_path = (
            Path(__file__).resolve().parents[1]
            / "waste_atlas"
            / "static"
            / "js"
            / "waste_atlas_choropleth.js"
        )
        script = script_path.read_text()

        # _legendItems must call _isNoCollectionCategory
        self.assertIn("_isNoCollectionCategory(item)", script)
        # Overlay pattern is NOT a legend item — it is rendered as a footnote.
        legend_items_fn = script.split("function _legendItems(cfg, exportMode)")[1]
        no_data_idx = legend_items_fn.find("cfg.noDataLabel")
        self.assertNotIn("cfg.overlayPatternField", legend_items_fn[: no_data_idx + 50])

    def test_no_data_legend_entries_only_render_for_displayed_regions(self):
        script_path = (
            Path(__file__).resolve().parents[1]
            / "waste_atlas"
            / "static"
            / "js"
            / "waste_atlas_choropleth.js"
        )
        script = script_path.read_text()
        annotate_fn = script.split("function _annotateFeatures(data, cfg)")[1].split(
            "function _overlayPatternId"
        )[0]
        legend_items_fn = script.split("function _legendItems(cfg, exportMode)")[
            1
        ].split("function _fitExportLegendWidth")[0]
        ordered_items_fn = script.split("function _orderedLegendCategories(cfg)")[
            1
        ].split("function _legendItems(cfg, exportMode)")[0]

        self.assertIn("function _isNoDataCategory(item)", script)
        self.assertIn("function _visibleLegendCategories(cfg)", script)
        self.assertIn("cfg._hasNoDataCategory = hasNoDataCategory", annotate_fn)
        self.assertIn("cfg._hasFallbackNoData = hasFallbackNoData", annotate_fn)
        self.assertIn("_orderedLegendCategories(cfg)", legend_items_fn)
        self.assertIn("_visibleLegendCategories(cfg)", ordered_items_fn)
        self.assertIn("cfg._hasFallbackNoData", legend_items_fn)

    def test_screen_legend_renders_no_data_last(self):
        script_path = (
            Path(__file__).resolve().parents[1]
            / "waste_atlas"
            / "static"
            / "js"
            / "waste_atlas_choropleth.js"
        )
        script = script_path.read_text()

        draw_legend_fn = script.split(
            "function _drawLegend(width, height, cfg, layout)"
        )[1]
        # Screen and export legends use the same explicit/legacy order.
        self.assertIn("_orderedLegendCategories(cfg)", draw_legend_fn)
        ordered_items_fn = script.split("function _orderedLegendCategories(cfg)")[
            1
        ].split("function _legendItems(cfg, exportMode)")[0]
        self.assertIn("_isNoCollectionCategory(item)", ordered_items_fn)
        # Overlay hint is a footnote (separator + italic text), not a swatch row
        self.assertIn("font-style', 'italic'", draw_legend_fn)
        self.assertIn("cfg.overlayPatternLegendLabel", draw_legend_fn)
        # Overlay footnote must come after No data so all real categories stay grouped
        no_data_render_idx = draw_legend_fn.find(
            "if (cfg.noDataLabel && cfg._hasFallbackNoData)"
        )
        overlay_render_idx = draw_legend_fn.rfind("if (hasOverlayLegend)")
        self.assertLess(no_data_render_idx, overlay_render_idx)

    def test_export_legend_renders_overlay_as_footnote(self):
        """The overlay pattern hint must be a footnote, not a legend category.

        In export mode the overlay is drawn as a separator line + italic text
        below the legend columns, not as a regular swatch item.
        """
        script_path = (
            Path(__file__).resolve().parents[1]
            / "waste_atlas"
            / "static"
            / "js"
            / "waste_atlas_choropleth.js"
        )
        script = script_path.read_text()

        # _measureExportLegend must compute a footnote separately
        measure_fn = script.split("function _measureExportLegend(")[1]
        measure_fn_body = measure_fn.split("function _rectIntersectionArea")[0]
        self.assertIn("opts.footnote", measure_fn)
        self.assertIn("opts.footnoteHeight", measure_fn)
        self.assertNotIn("exportMode", measure_fn_body)
        # _drawExportLegendItem must not draw pattern swatches for the overlay
        draw_item_fn = script.split("function _drawExportLegendItem(")[1]
        # The pattern block should be gone (overlay is no longer an item)
        self.assertNotIn("cat.pattern", draw_item_fn[:500])

    def test_export_legend_titles_support_explicit_line_breaks(self):
        """Explicit newlines in export legend titles must be preserved."""
        config = MAP_CONFIGS["waste_ratio"]
        self.assertEqual(
            config["exportLegendTitle"],
            "Separation rate –\nBiowaste stream (%)",
        )

        script_path = (
            Path(__file__).resolve().parents[1]
            / "waste_atlas"
            / "static"
            / "js"
            / "waste_atlas_choropleth.js"
        )
        script = script_path.read_text()
        wrap_fn = script.split("function _wrapTextToWidth(")[1].split(
            "function _exportLegendLabel("
        )[0]
        self.assertIn("String(label).split(/\\r?\\n/)", wrap_fn)

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
