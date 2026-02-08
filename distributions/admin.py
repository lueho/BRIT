from django.contrib import admin

from .models import Period, TemporalDistribution, Timestep


@admin.register(TemporalDistribution)
class TemporalDistributionAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "publication_status")
    search_fields = ("name",)
    list_filter = ("publication_status",)
    ordering = ("name",)


@admin.register(Timestep)
class TimestepAdmin(admin.ModelAdmin):
    list_display = ("name", "distribution", "order", "owner", "publication_status")
    search_fields = ("name",)
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
