from django.contrib import admin, messages
from django.contrib.gis.admin import GISModelAdmin
from django.core.exceptions import ValidationError
from django.utils.html import format_html, format_html_join

from .models import (
    Attribute,
    Catchment,
    CatchmentRevision,
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


@admin.register(CatchmentRevision)
class CatchmentRevisionModelAdmin(GISModelAdmin):
    actions = ["submit_selected_for_review", "approve_selected"]
    list_display = [
        "name",
        "catchment",
        "effective_from",
        "effective_to",
        "change_reason",
        "publication_status",
    ]
    list_filter = ["publication_status", "change_reason"]
    search_fields = ["name", "catchment__name", "description"]
    autocomplete_fields = ["catchment", "members", "sources"]
    filter_horizontal = ["predecessors"]
    readonly_fields = [
        "geom_hash",
        "publication_status",
        "submitted_at",
        "approved_at",
        "approved_by",
    ]

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj is not None and obj.publication_status in obj.IMMUTABLE_STATUSES:
            readonly_fields.extend(
                field
                for field in (
                    "catchment",
                    "effective_from",
                    "effective_to",
                    "geom",
                    "members",
                )
                if field not in readonly_fields
            )
        return readonly_fields

    @admin.action(description="Submit selected revisions for review")
    def submit_selected_for_review(self, request, queryset):
        self._transition_selected(request, queryset, "submit_for_review")

    @admin.action(description="Approve selected revisions")
    def approve_selected(self, request, queryset):
        self._transition_selected(request, queryset, "approve", user=request.user)

    def _transition_selected(self, request, queryset, transition, **kwargs):
        completed = 0
        for revision in queryset.order_by("effective_from", "pk"):
            try:
                getattr(revision, transition)(**kwargs)
            except ValidationError as error:
                self.message_user(
                    request,
                    f"{revision}: {'; '.join(error.messages)}",
                    level=messages.ERROR,
                )
            else:
                completed += 1
        if completed:
            self.message_user(
                request,
                f"Updated {completed} catchment revision(s).",
                level=messages.SUCCESS,
            )


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
