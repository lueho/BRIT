from django.contrib import admin

from .models import (
    Culture,
    Greenhouse,
    GreenhouseGrowthCycle,
    GrowthShare,
    GrowthTimeStepSet,
)


@admin.register(Greenhouse)
class GreenhouseAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "heated",
        "lighted",
        "high_wire",
        "above_ground",
        "owner",
        "publication_status",
    )
    search_fields = ("name", "description")
    list_filter = (
        "publication_status",
        "heated",
        "lighted",
        "high_wire",
        "above_ground",
    )
    ordering = ("name",)


@admin.register(Culture)
class CultureAdmin(admin.ModelAdmin):
    list_display = ("name", "residue", "owner", "publication_status")
    search_fields = ("name",)
    list_filter = ("publication_status",)
    ordering = ("name",)


@admin.register(GreenhouseGrowthCycle)
class GreenhouseGrowthCycleAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "cycle_number",
        "culture",
        "greenhouse",
        "owner",
        "publication_status",
    )
    list_filter = ("publication_status",)
    ordering = ("greenhouse", "cycle_number")


@admin.register(GrowthTimeStepSet)
class GrowthTimeStepSetAdmin(admin.ModelAdmin):
    list_display = ("__str__", "timestep", "growth_cycle", "owner")
    ordering = ("growth_cycle", "timestep")


@admin.register(GrowthShare)
class GrowthShareAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "component",
        "timestepset",
        "average",
        "standard_deviation",
        "owner",
    )
    search_fields = ("component__name",)
    ordering = ("timestepset", "component")
