from django.contrib import admin

from .models import Redirect


@admin.register(Redirect)
class RedirectAdmin(admin.ModelAdmin):
    list_display = ("short_code", "full_path")
    search_fields = ("short_code", "full_path")
    ordering = ("short_code",)
