from django.contrib import admin

from utils.object_management.admin import NamedUserCreatedObjectAdmin

from .models import Period, TemporalDistribution, Timestep


@admin.register(TemporalDistribution)
class TemporalDistributionAdmin(NamedUserCreatedObjectAdmin):
    pass


@admin.register(Timestep)
class TimestepAdmin(NamedUserCreatedObjectAdmin):
    list_display = ("name", "distribution", "order", "owner", "publication_status")
    list_filter = ("publication_status", "distribution")
    ordering = ("distribution", "order")
    autocomplete_fields = ("distribution",)


@admin.register(Period)
class PeriodAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "distribution",
        "first_timestep",
        "last_timestep",
        "owner",
        "publication_status",
    )
    list_filter = ("publication_status", "distribution")
    ordering = ("distribution", "first_timestep")
