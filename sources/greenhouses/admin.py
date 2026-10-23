from django.contrib import admin

from sources.greenhouses.models import (
    Culture,
    Greenhouse,
    GreenhouseGrowthCycle,
    GrowthShare,
    GrowthTimeStepSet,
)
from utils.object_management.admin import NamedUserCreatedObjectAdmin, PolicyAdminMixin


@admin.register(Greenhouse)
class GreenhouseAdmin(PolicyAdminMixin, NamedUserCreatedObjectAdmin):
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


@admin.register(Culture)
class CultureAdmin(PolicyAdminMixin, NamedUserCreatedObjectAdmin):
    list_display = ("name", "residue", "owner", "publication_status")


@admin.register(GreenhouseGrowthCycle)
class GreenhouseGrowthCycleAdmin(PolicyAdminMixin, admin.ModelAdmin):
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
class GrowthTimeStepSetAdmin(PolicyAdminMixin, admin.ModelAdmin):
    list_display = ("__str__", "timestep", "growth_cycle", "owner")
    ordering = ("growth_cycle", "timestep")


@admin.register(GrowthShare)
class GrowthShareAdmin(PolicyAdminMixin, admin.ModelAdmin):
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


__all__ = [
    "CultureAdmin",
    "GreenhouseAdmin",
    "GreenhouseGrowthCycleAdmin",
    "GrowthShareAdmin",
    "GrowthTimeStepSetAdmin",
]
