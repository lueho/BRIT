from django.contrib import admin

from utils.object_management.admin import PolicyAdminMixin

from .models import Property, Unit


@admin.register(Unit)
class UnitAdmin(PolicyAdminMixin, admin.ModelAdmin):
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
class PropertyAdmin(PolicyAdminMixin, admin.ModelAdmin):
    list_display = ("name", "owner", "publication_status")
    search_fields = ("name",)
    list_filter = ("publication_status",)
    ordering = ("name",)
    filter_horizontal = ("allowed_units",)
