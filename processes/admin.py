from django.contrib import admin

from .models import MechanismCategory, ProcessGroup, ProcessType


@admin.register(ProcessGroup)
class ProcessGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "publication_status")
    search_fields = ("name", "description")
    list_filter = ("publication_status",)
    ordering = ("name",)


@admin.register(MechanismCategory)
class MechanismCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "publication_status")
    search_fields = ("name", "description")
    list_filter = ("publication_status",)
    ordering = ("name",)


@admin.register(ProcessType)
class ProcessTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "group", "mechanism", "owner", "publication_status")
    search_fields = ("name", "description", "short_description", "mechanism")
    list_filter = ("publication_status", "group", "mechanism_categories")
    ordering = ("name",)
    autocomplete_fields = ("group", "sources")
    filter_horizontal = ("input_materials", "output_materials", "mechanism_categories")
