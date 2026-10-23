from django.contrib import admin

from utils.object_management.admin import NamedUserCreatedObjectAdmin, PolicyAdminMixin

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
    SampleAuthor,
    SampleGroup,
    SampleSeries,
)


class SampleAuthorInline(admin.TabularInline):
    model = SampleAuthor
    extra = 1
    autocomplete_fields = ("author",)


@admin.register(AnalyticalMethod)
class AnalyticalMethodAdmin(PolicyAdminMixin, admin.ModelAdmin):
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
class MaterialAdmin(PolicyAdminMixin, NamedUserCreatedObjectAdmin):
    list_display = ("name", "abbreviation", "owner", "publication_status")
    search_fields = ("name", "abbreviation", "description")


@admin.register(MaterialComponent)
class MaterialComponentAdmin(PolicyAdminMixin, NamedUserCreatedObjectAdmin):
    list_display = (
        "name",
        "abbreviation",
        "comparable_component",
        "is_aggregate",
        "owner",
        "publication_status",
    )
    search_fields = ("name", "abbreviation", "description")
    list_filter = ("publication_status", "is_aggregate")


@admin.register(MaterialComponentGroup)
class MaterialComponentGroupAdmin(PolicyAdminMixin, NamedUserCreatedObjectAdmin):
    pass


@admin.register(MaterialProperty)
class MaterialPropertyAdmin(PolicyAdminMixin, NamedUserCreatedObjectAdmin):
    list_display = (
        "name",
        "abbreviation",
        "comparable_property",
        "group",
        "aggregation_kind",
        "owner",
        "publication_status",
    )
    search_fields = ("name", "abbreviation")
    list_filter = ("publication_status", "aggregation_kind", "group")
    filter_horizontal = ("allowed_units",)


@admin.register(MaterialPropertyGroup)
class MaterialPropertyGroupAdmin(PolicyAdminMixin, NamedUserCreatedObjectAdmin):
    pass


@admin.register(MaterialPropertyValue)
class MaterialPropertyValueAdmin(PolicyAdminMixin, admin.ModelAdmin):
    list_display = (
        "__str__",
        "property",
        "basis_component",
        "average",
        "standard_deviation",
        "owner",
        "publication_status",
    )
    search_fields = ("property__name", "basis_component__name")
    list_filter = ("publication_status",)
    ordering = ("property__name",)
    autocomplete_fields = ("sources",)


@admin.register(SampleSeries)
class SampleSeriesAdmin(PolicyAdminMixin, NamedUserCreatedObjectAdmin):
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


@admin.register(SampleGroup)
class SampleGroupAdmin(PolicyAdminMixin, NamedUserCreatedObjectAdmin):
    list_display = ("name", "kind", "owner", "publication_status")
    search_fields = ("name", "description", "sources__title")
    list_filter = ("kind", "publication_status")
    autocomplete_fields = ("sources",)


@admin.register(Sample)
class SampleAdmin(PolicyAdminMixin, NamedUserCreatedObjectAdmin):
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
    list_filter = ("publication_status", "standalone", "sample_groups")
    autocomplete_fields = ("sources",)
    filter_horizontal = ("sample_groups",)
    inlines = (SampleAuthorInline,)


@admin.register(Composition)
class CompositionAdmin(PolicyAdminMixin, admin.ModelAdmin):
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


@admin.register(ComponentMeasurement)
class ComponentMeasurementAdmin(PolicyAdminMixin, admin.ModelAdmin):
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
