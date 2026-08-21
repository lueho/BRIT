import json
import re
from copy import deepcopy
from urllib.parse import parse_qs, urlencode, urlsplit

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from sources.waste_collection.waste_atlas.legend import quartile_legend_entries
from sources.waste_collection.waste_atlas.models import (
    WasteAtlasMapConfiguration,
)
from sources.waste_collection.waste_atlas.pages import MAP_PAGES


class WasteAtlasMapConfigurationViewsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(
            username="atlas-config-staff",
            password="secret",
            is_staff=True,
        )
        cls.regular_user = User.objects.create_user(
            username="atlas-config-user",
            password="secret",
        )
        atlas_group, _ = Group.objects.get_or_create(name="waste_atlas")
        cls.staff.groups.add(atlas_group)
        cls.regular_user.groups.add(atlas_group)

    def _configuration(self):
        return WasteAtlasMapConfiguration.objects.get(key="collection_system")

    def _form_data(self, configuration, **overrides):
        stored_columns = configuration.get("exportLegendColumns", "auto")
        data = {
            "legend_title": configuration["legendTitle"],
            "legend_note": configuration.get("legendNote", ""),
            "export_legend_title": configuration.get("exportLegendTitle", ""),
            "legend_placement": configuration.get("legendPlacement", "bottom-left"),
            "legend_width": configuration.get("legendWidth", 300),
            "legend_font_size": configuration.get("legendFontSize", 12),
            "export_legend_placement": configuration.get(
                "exportLegendPlacement", "auto"
            ),
            "export_legend_width": round(
                configuration.get("exportLegendWidth", 0.52) * 100
            ),
            "export_legend_columns": str(stored_columns),
            # Blank means "inherit the atlas default".
            "export_legend_item_flow": configuration.get("exportLegendItemFlow", ""),
        }
        # Any stored export-legend override means the map customizes the export.
        if any(
            key in configuration
            for key in (
                "exportLegendPlacement",
                "exportLegendColumns",
                "exportLegendItemFlow",
                "exportLegendWidth",
            )
        ):
            data["export_legend_customize"] = "on"
        if configuration.get("showOnlyPresentCategories"):
            data["show_only_present_categories"] = "on"
        for index, category in enumerate(configuration["categories"]):
            data[f"category_{index}_label"] = category["label"]
            data[f"category_{index}_export_label"] = category.get("exportLabel", "")
            data[f"category_{index}_order"] = index + 1
        # Quartile maps also order the data-derived quartile classes.
        for offset, entry in enumerate(quartile_legend_entries(configuration)):
            data[f"quartile_{entry['value']}_order"] = (
                len(configuration["categories"]) + offset + 1
            )
        data.update(overrides)
        return data

    def test_staff_can_hide_categories_that_are_absent_from_the_map(self):
        config = self._configuration()
        original = deepcopy(config.configuration)
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("waste-atlas-map-configuration-update", args=[config.key]),
            self._form_data(original, show_only_present_categories="on"),
        )

        self.assertEqual(response.status_code, 302)
        config.refresh_from_db()
        self.assertTrue(config.configuration["showOnlyPresentCategories"])

        edit_response = self.client.get(
            reverse("waste-atlas-map-configuration-update", args=[config.key])
        )
        self.assertEqual(edit_response.status_code, 200)
        self.assertTrue(
            edit_response.context["form"]["show_only_present_categories"].value()
        )
        self.assertContains(edit_response, "Hide categories not present on this map")

        disabled_data = self._form_data(config.configuration)
        disabled_data.pop("show_only_present_categories")
        response = self.client.post(
            reverse("waste-atlas-map-configuration-update", args=[config.key]),
            disabled_data,
        )

        self.assertEqual(response.status_code, 302)
        config.refresh_from_db()
        self.assertNotIn("showOnlyPresentCategories", config.configuration)

    def _rendered_map_config(self, response):
        match = re.search(
            r'<script id="atlas-config" type="application/json">(.*?)</script>',
            response.content.decode(),
            re.S,
        )
        self.assertIsNotNone(match)
        return json.loads(match.group(1))

    def test_configuration_list_requires_staff(self):
        url = reverse("waste-atlas-map-configuration-list")

        anonymous_response = self.client.get(url)
        self.assertEqual(anonymous_response.status_code, 302)

        self.client.force_login(self.regular_user)
        regular_response = self.client.get(url)
        self.assertEqual(regular_response.status_code, 403)

        self.client.force_login(self.staff)
        staff_response = self.client.get(url)
        self.assertEqual(staff_response.status_code, 200)
        self.assertContains(staff_response, "collection_system")

    def test_non_staff_user_cannot_update_configuration(self):
        config = self._configuration()
        original = deepcopy(config.configuration)
        self.client.force_login(self.regular_user)

        response = self.client.post(
            reverse("waste-atlas-map-configuration-update", args=[config.key]),
            self._form_data(
                original,
                legend_title="Unauthorized legend title",
            ),
        )

        self.assertEqual(response.status_code, 403)
        config.refresh_from_db()
        self.assertEqual(config.configuration, original)

    def test_staff_update_is_per_configuration_and_reaches_preview_and_export(self):
        config = self._configuration()
        map_url = f"{reverse('waste-atlas-germany-collection-system-map')}?year=2023"
        untouched = WasteAtlasMapConfiguration.objects.create(
            key="untouched-test-configuration",
            configuration={
                "legendTitle": "Untouched legend",
                "categories": [],
            },
        )
        original = deepcopy(config.configuration)
        untouched_original = deepcopy(untouched.configuration)
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("waste-atlas-map-configuration-update", args=[config.key]),
            self._form_data(
                original,
                legend_title="Edited online legend",
                legend_note="An explanatory legend note",
                export_legend_title="Edited export legend",
                category_0_label="Edited online category",
                category_0_export_label="Edited export category",
                category_0_order=2,
                category_1_order=1,
                legend_placement="top-right",
                legend_width=420,
                legend_font_size=15,
                export_legend_customize="on",
                export_legend_placement="left",
                export_legend_map_layout="fit",
                export_legend_width=38,
                export_legend_columns="2",
                export_legend_item_flow="row",
                return_to=map_url,
            ),
        )

        redirect = urlsplit(response["Location"])
        self.assertEqual(
            redirect.path,
            reverse("waste-atlas-germany-collection-system-map"),
        )
        redirect_query = parse_qs(redirect.query)
        self.assertEqual(redirect_query["year"], ["2023"])
        self.assertIn("config_updated", redirect_query)
        config.refresh_from_db()
        untouched.refresh_from_db()
        self.assertEqual(
            config.configuration["legendTitle"],
            "Edited online legend",
        )
        self.assertEqual(
            config.configuration["legendNote"],
            "An explanatory legend note",
        )
        self.assertEqual(
            config.configuration["exportLegendTitle"],
            "Edited export legend",
        )
        self.assertEqual(
            config.configuration["categories"][0]["label"],
            "Edited online category",
        )
        self.assertEqual(
            config.configuration["categories"][0]["exportLabel"],
            "Edited export category",
        )
        self.assertEqual(config.configuration["legendPlacement"], "top-right")
        self.assertEqual(config.configuration["legendWidth"], 420)
        self.assertEqual(config.configuration["legendFontSize"], 15)
        self.assertEqual(config.configuration["exportLegendPlacement"], "left")
        self.assertEqual(config.configuration["exportLegendMapLayout"], "fit")
        self.assertEqual(config.configuration["exportLegendWidth"], 0.38)
        self.assertEqual(config.configuration["exportLegendColumns"], 2)
        self.assertEqual(config.configuration["exportLegendItemFlow"], "row")
        # Retired options are never persisted.
        self.assertNotIn("exportLegendFitContent", config.configuration)
        self.assertNotIn("exportLegendAvoidMapOverlap", config.configuration)
        self.assertEqual(
            config.configuration["legendCategoryOrder"][:2],
            [
                original["categories"][1]["value"],
                original["categories"][0]["value"],
            ],
        )
        preserved_original = deepcopy(original)
        preserved_updated = deepcopy(config.configuration)
        for value in (preserved_original, preserved_updated):
            value.pop("legendTitle", None)
            value.pop("legendNote", None)
            value.pop("exportLegendTitle", None)
            value.pop("legendPlacement", None)
            value.pop("legendWidth", None)
            value.pop("legendFontSize", None)
            value.pop("exportLegendPlacement", None)
            value.pop("exportLegendMapLayout", None)
            value.pop("exportLegendWidth", None)
            value.pop("exportLegendColumns", None)
            value.pop("exportLegendItemFlow", None)
            value.pop("exportLegendFitContent", None)
            value.pop("exportLegendAvoidMapOverlap", None)
            value.pop("legendCategoryOrder", None)
            for category in value["categories"]:
                category.pop("label", None)
                category.pop("exportLabel", None)
        self.assertEqual(preserved_updated, preserved_original)
        self.assertEqual(untouched.configuration, untouched_original)

        map_response = self.client.get(response["Location"])
        self.assertIn("no-cache", map_response.headers["Cache-Control"])
        self.assertIn("no-store", map_response.headers["Cache-Control"])
        rendered_config = self._rendered_map_config(map_response)
        self.assertEqual(rendered_config["legendTitle"], "Edited online legend")
        self.assertEqual(rendered_config["legendNote"], "An explanatory legend note")
        self.assertEqual(
            rendered_config["exportLegendTitle"],
            "Edited export legend",
        )
        self.assertEqual(
            rendered_config["categories"][0]["label"],
            "Edited online category",
        )
        self.assertEqual(
            rendered_config["categories"][0]["exportLabel"],
            "Edited export category",
        )
        self.assertEqual(rendered_config["legendPlacement"], "top-right")
        self.assertEqual(rendered_config["legendWidth"], 420)
        self.assertEqual(rendered_config["legendFontSize"], 15)
        # The renderer receives one resolved object, not flat layout keys.
        self.assertEqual(
            rendered_config["exportLegend"],
            {
                "placement": "left",
                "mapLayout": "fit",
                "columns": 2,
                "itemFlow": "row",
                "maxWidthFraction": 0.38,
            },
        )
        self.assertNotIn("exportLegendPlacement", rendered_config)
        self.assertEqual(
            rendered_config["legendCategoryOrder"],
            config.configuration["legendCategoryOrder"],
        )

    def test_automatic_placement_with_width_and_columns_persists(self):
        """Regression: Automatic placement must still persist width and columns.

        The reported bug used Automatic placement, 52% maximum width and one
        column, yet the export rendered a wide three-column bottom legend
        because the form dropped width/columns whenever placement was blank.
        With the redesign, Automatic is an explicit ``auto`` value that keeps
        the constraints and reaches the resolved ``exportLegend`` config.
        """
        config = self._configuration()
        map_url = reverse("waste-atlas-germany-collection-system-map")
        original = deepcopy(config.configuration)
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("waste-atlas-map-configuration-update", args=[config.key]),
            self._form_data(
                original,
                export_legend_customize="on",
                export_legend_placement="auto",
                export_legend_width=52,
                export_legend_columns="1",
                return_to=map_url,
            ),
        )

        self.assertEqual(response.status_code, 302)
        config.refresh_from_db()
        self.assertEqual(config.configuration["exportLegendPlacement"], "auto")
        self.assertEqual(config.configuration["exportLegendColumns"], 1)
        self.assertEqual(config.configuration["exportLegendWidth"], 0.52)

        map_response = self.client.get(response["Location"])
        rendered_config = self._rendered_map_config(map_response)
        self.assertEqual(
            rendered_config["exportLegend"],
            {
                "placement": "auto",
                "mapLayout": "auto",
                "columns": 1,
                "itemFlow": "column",
                "maxWidthFraction": 0.52,
            },
        )

    def test_blank_export_text_uses_preview_text_fallback(self):
        config = self._configuration()
        original = deepcopy(config.configuration)
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("waste-atlas-map-configuration-update", args=[config.key]),
            self._form_data(
                original,
                legend_title="Shared legend title",
                export_legend_title="",
                category_0_label="Shared category name",
                category_0_export_label="",
            ),
        )

        self.assertEqual(response.status_code, 302)
        config.refresh_from_db()
        self.assertNotIn("exportLegendTitle", config.configuration)
        self.assertNotIn("exportLabel", config.configuration["categories"][0])
        self.assertEqual(config.configuration["legendTitle"], "Shared legend title")
        self.assertEqual(
            config.configuration["categories"][0]["label"],
            "Shared category name",
        )

    def test_staff_navigation_and_map_page_link_to_configuration_editor(self):
        config_list_url = reverse("waste-atlas-map-configuration-list")
        config_edit_url = reverse(
            "waste-atlas-map-configuration-update",
            args=["collection_system"],
        )

        self.client.force_login(self.regular_user)
        regular_response = self.client.get(
            reverse("waste-atlas-germany-collection-system-map")
        )
        self.assertNotContains(regular_response, config_list_url)
        self.assertNotContains(regular_response, config_edit_url)

        self.client.force_login(self.staff)
        staff_response = self.client.get(
            reverse("waste-atlas-germany-collection-system-map")
        )
        self.assertContains(staff_response, config_list_url)
        expected_edit_url = f"{config_edit_url}?" + urlencode(
            {"return_to": reverse("waste-atlas-germany-collection-system-map")}
        )
        self.assertContains(staff_response, expected_edit_url)

    def test_unsafe_return_url_is_replaced_with_a_configuration_map(self):
        config = self._configuration()
        original = deepcopy(config.configuration)
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("waste-atlas-map-configuration-update", args=[config.key]),
            self._form_data(
                original,
                return_to="https://example.com/not-the-map/",
            ),
        )

        self.assertEqual(response.status_code, 302)
        redirect = urlsplit(response["Location"])
        valid_map_paths = {
            reverse(page["name"])
            for page in MAP_PAGES
            if page["config_key"] == config.key
        }
        self.assertEqual(redirect.netloc, "")
        self.assertIn(redirect.path, valid_map_paths)

    def test_duplicate_category_positions_are_rejected(self):
        config = self._configuration()
        original = deepcopy(config.configuration)
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("waste-atlas-map-configuration-update", args=[config.key]),
            self._form_data(
                original,
                category_0_order=1,
                category_1_order=1,
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Each category position must be unique.")
        config.refresh_from_db()
        self.assertEqual(config.configuration, original)

    def test_quartile_classes_are_orderable_and_reach_preview_and_export(self):
        """Regression: an amount map's legend order was silently ignored.

        Amount maps classify the data into quartiles at render time, which
        replaces the stored classes with ``q1``-``q4``. The editor therefore has
        to offer those entries as well, otherwise a saved order can only name
        classes the legend never shows.
        """
        config = WasteAtlasMapConfiguration.objects.get(
            key="biowaste_collection_amount"
        )
        original = deepcopy(config.configuration)
        stored_values = [category["value"] for category in original["categories"]]
        self.client.force_login(self.staff)

        form_response = self.client.get(
            reverse("waste-atlas-map-configuration-update", args=[config.key])
        )
        self.assertContains(form_response, "quartile_q1_order")

        response = self.client.post(
            reverse("waste-atlas-map-configuration-update", args=[config.key]),
            self._form_data(
                original,
                # Highest quartile first, "no separate collection" last.
                quartile_q4_order=1,
                quartile_q3_order=2,
                quartile_q2_order=3,
                quartile_q1_order=4,
                **{
                    f"category_{index}_order": index + 5
                    for index in range(len(stored_values))
                },
                return_to=reverse(
                    "waste-atlas-south-tyrol-biowaste-collection-amount-map"
                ),
            ),
        )

        self.assertEqual(response.status_code, 302)
        config.refresh_from_db()
        self.assertEqual(
            config.configuration["legendCategoryOrder"],
            ["q4", "q3", "q2", "q1", *stored_values],
        )

        map_response = self.client.get(response["Location"])
        rendered_config = self._rendered_map_config(map_response)
        self.assertEqual(
            rendered_config["legendCategoryOrder"],
            config.configuration["legendCategoryOrder"],
        )

    def test_quartile_classes_default_to_the_order_the_renderer_uses(self):
        """The editor's initial order must match what the map renders.

        Without a saved order the renderer keeps the configured category order
        and appends the computed quartile classes, so the editor has to list
        the entries the same way.
        """
        config = WasteAtlasMapConfiguration.objects.get(
            key="biowaste_collection_amount"
        )
        configuration = deepcopy(config.configuration)
        configuration.pop("legendCategoryOrder", None)
        config.configuration = configuration
        config.save(update_fields=["configuration"])
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("waste-atlas-map-configuration-update", args=[config.key])
        )

        rows = response.context["form"].category_rows
        self.assertEqual(
            [row["value"] for row in rows],
            ["very_high", "high", "medium", "low", "no_bio", "q1", "q2", "q3", "q4"],
        )
        # Computed entries carry no editable text: their labels are the ranges
        # the renderer derives from the data.
        quartile_rows = [row for row in rows if row["value"].startswith("q")]
        self.assertTrue(all(row["label_field"] is None for row in quartile_rows))

    def test_saved_export_layout_overrides_regional_default(self):
        config, _ = WasteAtlasMapConfiguration.objects.update_or_create(
            key="residual_collection_amount",
            defaults={
                "configuration": {
                    "legendTitle": "Collected amount",
                    "categories": [
                        {
                            "value": "low",
                            "label": "Low",
                            "color": "#dddddd",
                        }
                    ],
                }
            },
        )
        original = deepcopy(config.configuration)
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("waste-atlas-map-configuration-update", args=[config.key]),
            self._form_data(
                original,
                export_legend_customize="on",
                export_legend_placement="top-left",
                export_legend_width=45,
                export_legend_columns="2",
                return_to=reverse("waste-atlas-sweden-residual-collection-amount-map"),
            ),
        )

        map_response = self.client.get(response["Location"])
        rendered_config = self._rendered_map_config(map_response)
        self.assertEqual(
            rendered_config["exportLegend"],
            {
                "placement": "top-left",
                "mapLayout": "auto",
                "columns": 2,
                "itemFlow": "column",
                "maxWidthFraction": 0.45,
            },
        )


class WasteAtlasExportFileNameTestCase(TestCase):
    """Export file names must be derived globally from (map set, theme).

    ``fileBase`` is the stem the choropleth renderer appends ``.svg``/``.png``
    (and ``_change_<from>_<to>`` for change maps) to.  It must follow one
    deterministic rule for every map page instead of being hand-set per page
    or per stored configuration.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="atlas-export-user",
            password="secret",
        )
        atlas_group, _ = Group.objects.get_or_create(name="waste_atlas")
        cls.user.groups.add(atlas_group)

    # (route name, expected fileBase) covering generic, country, sub-national,
    # multi-token selector sets and a theme only seeded for one region.
    EXPECTED_FILE_BASES = (
        ("waste-atlas-orga-level-map", "waste_atlas_orga_level"),
        (
            "waste-atlas-orga-level-italy-map",
            "waste_atlas_it_orga_level",
        ),
        (
            "waste-atlas-germany-collection-system-map",
            "waste_atlas_de_collection_system",
        ),
        (
            "waste-atlas-nrw-participation-policy-map",
            "waste_atlas_de_nw_participation_policy",
        ),
        (
            "waste-atlas-sweden-biowaste-collection-amount-map",
            "waste_atlas_se_biowaste_collection_amount",
        ),
        (
            "waste-atlas-south-tyrol-target-waste-category-map",
            "waste_atlas_it_st_target_waste_category",
        ),
        (
            "waste-atlas-orga-level-belgium-flanders-map",
            "waste_atlas_be_fl_br_orga_level",
        ),
    )

    def test_every_map_page_derives_a_deterministic_file_base(self):
        self.client.force_login(self.user)
        for route_name, expected in self.EXPECTED_FILE_BASES:
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                rendered_config = _rendered_map_config(response)
                self.assertEqual(rendered_config["fileBase"], expected)

    def test_no_map_page_defines_a_manual_file_base_override(self):
        """No page may carry a ``fileBase`` override; naming is global."""
        for page in MAP_PAGES:
            overrides = page.get("overrides") or {}
            with self.subTest(route=page["name"]):
                self.assertNotIn("fileBase", overrides)

    def test_no_stored_configuration_carries_a_file_base(self):
        """Stored configs must not keep a stale ``fileBase`` key."""
        for config in WasteAtlasMapConfiguration.objects.all():
            with self.subTest(key=config.key):
                self.assertNotIn("fileBase", config.configuration)


def _rendered_map_config(response):
    match = re.search(
        r'<script id="atlas-config" type="application/json">(.*?)</script>',
        response.content.decode(),
        re.S,
    )
    assert match is not None, "atlas-config script not rendered"
    return json.loads(match.group(1))
