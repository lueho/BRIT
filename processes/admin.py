from django.contrib import admin

from .models import (
    Process,
    ProcessCategory,
    ProcessInfoResource,
    ProcessLink,
    ProcessMaterial,
    ProcessOperatingParameter,
    ProcessReference,
)


class ProcessMaterialInline(admin.TabularInline):
    model = ProcessMaterial
    extra = 1


class ProcessOperatingParameterInline(admin.TabularInline):
    model = ProcessOperatingParameter
    extra = 1


class ProcessLinkInline(admin.TabularInline):
    model = ProcessLink
    extra = 1


class ProcessInfoResourceInline(admin.TabularInline):
    model = ProcessInfoResource
    extra = 1


class ProcessReferenceInline(admin.TabularInline):
    model = ProcessReference
    extra = 1


@admin.register(Process)
class ProcessAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "parent", "publication_status")
    list_filter = ("categories", "publication_status")
    search_fields = ("name", "short_description", "mechanism")
    inlines = [
        ProcessMaterialInline,
        ProcessOperatingParameterInline,
        ProcessLinkInline,
        ProcessInfoResourceInline,
        ProcessReferenceInline,
    ]
    filter_horizontal = ("categories",)


@admin.register(ProcessCategory)
class ProcessCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "publication_status")
    search_fields = ("name",)


@admin.register(ProcessMaterial)
class ProcessMaterialAdmin(admin.ModelAdmin):
    list_display = (
        "process",
        "material",
        "role",
        "stage",
        "stream_label",
        "quantity_value",
        "quantity_unit",
        "order",
        "optional",
    )
    list_filter = ("role", "optional")
    search_fields = ("process__name", "material__name")


@admin.register(ProcessOperatingParameter)
class ProcessOperatingParameterAdmin(admin.ModelAdmin):
    list_display = (
        "process",
        "parameter",
        "name",
        "value_min",
        "value_max",
        "nominal_value",
        "unit",
        "order",
    )
    list_filter = ("parameter",)
    search_fields = ("process__name", "name")


@admin.register(ProcessLink)
class ProcessLinkAdmin(admin.ModelAdmin):
    list_display = ("label", "process", "order", "open_in_new_tab")
    search_fields = ("label", "url", "process__name")


@admin.register(ProcessInfoResource)
class ProcessInfoResourceAdmin(admin.ModelAdmin):
    list_display = ("title", "process", "resource_type", "order")
    list_filter = ("resource_type",)
    search_fields = ("title", "description", "process__name")


@admin.register(ProcessReference)
class ProcessReferenceAdmin(admin.ModelAdmin):
    list_display = ("__str__", "process", "reference_type", "order")
    list_filter = ("reference_type",)
    search_fields = ("title", "source__title", "process__name")
