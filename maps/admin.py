from django.contrib import admin
from django.utils.html import format_html, format_html_join

from .models import (
    Attribute,
    Catchment,
    CategoricalAttribute,
    GeoDataset,
    GeoDatasetColumnPolicy,
    GeoDatasetRuntimeConfiguration,
    Location,
    MapConfiguration,
    MapLayerConfiguration,
    MapLayerStyle,
    ModelMapConfiguration,
    Region,
    RegionAttributeTextValue,
    RegionAttributeValue,
    RegionProperty,
)
from .runtime_adapters import get_dataset_runtime_adapter


class GeoDatasetRuntimeConfigurationInline(admin.StackedInline):
    model = GeoDatasetRuntimeConfiguration
    extra = 0
    max_num = 1


class GeoDatasetColumnPolicyInline(admin.TabularInline):
    model = GeoDatasetColumnPolicy
    extra = 0


@admin.register(Attribute)
class AttributeModelAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(RegionProperty)
class RegionPropertyModelAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(CategoricalAttribute)
class CategoricalAttributeModelAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(Catchment)
class CatchmentModelAdmin(admin.ModelAdmin):
    autocomplete_fields = ["region", "parent_region", "parent"]
    search_fields = ["name"]


@admin.register(GeoDataset)
class GeoDatasetModelAdmin(admin.ModelAdmin):
    autocomplete_fields = ["region"]
    list_display = ["name", "model_name", "region"]
    readonly_fields = ["relation_column_review"]
    search_fields = ["name", "model_name", "region__name"]
    inlines = [GeoDatasetRuntimeConfigurationInline, GeoDatasetColumnPolicyInline]

    @admin.display(description="Local relation column review")
    def relation_column_review(self, obj):
        if not obj or not obj.pk:
            return "-"
        runtime_configuration = obj.get_runtime_configuration()
        if (
            not runtime_configuration
            or runtime_configuration.backend_type != "local_relation"
        ):
            return "Only available for local relation datasets."
        try:
            columns = get_dataset_runtime_adapter(obj).get_relation_columns()
        except Exception as exc:
            return format_html("Introspection failed: {}", exc)
        if not columns:
            return "No columns found."
        return format_html(
            "<table><thead><tr><th>Column</th><th>Type</th><th>Flags</th></tr></thead>"
            "<tbody>{}</tbody></table>",
            format_html_join(
                "",
                "<tr><td>{}</td><td>{}</td><td>{}</td></tr>",
                (
                    (
                        column["name"],
                        column["data_type"],
                        ", ".join(
                            flag
                            for flag, enabled in [
                                ("primary key", column["is_primary_key"]),
                                ("geometry", column["is_geometry"]),
                                ("label", column["is_label"]),
                                ("configured", column["is_configured"]),
                                ("visible", column["is_visible"]),
                                ("filterable", column["is_filterable"]),
                                ("searchable", column["is_searchable"]),
                                ("exportable", column["is_exportable"]),
                            ]
                            if enabled
                        )
                        or "-",
                    )
                    for column in columns
                ),
            ),
        )


@admin.register(GeoDatasetRuntimeConfiguration)
class GeoDatasetRuntimeConfigurationAdmin(admin.ModelAdmin):
    autocomplete_fields = ["dataset"]
    list_display = [
        "dataset",
        "backend_type",
        "runtime_model_name",
        "schema_name",
        "relation_name",
    ]
    search_fields = [
        "dataset__name",
        "runtime_model_name",
        "schema_name",
        "relation_name",
    ]


@admin.register(GeoDatasetColumnPolicy)
class GeoDatasetColumnPolicyAdmin(admin.ModelAdmin):
    autocomplete_fields = ["dataset"]
    list_display = [
        "dataset",
        "column_name",
        "is_visible",
        "is_filterable",
        "is_searchable",
        "is_exportable",
    ]
    search_fields = ["dataset__name", "column_name", "display_label"]


@admin.register(Location)
class LocationModelAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(MapLayerStyle)
class LayerStyleModelAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(MapLayerConfiguration)
class LayerModelAdmin(admin.ModelAdmin):
    autocomplete_fields = ["style"]
    search_fields = ["name"]


@admin.register(MapConfiguration)
class MapConfigurationModelAdmin(admin.ModelAdmin):
    autocomplete_fields = ["layers"]
    search_fields = ["name"]


@admin.register(ModelMapConfiguration)
class ModelMapConfigurationModelAdmin(admin.ModelAdmin):
    autocomplete_fields = ["map_config"]  # TODO autocomplete for model_name


@admin.register(Region)
class RegionModelAdmin(admin.ModelAdmin):
    autocomplete_fields = ["composed_of"]
    raw_id_fields = ["borders"]
    search_fields = ["name"]


@admin.register(RegionAttributeValue)
class RegionAttributeValueModelAdmin(admin.ModelAdmin):
    autocomplete_fields = ["region", "property", "unit"]


@admin.register(RegionAttributeTextValue)
class RegionAttributeTextValueModelAdmin(admin.ModelAdmin):
    autocomplete_fields = ["region", "categorical_attribute"]
