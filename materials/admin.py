from django.contrib import admin

from .models import (
    AnalyticalMethod,
    ComponentMeasurement,
    Composition,
    Material,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialProperty,
    MaterialPropertyGroup,
    MaterialPropertyValue,
    Sample,
    SampleSeries,
    WeightShare,
)


@admin.register(AnalyticalMethod)
class AnalyticalMethodAdmin(admin.ModelAdmin):
    """
    Admin interface for the AnalyticalMethod model with autocomplete for sources.
    """

    list_display = ("name", "ontology_uri", "technique", "standard", "display_sources")
    search_fields = (
        "name",
        "description",
        "ontology_uri",
        "technique",
        "standard",
        "instrument_type",
        "sources__title",
    )
    fieldsets = (
        (None, {"fields": ("name", "description")}),
        ("External Ontology", {"fields": ("ontology_uri",)}),
        (
            "Method Details",
            {
                "fields": (
                    "technique",
                    "standard",
                    "instrument_type",
                    "lower_detection_limit",
                )
            },
        ),
        ("Sources", {"fields": ("sources",)}),
    )
    ordering = ("name",)
    exclude = ("created_by_id", "updated_by_id", "created_at", "updated_at")
    autocomplete_fields = ("sources",)  # Enable autocomplete for the 'sources' field

    def display_sources(self, obj):
        return ", ".join([source.title for source in obj.sources.all()])

    display_sources.short_description = "Sources"


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("name", "abbreviation", "owner", "publication_status")
    search_fields = ("name", "abbreviation", "description")
    list_filter = ("publication_status",)
    ordering = ("name",)


@admin.register(MaterialComponent)
class MaterialComponentAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "abbreviation",
        "component_kind",
        "owner",
        "publication_status",
    )
    search_fields = ("name", "abbreviation", "description")
    list_filter = ("publication_status", "component_kind")
    ordering = ("name",)


@admin.register(MaterialComponentGroup)
class MaterialComponentGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "publication_status")
    search_fields = ("name",)
    list_filter = ("publication_status",)
    ordering = ("name",)


@admin.register(MaterialProperty)
class MaterialPropertyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "unit",
        "abbreviation",
        "group",
        "aggregation_kind",
        "owner",
        "publication_status",
    )
    search_fields = ("name", "abbreviation")
    list_filter = ("publication_status", "aggregation_kind", "group")
    ordering = ("name",)
    filter_horizontal = ("allowed_units",)


@admin.register(MaterialPropertyGroup)
class MaterialPropertyGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "publication_status")
    search_fields = ("name",)
    list_filter = ("publication_status",)
    ordering = ("name",)


@admin.register(MaterialPropertyValue)
class MaterialPropertyValueAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "property",
        "average",
        "standard_deviation",
        "owner",
        "publication_status",
    )
    search_fields = ("property__name",)
    list_filter = ("publication_status",)
    ordering = ("property__name",)
    autocomplete_fields = ("sources",)


@admin.register(SampleSeries)
class SampleSeriesAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "material",
        "publish",
        "standard",
        "owner",
        "publication_status",
    )
    search_fields = ("name", "material__name")
    list_filter = ("publication_status", "publish", "standard")
    ordering = ("name",)


@admin.register(Sample)
class SampleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "material",
        "series",
        "timestep",
        "standalone",
        "owner",
        "publication_status",
    )
    search_fields = ("name", "material__name", "location")
    list_filter = ("publication_status", "standalone")
    ordering = ("name",)
    autocomplete_fields = ("sources",)


@admin.register(Composition)
class CompositionAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "sample",
        "group",
        "fractions_of",
        "order",
        "owner",
        "publication_status",
    )
    search_fields = ("sample__name", "group__name")
    list_filter = ("publication_status",)
    ordering = ("sample", "order")


@admin.register(WeightShare)
class WeightShareAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "component",
        "composition",
        "average",
        "standard_deviation",
        "owner",
    )
    search_fields = ("component__name",)
    ordering = ("-average",)


@admin.register(ComponentMeasurement)
class ComponentMeasurementAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "sample",
        "group",
        "component",
        "average",
        "unit",
        "owner",
    )
    search_fields = ("component__name", "sample__name")
    list_filter = ("group",)
    ordering = ("component__name",)
    autocomplete_fields = ("sources",)
