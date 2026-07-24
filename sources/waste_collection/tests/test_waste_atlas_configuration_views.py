import json
import re
from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

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
        data = {
            "legend_title": configuration["legendTitle"],
            "export_legend_title": configuration.get("exportLegendTitle", ""),
            "legend_placement": configuration.get("legendPlacement", "bottom-left"),
            "legend_width": configuration.get("legendWidth", 300),
            "legend_font_size": configuration.get("legendFontSize", 12),
            "export_legend_placement": configuration.get("exportLegendPlacement", ""),
            "export_legend_width": round(
                configuration.get("exportLegendWidth", 0.52) * 100
            ),
            "export_legend_columns": configuration.get("exportLegendColumns", 1),
        }
        if configuration.get("exportLegendFitContent"):
            data["export_legend_fit_content"] = "on"
        if configuration.get("exportLegendAvoidMapOverlap"):
            data["export_legend_avoid_map_overlap"] = "on"
        for index, category in enumerate(configuration["categories"]):
            data[f"category_{index}_label"] = category["label"]
            data[f"category_{index}_export_label"] = category.get("exportLabel", "")
            data[f"category_{index}_order"] = index + 1
        data.update(overrides)
        return data

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
                export_legend_title="Edited export legend",
                category_0_label="Edited online category",
                category_0_export_label="Edited export category",
                category_0_order=2,
                category_1_order=1,
                legend_placement="top-right",
                legend_width=420,
                legend_font_size=15,
                export_legend_placement="left",
                export_legend_width=38,
                export_legend_columns=2,
                export_legend_fit_content="on",
                export_legend_avoid_map_overlap="on",
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
        self.assertEqual(config.configuration["exportLegendWidth"], 0.38)
        self.assertEqual(config.configuration["exportLegendColumns"], 2)
        self.assertIs(config.configuration["exportLegendFitContent"], True)
        self.assertIs(config.configuration["exportLegendAvoidMapOverlap"], True)
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
            value.pop("exportLegendTitle", None)
            value.pop("legendPlacement", None)
            value.pop("legendWidth", None)
            value.pop("legendFontSize", None)
            value.pop("exportLegendPlacement", None)
            value.pop("exportLegendWidth", None)
            value.pop("exportLegendColumns", None)
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
        self.assertEqual(rendered_config["exportLegendPlacement"], "left")
        self.assertEqual(rendered_config["exportLegendWidth"], 0.38)
        self.assertEqual(rendered_config["exportLegendColumns"], 2)
        self.assertEqual(
            rendered_config["legendCategoryOrder"],
            config.configuration["legendCategoryOrder"],
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

    def test_renderer_uses_configured_legend_layout_and_category_order(self):
        script_path = (
            Path(__file__).resolve().parents[1]
            / "waste_atlas"
            / "static"
            / "js"
            / "waste_atlas_choropleth.js"
        )
        script = script_path.read_text()

        self.assertIn("cfg.legendPlacement", script)
        self.assertIn("cfg.legendWidth", script)
        self.assertIn("cfg.legendFontSize", script)
        self.assertIn("cfg.legendCategoryOrder", script)
        self.assertIn("function _orderedLegendCategories(cfg)", script)

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
                export_legend_placement="top-left",
                export_legend_width=45,
                export_legend_columns=2,
                return_to=reverse("waste-atlas-sweden-residual-collection-amount-map"),
            ),
        )

        map_response = self.client.get(response["Location"])
        rendered_config = self._rendered_map_config(map_response)
        self.assertEqual(rendered_config["exportLegendPlacement"], "top-left")
        self.assertEqual(rendered_config["exportLegendWidth"], 0.45)
        self.assertEqual(rendered_config["exportLegendColumns"], 2)
