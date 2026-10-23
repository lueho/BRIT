from django.contrib import admin

from utils.object_management.admin import NamedUserCreatedObjectAdmin, PolicyAdminMixin

from .models import InputMaterial


@admin.register(InputMaterial)
class InputMaterialAdmin(PolicyAdminMixin, NamedUserCreatedObjectAdmin):
    list_display = ("name", "material", "series", "owner", "publication_status")
    search_fields = ("name", "material__name")
