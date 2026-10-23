import math

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from utils.object_management.admin import NamedUserCreatedObjectAdmin

from .models import (
    InventoryAlgorithm,
    InventoryAlgorithmParameter,
    InventoryAlgorithmParameterValue,
    InventoryAmountShare,
    RunningTask,
    Scenario,
    ScenarioInventoryConfiguration,
    ScenarioStatus,
)


@admin.register(InventoryAlgorithm)
class InventoryAlgorithmAdmin(admin.ModelAdmin):
    list_display = ("name", "geodataset_link", "default", "description")
    search_fields = ("name", "description", "function_name")
    list_filter = ("default",)
    ordering = ("name",)

    @staticmethod
    def geodataset_link(obj):
        url = reverse("admin:inventories_geodataset_change", args=(obj.geodataset.id,))
        return format_html("<a href='{}'>{}</a>", url, obj.geodataset.name)


@admin.register(InventoryAlgorithmParameter)
class InventoryAlgorithmParameterAdmin(admin.ModelAdmin):
    list_display = (
        "descriptive_name",
        "short_name",
        "unit",
        "is_required",
        "description",
    )
    search_fields = ("descriptive_name", "short_name", "description")
    list_filter = ("is_required",)
    ordering = ("descriptive_name",)


@admin.register(InventoryAlgorithmParameterValue)
class InventoryAlgorithmParameterValueAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "parameter",
        "value",
        "standard_deviation",
        "default",
        "is_custom",
        "source",
    )
    search_fields = ("name", "source")
    list_filter = ("default", "is_custom")
    ordering = ("parameter", "name")

    def get_search_results(self, request, queryset, search_term):
        """Also match the numeric value, which custom values display instead of a name."""
        results, may_have_duplicates = super().get_search_results(
            request, queryset, search_term
        )
        try:
            number = float(search_term.strip())
        except ValueError:
            return results, may_have_duplicates
        if not math.isfinite(number):
            return results, may_have_duplicates
        return results | queryset.filter(value=number), may_have_duplicates


@admin.register(ScenarioInventoryConfiguration)
class ScenarioInventoryConfigurationAdmin(admin.ModelAdmin):
    list_display = (
        "scenario",
        "feedstock_link",
        "geodataset_link",
        "inventory_algorithm_link",
        "parameter",
        "value",
    )
    ordering = ("scenario",)
    autocomplete_fields = (
        "scenario",
        "feedstock",
        "sample_series",
        "geodataset",
        "inventory_algorithm",
        "inventory_parameter",
        "inventory_value",
    )

    @staticmethod
    def feedstock_link(obj):
        if not obj.feedstock:
            return "-"
        url = reverse("admin:materials_material_change", args=(obj.feedstock.id,))
        return format_html("<a href='{}'>{}</a>", url, obj.feedstock.name)

    @staticmethod
    def geodataset_link(obj):
        url = reverse("admin:maps_geodataset_change", args=(obj.geodataset.id,))
        return format_html("<a href='{}'>{}</a>", url, obj.geodataset.name)

    @staticmethod
    def inventory_algorithm_link(obj):
        url = reverse(
            "admin:inventories_inventoryalgorithm_change",
            args=(obj.inventory_algorithm.id,),
        )
        return format_html("<a href='{}'>{}</a>", url, obj.inventory_algorithm.name)

    @staticmethod
    def parameter(obj):
        if not obj.inventory_parameter:
            return "-"
        url = reverse(
            "admin:inventories_inventoryalgorithmparameter_change",
            args=(obj.inventory_parameter.id,),
        )
        return format_html(
            "<a href='{}'>{}</a>", url, obj.inventory_parameter.descriptive_name
        )

    @staticmethod
    def value(obj):
        if not obj.inventory_value:
            return "-"
        url = reverse(
            "admin:inventories_inventoryalgorithmparametervalue_change",
            args=(obj.inventory_value.id,),
        )
        return format_html("<a href='{}'>{}</a>", url, obj.inventory_value.name)


@admin.register(Scenario)
class ScenarioAdmin(NamedUserCreatedObjectAdmin):
    list_display = (
        "name",
        "region_link",
        "catchment_link",
        "showcase_link",
        "description",
        "status",
        "owner",
        "publication_status",
    )
    search_fields = ("name", "description")
    autocomplete_fields = ("showcase",)

    @staticmethod
    def region_link(obj):
        if not obj.region:
            return "-"
        url = reverse("admin:maps_region_change", args=(obj.region.id,))
        return format_html("<a href='{}'>{}</a>", url, obj.region.name)

    @staticmethod
    def catchment_link(obj):
        if not obj.catchment:
            return "-"
        url = reverse("admin:maps_catchment_change", args=(obj.catchment.id,))
        return format_html("<a href='{}'>{}</a>", url, obj.catchment.name)

    @staticmethod
    def showcase_link(obj):
        if not obj.showcase:
            return "-"
        url = reverse("admin:closecycle_showcase_change", args=(obj.showcase.id,))
        return format_html("<a href='{}'>{}</a>", url, obj.showcase.name)

    @staticmethod
    def status(obj):
        return obj.status


@admin.register(ScenarioStatus)
class ScenarioStatusAdmin(admin.ModelAdmin):
    list_display = ("scenario", "status")
    list_filter = ("status",)
    ordering = ("scenario",)


@admin.register(InventoryAmountShare)
class InventoryAmountShareAdmin(admin.ModelAdmin):
    list_display = (
        "scenario",
        "feedstock",
        "timestep",
        "average",
        "standard_deviation",
        "owner",
    )
    ordering = ("scenario", "feedstock", "timestep")


@admin.register(RunningTask)
class RunningTaskAdmin(admin.ModelAdmin):
    list_display = ("scenario", "algorithm", "uuid")
    ordering = ("scenario",)
