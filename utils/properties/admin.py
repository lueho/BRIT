from django.contrib import admin

from .models import Property, Unit


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "dimensionless",
        "reference_quantity",
        "owner",
        "publication_status",
    )
    search_fields = ("name",)
    list_filter = ("publication_status", "dimensionless")
    ordering = ("name",)


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ("name", "unit", "owner", "publication_status")
    search_fields = ("name",)
    list_filter = ("publication_status",)
    ordering = ("name",)
    filter_horizontal = ("allowed_units",)
