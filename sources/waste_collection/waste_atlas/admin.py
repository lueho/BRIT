from django import forms
from django.contrib import admin
from django.db import models

from .models import WasteAtlasMapConfiguration


@admin.register(WasteAtlasMapConfiguration)
class WasteAtlasMapConfigurationAdmin(admin.ModelAdmin):
    list_display = ("key", "map_title", "updated_at")
    search_fields = ("key", "configuration__title")
    readonly_fields = ("updated_at",)
    ordering = ("key",)
    formfield_overrides = {
        models.JSONField: {
            "widget": forms.Textarea(
                attrs={"class": "vLargeTextField", "cols": 120, "rows": 32}
            )
        }
    }

    @admin.display(description="Title")
    def map_title(self, obj):
        return obj.configuration.get("title", "")
