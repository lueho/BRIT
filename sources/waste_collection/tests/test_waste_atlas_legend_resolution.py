"""Export-legend configuration semantics: inherit / auto / fixed + precedence.

The export legend has three independent settings (placement, columns, maximum
width). Each is resolved with explicit *inherit* (missing), *auto* (decide
automatically) and *fixed* semantics, with precedence page/region override ->
stored theme config -> atlas defaults. These tests pin that resolution down
directly and through the form and template tag.
"""

from django.template import Context
from django.test import TestCase

from sources.waste_collection.waste_atlas.forms import (
    WasteAtlasMapConfigurationForm,
)
from sources.waste_collection.waste_atlas.legend import (
    resolve_export_legend,
)
from sources.waste_collection.waste_atlas.models import (
    WasteAtlasMapConfiguration,
    WasteAtlasRenderingSettings,
)
from sources.waste_collection.waste_atlas.templatetags.atlas_tags import (
    atlas_js_config,
)

ATLAS_DEFAULTS = {"placement": "auto", "columns": "auto", "maxWidthFraction": 0.52}


class ResolveExportLegendTests(TestCase):
    def _resolve(self, stored=None, page_overrides=None, defaults=None):
        return resolve_export_legend(
            stored=stored,
            page_overrides=page_overrides,
            defaults=defaults or ATLAS_DEFAULTS,
        )

    def test_missing_keys_inherit_the_atlas_defaults(self):
        self.assertEqual(self._resolve(stored={}), ATLAS_DEFAULTS)

    def test_explicit_auto_is_distinct_from_inherit_but_resolves_to_auto(self):
        resolved = self._resolve(
            stored={
                "exportLegendPlacement": "auto",
                "exportLegendColumns": "auto",
                "exportLegendWidth": 0.4,
            }
        )
        self.assertEqual(
            resolved,
            {"placement": "auto", "columns": "auto", "maxWidthFraction": 0.4},
        )

    def test_fixed_values_are_honoured(self):
        resolved = self._resolve(
            stored={
                "exportLegendPlacement": "left",
                "exportLegendColumns": 1,
                "exportLegendWidth": 0.52,
            }
        )
        self.assertEqual(
            resolved,
            {"placement": "left", "columns": 1, "maxWidthFraction": 0.52},
        )

    def test_page_override_wins_over_stored_theme_config(self):
        resolved = self._resolve(
            stored={
                "exportLegendPlacement": "left",
                "exportLegendColumns": 2,
                "exportLegendWidth": 0.4,
            },
            page_overrides={
                "exportLegendPlacement": "right",
                "exportLegendColumns": 1,
            },
        )
        # Placement/columns come from the page; width still inherits the theme.
        self.assertEqual(
            resolved,
            {"placement": "right", "columns": 1, "maxWidthFraction": 0.4},
        )

    def test_stored_wins_over_atlas_default_when_no_page_override(self):
        resolved = self._resolve(stored={"exportLegendWidth": 0.7})
        self.assertEqual(
            resolved,
            {"placement": "auto", "columns": "auto", "maxWidthFraction": 0.7},
        )

    def test_retired_keys_do_not_affect_resolution(self):
        resolved = self._resolve(
            stored={
                "exportLegendFitContent": True,
                "exportLegendAvoidMapOverlap": True,
                "exportLegendBottomColumns": 3,
            }
        )
        self.assertEqual(resolved, ATLAS_DEFAULTS)

    def test_out_of_range_width_is_clamped(self):
        self.assertEqual(
            self._resolve(stored={"exportLegendWidth": 5})["maxWidthFraction"],
            0.9,
        )

    def test_invalid_values_fall_through_to_the_next_layer(self):
        resolved = self._resolve(
            stored={
                "exportLegendPlacement": "nonsense",
                "exportLegendColumns": 9,
            }
        )
        self.assertEqual(resolved["placement"], "auto")
        self.assertEqual(resolved["columns"], "auto")


class AtlasJsConfigExportLegendTests(TestCase):
    @staticmethod
    def _config(**context):
        return atlas_js_config(Context(context), "collection_system")

    def _store(self, **legend):
        configuration = WasteAtlasMapConfiguration.objects.get(key="collection_system")
        configuration.configuration.update(legend)
        configuration.save(update_fields=["configuration"])

    def test_default_config_resolves_to_the_atlas_defaults(self):
        WasteAtlasRenderingSettings.load()
        config = self._config()
        self.assertEqual(config["exportLegend"], ATLAS_DEFAULTS)
        # Flat/legacy layout keys are never emitted to the renderer.
        for key in (
            "exportLegendPlacement",
            "exportLegendColumns",
            "exportLegendWidth",
        ):
            self.assertNotIn(key, config)

    def test_stored_fixed_values_reach_the_resolved_object(self):
        self._store(
            exportLegendPlacement="right",
            exportLegendColumns=1,
            exportLegendWidth=0.52,
        )
        self.assertEqual(
            self._config()["exportLegend"],
            {"placement": "right", "columns": 1, "maxWidthFraction": 0.52},
        )

    def test_page_override_wins_over_stored_theme_config(self):
        self._store(exportLegendPlacement="left", exportLegendColumns=2)
        config = self._config(map_config_overrides={"exportLegendPlacement": "bottom"})
        self.assertEqual(config["exportLegend"]["placement"], "bottom")
        self.assertEqual(config["exportLegend"]["columns"], 2)

    def test_legacy_keys_stored_on_a_config_are_stripped(self):
        self._store(exportLegendFitContent=True, exportLegendAvoidMapOverlap=True)
        config = self._config()
        self.assertNotIn("exportLegendFitContent", config)
        self.assertNotIn("exportLegendAvoidMapOverlap", config)


class ExportLegendFormSemanticsTests(TestCase):
    def _configuration(self):
        return WasteAtlasMapConfiguration.objects.get(key="collection_system")

    def _base_data(self, configuration, **overrides):
        data = {
            "legend_title": configuration.configuration["legendTitle"],
            "export_legend_title": "",
            "legend_placement": "bottom-left",
            "legend_width": 300,
            "legend_font_size": 12,
            "export_legend_placement": "auto",
            "export_legend_columns": "auto",
            "export_legend_width": 52,
        }
        for index, category in enumerate(configuration.configuration["categories"]):
            data[f"category_{index}_label"] = category["label"]
            data[f"category_{index}_export_label"] = category.get("exportLabel", "")
            data[f"category_{index}_order"] = index + 1
        data.update(overrides)
        return data

    def test_use_atlas_defaults_removes_the_theme_override(self):
        configuration = self._configuration()
        configuration.configuration.update(
            {
                "exportLegendPlacement": "left",
                "exportLegendColumns": 2,
                "exportLegendWidth": 0.4,
            }
        )
        configuration.save(update_fields=["configuration"])

        form = WasteAtlasMapConfigurationForm(
            data=self._base_data(configuration),  # customize checkbox absent = off
            instance=configuration,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        configuration.refresh_from_db()
        for key in (
            "exportLegendPlacement",
            "exportLegendColumns",
            "exportLegendWidth",
        ):
            self.assertNotIn(key, configuration.configuration)

    def test_customized_automatic_placement_persists_auto(self):
        configuration = self._configuration()
        form = WasteAtlasMapConfigurationForm(
            data=self._base_data(
                configuration,
                export_legend_customize="on",
                export_legend_placement="auto",
                export_legend_columns="auto",
                export_legend_width=52,
            ),
            instance=configuration,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        configuration.refresh_from_db()
        self.assertEqual(configuration.configuration["exportLegendPlacement"], "auto")
        self.assertEqual(configuration.configuration["exportLegendColumns"], "auto")
        self.assertEqual(configuration.configuration["exportLegendWidth"], 0.52)

    def test_blank_maximum_width_preserves_inheritance(self):
        configuration = self._configuration()
        data = self._base_data(
            configuration,
            export_legend_customize="on",
            export_legend_placement="auto",
            export_legend_columns="1",
        )
        data["export_legend_width"] = ""
        form = WasteAtlasMapConfigurationForm(data=data, instance=configuration)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        configuration.refresh_from_db()
        self.assertEqual(configuration.configuration["exportLegendPlacement"], "auto")
        self.assertEqual(configuration.configuration["exportLegendColumns"], 1)
        # A blank width must inherit rather than freeze the atlas default.
        self.assertNotIn("exportLegendWidth", configuration.configuration)

        # Inheritance must be durable: reopening shows a blank width (the atlas
        # default is only a placeholder), and saving again keeps it inherited
        # instead of freezing the resolved value.
        reopened = WasteAtlasMapConfigurationForm(instance=configuration)
        self.assertIsNone(reopened.initial.get("export_legend_width"))

        resave = WasteAtlasMapConfigurationForm(
            data=self._base_data(
                configuration,
                export_legend_customize="on",
                export_legend_placement="auto",
                export_legend_columns="1",
                **{"export_legend_width": ""},
            ),
            instance=configuration,
        )
        self.assertTrue(resave.is_valid(), resave.errors)
        resave.save()
        configuration.refresh_from_db()
        self.assertNotIn("exportLegendWidth", configuration.configuration)

    def test_customize_toggle_initial_reflects_stored_override(self):
        configuration = self._configuration()
        inherit_form = WasteAtlasMapConfigurationForm(instance=configuration)
        self.assertFalse(inherit_form.initial["export_legend_customize"])

        configuration.configuration["exportLegendPlacement"] = "auto"
        configuration.save(update_fields=["configuration"])
        custom_form = WasteAtlasMapConfigurationForm(instance=configuration)
        self.assertTrue(custom_form.initial["export_legend_customize"])
        self.assertEqual(custom_form.initial["export_legend_placement"], "auto")
