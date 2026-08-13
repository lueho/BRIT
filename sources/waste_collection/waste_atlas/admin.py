from django import forms
from django.contrib import admin
from django.db import models

from .models import WasteAtlasMapConfiguration, WasteAtlasRenderingSettings


@admin.register(WasteAtlasMapConfiguration)
class WasteAtlasMapConfigurationAdmin(admin.ModelAdmin):
    list_display = ("key", "map_title", "updated_at")
    search_fields = ("key", "configuration__title")
    readonly_fields = ("updated_at",)
    ordering = ("key",)
    formfield_overrides = {
        models.JSONField: {
            "widget": forms.Textarea(
                attrs={"class": "vLargeTextField", "cols": 120, "rows": 32}
            )
        }
    }

    @admin.display(description="Title")
    def map_title(self, obj):
        return obj.configuration.get("title", "")


@admin.register(WasteAtlasRenderingSettings)
class WasteAtlasRenderingSettingsAdmin(admin.ModelAdmin):
    """Single row of atlas-wide rendering and export defaults."""

    readonly_fields = ("updated_at",)
    fieldsets = (
        (
            "Palette",
            {
                "fields": (
                    "no_data_color",
                    "no_collection_color",
                    "quartile_colors",
                )
            },
        ),
        (
            "Geometry outlines",
            {
                "fields": (
                    "country_fill_color",
                    "country_stroke_color",
                    "country_stroke_width",
                    "subdivision_stroke_color",
                    "subdivision_stroke_width",
                    "catchment_stroke_color",
                    "catchment_stroke_width",
                    "conflict_stroke_color",
                    "conflict_stroke_width",
                    "conflict_stroke_dasharray",
                    "geometry_simplify_tolerance",
                )
            },
        ),
        (
            "Aggregated values (ACPV)",
            {
                "description": (
                    "Appearance of the aggregated-value markers, shared by the "
                    "on-screen maps and the exports. A single map can override "
                    "any of these with the acpvHatchColor, acpvHatchOpacity, "
                    "acpvOutlineColor, acpvOutlineOpacity or acpvOutlineWidth "
                    "key in its configuration."
                ),
                "fields": (
                    "acpv_hatch_color",
                    "acpv_hatch_opacity",
                    "acpv_outline_color",
                    "acpv_outline_opacity",
                    "acpv_outline_width",
                ),
            },
        ),
        (
            "Change maps",
            {
                "fields": (
                    "change_no_change_color",
                    "change_changed_color",
                    "change_boundary_changed_color",
                    "change_new_color",
                    "change_removed_color",
                    "change_increase_color",
                    "change_decrease_color",
                )
            },
        ),
        (
            "Legend defaults",
            {"fields": ("legend_placement", "legend_width", "legend_font_size")},
        ),
        (
            "Export defaults",
            {
                "fields": (
                    "export_dpi",
                    "export_width_mm",
                    "export_height_mm",
                    "export_max_height_mm",
                    "export_legend_font_size_pt",
                    "export_legend_font_family",
                    "export_legend_width_fraction",
                    "export_legend_item_flow",
                    "export_file_name_prefix",
                )
            },
        ),
        (None, {"fields": ("updated_at",)}),
    )

    def has_add_permission(self, request):
        return not WasteAtlasRenderingSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
