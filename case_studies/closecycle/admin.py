from django.contrib import admin

from utils.object_management.admin import PolicyAdminMixin, PolicyOwnedInlineMixin

from .models import Showcase, ShowcaseMaterial, ShowcaseProcess


class ShowcaseMaterialInline(PolicyOwnedInlineMixin, admin.TabularInline):
    model = ShowcaseMaterial
    extra = 0
    autocomplete_fields = ("material",)


class ShowcaseProcessInline(PolicyOwnedInlineMixin, admin.TabularInline):
    model = ShowcaseProcess
    extra = 0
    autocomplete_fields = ("process",)


@admin.register(Showcase)
class ShowcaseAdmin(PolicyAdminMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "theme",
        "region",
        "catchment",
        "owner",
        "publication_status",
    )
    search_fields = ("name", "description")
    list_filter = ("publication_status", "theme", "catchment")
    ordering = ("name",)
    autocomplete_fields = ("catchment", "samples", "sample_series")
    inlines = (ShowcaseMaterialInline, ShowcaseProcessInline)
