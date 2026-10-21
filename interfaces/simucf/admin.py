from django.contrib import admin

from utils.object_management.admin import PolicyAdminMixin

from .models import InputMaterial


@admin.register(InputMaterial)
class InputMaterialAdmin(PolicyAdminMixin, admin.ModelAdmin):
    list_display = ("name", "material", "series", "owner", "publication_status")
    search_fields = ("name", "material__name")
    list_filter = ("publication_status",)
    ordering = ("name",)
