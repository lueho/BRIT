from django.contrib import admin

from .models import Showcase


@admin.register(Showcase)
class ShowcaseAdmin(admin.ModelAdmin):
    list_display = ("name", "region", "owner", "publication_status")
    search_fields = ("name", "description")
    list_filter = ("publication_status",)
    ordering = ("name",)
