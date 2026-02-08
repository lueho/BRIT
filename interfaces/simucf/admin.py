from django.contrib import admin

from .models import InputMaterial


@admin.register(InputMaterial)
class InputMaterialAdmin(admin.ModelAdmin):
    list_display = ("name", "material", "series", "owner", "publication_status")
    search_fields = ("name", "material__name")
    list_filter = ("publication_status",)
    ordering = ("name",)
