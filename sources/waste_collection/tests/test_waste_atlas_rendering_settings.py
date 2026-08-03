"""Database-backed Waste Atlas rendering and export defaults.

Every value the renderer needs that is not specific to a single map lives in a
singleton ``WasteAtlasRenderingSettings`` row: palette colors, legend defaults
and export page geometry.  These tests pin down that the renderer, the
configuration form and the export file naming all read those values from the
database instead of module-level constants.
"""

from pathlib import Path

from django.template import Context, Template
from django.test import TestCase

from sources.waste_collection.waste_atlas.forms import (
    WasteAtlasMapConfigurationForm,
)
from sources.waste_collection.waste_atlas.models import (
    WasteAtlasMapConfiguration,
    WasteAtlasRenderingSettings,
)
from sources.waste_collection.waste_atlas.templatetags.atlas_tags import (
    atlas_js_config,
)

CHOROPLETH_JS = (
    Path(__file__).resolve().parents[1]
    / "waste_atlas"
    / "static"
    / "js"
    / "waste_atlas_choropleth.js"
)


class WasteAtlasRenderingSettingsModelTests(TestCase):
    def test_settings_row_is_seeded_by_migration(self):
        self.assertEqual(WasteAtlasRenderingSettings.objects.count(), 1)
        settings = WasteAtlasRenderingSettings.load()
        self.assertEqual(settings.no_data_color, "#e0e0e0")
        self.assertEqual(settings.no_collection_color, "#fff696")
        self.assertEqual(settings.export_dpi, 300)
        self.assertEqual(settings.export_width_mm, 160)
        self.assertEqual(settings.export_height_mm, 110)
        self.assertEqual(settings.export_max_height_mm, 180)
        self.assertEqual(settings.export_file_name_prefix, "waste_atlas")

    def test_load_never_creates_a_second_row(self):
        WasteAtlasRenderingSettings.load()
        WasteAtlasRenderingSettings.load()
        self.assertEqual(WasteAtlasRenderingSettings.objects.count(), 1)

    def test_client_defaults_expose_the_stored_values(self):
        settings = WasteAtlasRenderingSettings.load()
        settings.no_data_color = "#123456"
        settings.legend_width = 420
        settings.export_dpi = 150
        settings.quartile_colors = ["#111111", "#222222", "#333333", "#444444"]
        settings.save()

        defaults = WasteAtlasRenderingSettings.load().client_defaults()

        self.assertEqual(defaults["noDataColor"], "#123456")
        self.assertEqual(defaults["legend"]["width"], 420)
        self.assertEqual(defaults["export"]["dpi"], 150)
        self.assertEqual(defaults["quartileColors"][0], "#111111")
        self.assertEqual(defaults["changeColors"]["increase"], "#1a9850")


class WasteAtlasRenderingSettingsConfigTests(TestCase):
    @staticmethod
    def _config(**context):
        return atlas_js_config(Context(context), "collection_system")

    def test_js_config_carries_the_database_rendering_defaults(self):
        settings = WasteAtlasRenderingSettings.load()
        settings.country_fill_color = "#abcdef"
        settings.export_height_mm = 120
        settings.save()

        config = self._config()

        self.assertEqual(config["renderDefaults"]["countryFill"], "#abcdef")
        self.assertEqual(config["renderDefaults"]["export"]["heightMm"], 120)

    def test_export_file_prefix_comes_from_the_database(self):
        settings = WasteAtlasRenderingSettings.load()
        settings.export_file_name_prefix = "atlas"
        settings.save()

        config = self._config(
            atlas_page_selector_set="DE-NW",
            atlas_active_theme="collection_system",
        )

        self.assertEqual(config["fileBase"], "atlas_de_nw_collection_system")

    def test_stored_map_configuration_wins_over_the_global_default(self):
        """A per-map ``noDataColor`` must not be overwritten by the default."""
        configuration = WasteAtlasMapConfiguration.objects.get(key="collection_system")
        configuration.configuration["noDataColor"] = "#0f0f0f"
        configuration.save(update_fields=["configuration"])

        self.assertEqual(self._config()["noDataColor"], "#0f0f0f")

    def test_maps_without_a_stored_no_data_color_fall_back_to_the_default(self):
        settings = WasteAtlasRenderingSettings.load()
        settings.no_data_color = "#654321"
        settings.save()
        configuration = WasteAtlasMapConfiguration.objects.get(key="collection_system")
        configuration.configuration.pop("noDataColor", None)
        configuration.save(update_fields=["configuration"])

        self.assertEqual(self._config()["noDataColor"], "#654321")

    def test_template_tag_renders_the_defaults_into_the_page(self):
        template = Template(
            "{% load atlas_tags %}"
            "{% atlas_js_config 'collection_system' as cfg %}"
            "{{ cfg.renderDefaults.noDataColor }}"
        )
        self.assertIn("#e0e0e0", template.render(Context({})))


class WasteAtlasLegendFormDefaultTests(TestCase):
    def test_form_initials_follow_the_database_legend_defaults(self):
        settings = WasteAtlasRenderingSettings.load()
        settings.legend_placement = "top-right"
        settings.legend_width = 360
        settings.legend_font_size = 14
        settings.export_legend_width_fraction = 0.6
        settings.save()

        configuration = WasteAtlasMapConfiguration.objects.get(key="collection_system")
        for key in (
            "legendPlacement",
            "legendWidth",
            "legendFontSize",
            "exportLegendWidth",
        ):
            configuration.configuration.pop(key, None)
        configuration.save(update_fields=["configuration"])

        form = WasteAtlasMapConfigurationForm(instance=configuration)

        self.assertEqual(form.initial["legend_placement"], "top-right")
        self.assertEqual(form.initial["legend_width"], 360)
        self.assertEqual(form.initial["legend_font_size"], 14)
        self.assertEqual(form.initial["export_legend_width"], 60)


class WasteAtlasRendererHasNoHardcodedDefaultsTests(TestCase):
    """The renderer must take its defaults from the injected configuration."""

    FORBIDDEN_LITERALS = (
        "#e0e0e0",
        "#f0f0f0",
        "#666666",
        "#232323",
        "#d7263d",
        "#c8e6c9",
        "#ffb74d",
        "#64b5f6",
        "#bdbdbd",
        "#d9f0d3",
        "'waste_atlas",
    )

    def test_renderer_source_has_no_hardcoded_configuration_values(self):
        source = CHOROPLETH_JS.read_text()
        for literal in self.FORBIDDEN_LITERALS:
            with self.subTest(literal=literal):
                self.assertNotIn(literal, source)

    def test_renderer_applies_the_injected_defaults(self):
        source = CHOROPLETH_JS.read_text()
        self.assertIn("renderDefaults", source)
