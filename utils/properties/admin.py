from django.contrib import admin

from utils.object_management.admin import NamedUserCreatedObjectAdmin, PolicyAdminMixin

from .models import Property, Unit


@admin.register(Unit)
class UnitAdmin(PolicyAdminMixin, NamedUserCreatedObjectAdmin):
    list_display = (
        "name",
        "dimensionless",
        "reference_quantity",
        "owner",
        "publication_status",
    )
    list_filter = ("publication_status", "dimensionless")


@admin.register(Property)
class PropertyAdmin(PolicyAdminMixin, NamedUserCreatedObjectAdmin):
    filter_horizontal = ("allowed_units",)
