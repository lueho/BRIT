import django.core.validators
from django.db import migrations, models

import sources.waste_collection.waste_atlas.models


class Migration(migrations.Migration):
    replaces = [
        ("waste_atlas", "0001_initial"),
        ("waste_atlas", "0002_seed_map_configurations"),
        ("waste_atlas", "0003_seed_target_waste_category"),
        ("waste_atlas", "0004_drop_file_base_from_map_configurations"),
        ("waste_atlas", "0004_seed_residual_waste_composition_maps"),
        ("waste_atlas", "0005_merge_20260730_1555"),
        ("waste_atlas", "0006_add_residual_collection_amount_acpv_overlay"),
        ("waste_atlas", "0006_wasteatlasrenderingsettings"),
        ("waste_atlas", "0007_add_waste_ratio_aggregated_overlay"),
        ("waste_atlas", "0007_seed_rendering_settings"),
        ("waste_atlas", "0008_drop_redundant_no_data_color"),
        ("waste_atlas", "0009_drop_placement_coupled_legend_columns"),
        (
            "waste_atlas",
            "0010_wasteatlasrenderingsettings_change_boundary_changed_color",
        ),
        ("waste_atlas", "0011_wasteatlasrenderingsettings_export_legend_item_flow"),
        ("waste_atlas", "0012_wasteatlasrenderingsettings_acpv_hatch_color_and_more"),
        ("waste_atlas", "0013_centralize_acpv_marker_appearance"),
        (
            "waste_atlas",
            "0014_alter_wasteatlasrenderingsettings_export_legend_item_flow",
        ),
        ("waste_atlas", "0014_seed_rp_map_configurations"),
        ("waste_atlas", "0015_merge_legend_flow_and_rp_configurations"),
        ("waste_atlas", "0016_distinguish_no_collection_from_no_door_to_door"),
        ("waste_atlas", "0017_disable_connection_rate_quartiles"),
        ("waste_atlas", "0018_configure_connection_rate_boundaries"),
        ("waste_atlas", "0019_include_all_connection_rates_in_quartiles"),
        ("waste_atlas", "0020_reclassify_min_bin_sizes"),
        ("waste_atlas", "0021_hide_absent_min_bin_size_categories"),
        ("waste_atlas", "0022_add_access_control_legend_note"),
        ("waste_atlas", "0023_add_organic_amount_no_collection"),
        ("waste_atlas", "0024_group_access_control_export_legend"),
        ("waste_atlas", "0025_compact_system_access_control_legend"),
        ("waste_atlas", "0026_add_organic_ratio_no_collection"),
        ("waste_atlas", "0027_move_stored_urls_to_atlas_prefix"),
    ]

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="WasteAtlasMapConfiguration",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "key",
                    models.SlugField(
                        help_text="Stable key referenced by the Waste Atlas page registry.",
                        max_length=100,
                        unique=True,
                    ),
                ),
                (
                    "configuration",
                    models.JSONField(
                        default=dict,
                        help_text="JSON object passed to the Waste Atlas choropleth renderer.",
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Waste Atlas map configuration",
                "verbose_name_plural": "Waste Atlas map configurations",
                "ordering": ("key",),
                "indexes": [],
                "constraints": [],
            },
        ),
        migrations.CreateModel(
            name="WasteAtlasRenderingSettings",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "no_data_color",
                    models.CharField(
                        default="#e0e0e0",
                        help_text="Fill for regions without data.",
                        max_length=7,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Enter a hex color such as #e0e0e0.",
                                regex="^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
                            )
                        ],
                    ),
                ),
                (
                    "no_collection_color",
                    models.CharField(
                        default="#fff696",
                        help_text="Fill for regions without a separate collection.",
                        max_length=7,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Enter a hex color such as #e0e0e0.",
                                regex="^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
                            )
                        ],
                    ),
                ),
                (
                    "country_fill_color",
                    models.CharField(
                        default="#f0f0f0",
                        help_text="Base fill of the country layer.",
                        max_length=7,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Enter a hex color such as #e0e0e0.",
                                regex="^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
                            )
                        ],
                    ),
                ),
                (
                    "country_stroke_color",
                    models.CharField(
                        default="#000000",
                        help_text="Outline color of the country border.",
                        max_length=7,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Enter a hex color such as #e0e0e0.",
                                regex="^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
                            )
                        ],
                    ),
                ),
                (
                    "country_stroke_width",
                    models.FloatField(
                        default=1.5,
                        help_text="Outline width of the country border in pixels.",
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "subdivision_stroke_color",
                    models.CharField(
                        default="#666666",
                        help_text="Outline color of first-level subdivisions (e.g. Bundesländer).",
                        max_length=7,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Enter a hex color such as #e0e0e0.",
                                regex="^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
                            )
                        ],
                    ),
                ),
                (
                    "subdivision_stroke_width",
                    models.FloatField(
                        default=1.0,
                        help_text="Outline width of first-level subdivisions in pixels.",
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "catchment_stroke_color",
                    models.CharField(
                        default="#232323",
                        help_text="Outline color of catchments.",
                        max_length=7,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Enter a hex color such as #e0e0e0.",
                                regex="^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
                            )
                        ],
                    ),
                ),
                (
                    "catchment_stroke_width",
                    models.FloatField(
                        default=0.35,
                        help_text="Outline width of catchments in pixels.",
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "conflict_stroke_color",
                    models.CharField(
                        default="#d7263d",
                        help_text="Outline color highlighting catchments with conflicting collections.",
                        max_length=7,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Enter a hex color such as #e0e0e0.",
                                regex="^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
                            )
                        ],
                    ),
                ),
                (
                    "conflict_stroke_width",
                    models.FloatField(
                        default=1.6,
                        help_text="Outline width of the conflict highlight in pixels.",
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "conflict_stroke_dasharray",
                    models.CharField(
                        default="3 2",
                        help_text="SVG dash pattern of the conflict highlight.",
                        max_length=32,
                    ),
                ),
                (
                    "quartile_colors",
                    models.JSONField(
                        default=sources.waste_collection.waste_atlas.models.default_quartile_colors,
                        help_text="Four hex colors used for quartile classification, low to high.",
                    ),
                ),
                (
                    "change_no_change_color",
                    models.CharField(
                        default="#c8e6c9",
                        help_text="Change maps: regions that did not change.",
                        max_length=7,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Enter a hex color such as #e0e0e0.",
                                regex="^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
                            )
                        ],
                    ),
                ),
                (
                    "change_changed_color",
                    models.CharField(
                        default="#ffb74d",
                        help_text="Change maps: regions whose category changed.",
                        max_length=7,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Enter a hex color such as #e0e0e0.",
                                regex="^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
                            )
                        ],
                    ),
                ),
                (
                    "change_new_color",
                    models.CharField(
                        default="#64b5f6",
                        help_text="Change maps: regions with data only in the later year.",
                        max_length=7,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Enter a hex color such as #e0e0e0.",
                                regex="^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
                            )
                        ],
                    ),
                ),
                (
                    "change_removed_color",
                    models.CharField(
                        default="#bdbdbd",
                        help_text="Change maps: regions with data only in the earlier year.",
                        max_length=7,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Enter a hex color such as #e0e0e0.",
                                regex="^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
                            )
                        ],
                    ),
                ),
                (
                    "change_increase_color",
                    models.CharField(
                        default="#1a9850",
                        help_text="Change maps: numeric increase.",
                        max_length=7,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Enter a hex color such as #e0e0e0.",
                                regex="^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
                            )
                        ],
                    ),
                ),
                (
                    "change_decrease_color",
                    models.CharField(
                        default="#d73027",
                        help_text="Change maps: numeric decrease.",
                        max_length=7,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Enter a hex color such as #e0e0e0.",
                                regex="^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
                            )
                        ],
                    ),
                ),
                (
                    "legend_placement",
                    models.CharField(
                        choices=[
                            ("bottom-left", "Bottom left"),
                            ("bottom-right", "Bottom right"),
                            ("top-left", "Top left"),
                            ("top-right", "Top right"),
                        ],
                        default="bottom-left",
                        help_text="Default on-screen legend placement.",
                        max_length=20,
                    ),
                ),
                (
                    "legend_width",
                    models.PositiveIntegerField(
                        default=300,
                        help_text="Default on-screen legend width in pixels.",
                        validators=[
                            django.core.validators.MinValueValidator(180),
                            django.core.validators.MaxValueValidator(600),
                        ],
                    ),
                ),
                (
                    "legend_font_size",
                    models.PositiveIntegerField(
                        default=12,
                        help_text="Default on-screen legend text size in pixels.",
                        validators=[
                            django.core.validators.MinValueValidator(8),
                            django.core.validators.MaxValueValidator(24),
                        ],
                    ),
                ),
                (
                    "export_dpi",
                    models.PositiveIntegerField(
                        default=300,
                        help_text="Resolution of exported PNG and SVG documents.",
                        validators=[
                            django.core.validators.MinValueValidator(72),
                            django.core.validators.MaxValueValidator(1200),
                        ],
                    ),
                ),
                (
                    "export_width_mm",
                    models.PositiveIntegerField(
                        default=160,
                        help_text="Width of the exported document in millimetres.",
                        validators=[
                            django.core.validators.MinValueValidator(50),
                            django.core.validators.MaxValueValidator(600),
                        ],
                    ),
                ),
                (
                    "export_height_mm",
                    models.PositiveIntegerField(
                        default=110,
                        help_text="Preferred height of the exported document in millimetres.",
                        validators=[
                            django.core.validators.MinValueValidator(50),
                            django.core.validators.MaxValueValidator(600),
                        ],
                    ),
                ),
                (
                    "export_max_height_mm",
                    models.PositiveIntegerField(
                        default=180,
                        help_text="Largest height the export layout may grow to.",
                        validators=[
                            django.core.validators.MinValueValidator(50),
                            django.core.validators.MaxValueValidator(600),
                        ],
                    ),
                ),
                (
                    "export_legend_font_size_pt",
                    models.FloatField(
                        default=11.0,
                        help_text="Legend text size in exports, in points.",
                        validators=[
                            django.core.validators.MinValueValidator(4),
                            django.core.validators.MaxValueValidator(48),
                        ],
                    ),
                ),
                (
                    "export_legend_font_family",
                    models.CharField(
                        default="'Calibri', 'Carlito', Arial, sans-serif",
                        help_text="Font stack used for legend text in exports.",
                        max_length=200,
                    ),
                ),
                (
                    "export_legend_width_fraction",
                    models.FloatField(
                        default=0.52,
                        help_text="Default maximum legend width in exports as a fraction of the page. The renderer fits the legend to its content and never exceeds this bound.",
                        validators=[
                            django.core.validators.MinValueValidator(0.2),
                            django.core.validators.MaxValueValidator(0.9),
                        ],
                    ),
                ),
                (
                    "export_file_name_prefix",
                    models.SlugField(
                        default="waste_atlas",
                        help_text="Prefix of every exported file name.",
                    ),
                ),
                (
                    "geometry_simplify_tolerance",
                    models.FloatField(
                        default=0.001,
                        help_text="Geometry simplification tolerance in degrees used when serving catchment geometries (0 disables simplification).",
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "change_boundary_changed_color",
                    models.CharField(
                        default="#ba68c8",
                        help_text="Change maps: territory reassigned to a different catchment.",
                        max_length=7,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Enter a hex color such as #e0e0e0.",
                                regex="^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
                            )
                        ],
                    ),
                ),
                (
                    "export_legend_item_flow",
                    models.CharField(
                        choices=[
                            ("column", "By column (fill one column, then the next)"),
                            ("row", "By row (fill across the columns)"),
                        ],
                        default="column",
                        help_text="Default arrangement of legend entries across the legend columns, in exports and on the map page.",
                        max_length=10,
                    ),
                ),
                (
                    "acpv_hatch_color",
                    models.CharField(
                        default="#1f2937",
                        help_text="Hatching that marks values aggregated over several catchments (ACPV).",
                        max_length=7,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Enter a hex color such as #e0e0e0.",
                                regex="^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
                            )
                        ],
                    ),
                ),
                (
                    "acpv_hatch_opacity",
                    models.FloatField(
                        default=0.9,
                        help_text="Opacity of the aggregated-value hatching, 0 to 1.",
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(1),
                        ],
                    ),
                ),
                (
                    "acpv_outline_color",
                    models.CharField(
                        default="#ffffff",
                        help_text="Outline around a group of catchments sharing an aggregated value.",
                        max_length=7,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Enter a hex color such as #e0e0e0.",
                                regex="^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
                            )
                        ],
                    ),
                ),
                (
                    "acpv_outline_opacity",
                    models.FloatField(
                        default=0.95,
                        help_text="Opacity of the aggregated-value group outline, 0 to 1.",
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(1),
                        ],
                    ),
                ),
                (
                    "acpv_outline_width",
                    models.FloatField(
                        default=1.35,
                        help_text="Width of the aggregated-value group outline, in pixels of the on-screen map; exports scale it with the page.",
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
            ],
            options={
                "verbose_name": "Waste Atlas rendering settings",
                "verbose_name_plural": "Waste Atlas rendering settings",
                "indexes": [],
                "constraints": [],
            },
        ),
    ]
