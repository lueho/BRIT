from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

HEX_COLOR_VALIDATOR = RegexValidator(
    regex=r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
    message="Enter a hex color such as #e0e0e0.",
)

LEGEND_PLACEMENTS = (
    ("bottom-left", "Bottom left"),
    ("bottom-right", "Bottom right"),
    ("top-left", "Top left"),
    ("top-right", "Top right"),
)


def _color_field(help_text, **kwargs):
    return models.CharField(
        max_length=7,
        validators=[HEX_COLOR_VALIDATOR],
        help_text=help_text,
        **kwargs,
    )


class WasteAtlasMapConfiguration(models.Model):
    """Client-side rendering configuration for a Waste Atlas map."""

    key = models.SlugField(
        max_length=100,
        unique=True,
        help_text="Stable key referenced by the Waste Atlas page registry.",
    )
    configuration = models.JSONField(
        default=dict,
        help_text="JSON object passed to the Waste Atlas choropleth renderer.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("key",)
        verbose_name = "Waste Atlas map configuration"
        verbose_name_plural = "Waste Atlas map configurations"

    def __str__(self):
        return self.key

    def clean(self):
        super().clean()
        if not isinstance(self.configuration, dict):
            raise ValidationError(
                {"configuration": "Map configuration must be a JSON object."}
            )


def default_quartile_colors():
    return ["#d9f0d3", "#a6d96a", "#66bd63", "#1a9850"]


class WasteAtlasRenderingSettings(models.Model):
    """Singleton holding the Waste Atlas defaults shared by every map.

    Per-map values live in :class:`WasteAtlasMapConfiguration`; everything that
    is global to the atlas (palette, legend defaults, export page geometry and
    file naming) is stored here so maintainers can change it without a code
    deployment.
    """

    SINGLETON_PK = 1

    no_data_color = _color_field(
        "Fill for regions without data.",
        default="#e0e0e0",
    )
    no_collection_color = _color_field(
        "Fill for regions without a separate collection.",
        default="#fff696",
    )
    country_fill_color = _color_field(
        "Base fill of the country layer.",
        default="#f0f0f0",
    )
    country_stroke_color = _color_field(
        "Outline color of the country border.",
        default="#000000",
    )
    country_stroke_width = models.FloatField(
        default=1.5,
        validators=[MinValueValidator(0)],
        help_text="Outline width of the country border in pixels.",
    )
    subdivision_stroke_color = _color_field(
        "Outline color of first-level subdivisions (e.g. Bundesländer).",
        default="#666666",
    )
    subdivision_stroke_width = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(0)],
        help_text="Outline width of first-level subdivisions in pixels.",
    )
    catchment_stroke_color = _color_field(
        "Outline color of catchments.",
        default="#232323",
    )
    catchment_stroke_width = models.FloatField(
        default=0.35,
        validators=[MinValueValidator(0)],
        help_text="Outline width of catchments in pixels.",
    )
    conflict_stroke_color = _color_field(
        "Outline color highlighting catchments with conflicting collections.",
        default="#d7263d",
    )
    conflict_stroke_width = models.FloatField(
        default=1.6,
        validators=[MinValueValidator(0)],
        help_text="Outline width of the conflict highlight in pixels.",
    )
    conflict_stroke_dasharray = models.CharField(
        max_length=32,
        default="3 2",
        help_text="SVG dash pattern of the conflict highlight.",
    )
    quartile_colors = models.JSONField(
        default=default_quartile_colors,
        help_text="Four hex colors used for quartile classification, low to high.",
    )
    change_no_change_color = _color_field(
        "Change maps: regions that did not change.",
        default="#c8e6c9",
    )
    change_changed_color = _color_field(
        "Change maps: regions whose category changed.",
        default="#ffb74d",
    )
    change_new_color = _color_field(
        "Change maps: regions with data only in the later year.",
        default="#64b5f6",
    )
    change_removed_color = _color_field(
        "Change maps: regions with data only in the earlier year.",
        default="#bdbdbd",
    )
    change_increase_color = _color_field(
        "Change maps: numeric increase.",
        default="#1a9850",
    )
    change_decrease_color = _color_field(
        "Change maps: numeric decrease.",
        default="#d73027",
    )
    legend_placement = models.CharField(
        max_length=20,
        choices=LEGEND_PLACEMENTS,
        default="bottom-left",
        help_text="Default on-screen legend placement.",
    )
    legend_width = models.PositiveIntegerField(
        default=300,
        validators=[MinValueValidator(180), MaxValueValidator(600)],
        help_text="Default on-screen legend width in pixels.",
    )
    legend_font_size = models.PositiveIntegerField(
        default=12,
        validators=[MinValueValidator(8), MaxValueValidator(24)],
        help_text="Default on-screen legend text size in pixels.",
    )
    export_dpi = models.PositiveIntegerField(
        default=300,
        validators=[MinValueValidator(72), MaxValueValidator(1200)],
        help_text="Resolution of exported PNG and SVG documents.",
    )
    export_width_mm = models.PositiveIntegerField(
        default=160,
        validators=[MinValueValidator(50), MaxValueValidator(600)],
        help_text="Width of the exported document in millimetres.",
    )
    export_height_mm = models.PositiveIntegerField(
        default=110,
        validators=[MinValueValidator(50), MaxValueValidator(600)],
        help_text="Preferred height of the exported document in millimetres.",
    )
    export_max_height_mm = models.PositiveIntegerField(
        default=180,
        validators=[MinValueValidator(50), MaxValueValidator(600)],
        help_text="Largest height the export layout may grow to.",
    )
    export_legend_font_size_pt = models.FloatField(
        default=11.0,
        validators=[MinValueValidator(4), MaxValueValidator(48)],
        help_text="Legend text size in exports, in points.",
    )
    export_legend_font_family = models.CharField(
        max_length=200,
        default="'Calibri', 'Carlito', Arial, sans-serif",
        help_text="Font stack used for legend text in exports.",
    )
    export_legend_width_fraction = models.FloatField(
        default=0.52,
        validators=[MinValueValidator(0.2), MaxValueValidator(0.9)],
        help_text="Default legend width in exports as a fraction of the page.",
    )
    export_legend_columns = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(4)],
        help_text="Default number of legend columns in exports.",
    )
    export_legend_bottom_columns = models.PositiveIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(6)],
        help_text="Legend columns used when the legend sits below the map.",
    )
    export_file_name_prefix = models.SlugField(
        max_length=50,
        default="waste_atlas",
        help_text="Prefix of every exported file name.",
    )
    geometry_simplify_tolerance = models.FloatField(
        default=0.001,
        validators=[MinValueValidator(0)],
        help_text=(
            "Geometry simplification tolerance in degrees used when serving "
            "catchment geometries (0 disables simplification)."
        ),
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Waste Atlas rendering settings"
        verbose_name_plural = "Waste Atlas rendering settings"

    def __str__(self):
        return "Waste Atlas rendering settings"

    def save(self, *args, **kwargs):
        self.pk = self.SINGLETON_PK
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("The Waste Atlas rendering settings cannot be deleted.")

    @classmethod
    def load(cls):
        """Return the settings row, creating it with the defaults if missing."""
        settings, _created = cls.objects.get_or_create(pk=cls.SINGLETON_PK)
        return settings

    def clean(self):
        super().clean()
        colors = self.quartile_colors
        if not isinstance(colors, list) or len(colors) != 4:
            raise ValidationError(
                {"quartile_colors": "Provide exactly four quartile colors."}
            )
        for color in colors:
            HEX_COLOR_VALIDATOR(str(color))
        if self.export_max_height_mm < self.export_height_mm:
            raise ValidationError(
                {
                    "export_max_height_mm": (
                        "The maximum height must not be smaller than the "
                        "preferred height."
                    )
                }
            )

    def client_defaults(self):
        """Return the defaults in the shape the choropleth renderer expects."""
        return {
            "noDataColor": self.no_data_color,
            "noCollectionColor": self.no_collection_color,
            "countryFill": self.country_fill_color,
            "countryStroke": self.country_stroke_color,
            "countryStrokeWidth": self.country_stroke_width,
            "subdivisionStroke": self.subdivision_stroke_color,
            "subdivisionStrokeWidth": self.subdivision_stroke_width,
            "catchmentStroke": self.catchment_stroke_color,
            "catchmentStrokeWidth": self.catchment_stroke_width,
            "conflictStroke": self.conflict_stroke_color,
            "conflictStrokeWidth": self.conflict_stroke_width,
            "conflictStrokeDasharray": self.conflict_stroke_dasharray,
            "quartileColors": list(self.quartile_colors),
            "exportFileNamePrefix": self.export_file_name_prefix,
            "changeColors": {
                "noChange": self.change_no_change_color,
                "changed": self.change_changed_color,
                "new": self.change_new_color,
                "removed": self.change_removed_color,
                "increase": self.change_increase_color,
                "decrease": self.change_decrease_color,
            },
            "legend": {
                "placement": self.legend_placement,
                "width": self.legend_width,
                "fontSize": self.legend_font_size,
            },
            "export": {
                "dpi": self.export_dpi,
                "widthMm": self.export_width_mm,
                "heightMm": self.export_height_mm,
                "maxHeightMm": self.export_max_height_mm,
                "legendFontSizePt": self.export_legend_font_size_pt,
                "legendFontFamily": self.export_legend_font_family,
                "legendWidth": self.export_legend_width_fraction,
                "legendColumns": self.export_legend_columns,
                "legendBottomColumns": self.export_legend_bottom_columns,
            },
        }
