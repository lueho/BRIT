from django.contrib import admin

from utils.object_management.admin import (
    NamedUserCreatedObjectAdmin,
    PolicyAdminMixin,
    PolicyOwnedInlineMixin,
)

from .models import Author, Licence, Source, SourceAuthor


class SourceAuthorInline(PolicyOwnedInlineMixin, admin.TabularInline):
    model = SourceAuthor
    # formset = SourceAuthorFormSet
    fields = ("author", "position")
    extra = 1
    ordering = ("position",)


@admin.register(Author)
class AuthorAdmin(PolicyAdminMixin, admin.ModelAdmin):
    list_display = (
        "author_type",
        "last_names",
        "first_names",
        "organization_name",
        "institution",
        "contact_email",
        "owner",
        "publication_status",
    )
    search_fields = (
        "last_names",
        "first_names",
        "middle_names",
        "organization_name",
        "organization_abbreviation",
        "institution",
        "contact_email",
    )
    list_filter = ("publication_status",)
    ordering = ("last_names", "first_names")


@admin.register(Licence)
class LicenceAdmin(PolicyAdminMixin, NamedUserCreatedObjectAdmin):
    list_display = ("name", "reference_url", "owner", "publication_status")


@admin.register(Source)
class SourceAdmin(PolicyAdminMixin, admin.ModelAdmin):
    inlines = SourceAuthorInline
    list_display = (
        "citation_key",
        "title",
        "year",
        "type",
        "owner",
        "publication_status",
    )
    search_fields = ("citation_key", "title", "doi")
    list_filter = ("publication_status", "type")
    ordering = ("citation_key",)
    autocomplete_fields = ("licence",)
