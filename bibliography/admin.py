from django.contrib import admin

from .models import Author, Licence, Source, SourceAuthor


class SourceAuthorInline(admin.TabularInline):
    model = SourceAuthor
    # formset = SourceAuthorFormSet
    fields = ("author", "position")
    readonly_fields = ("position",)
    extra = 1
    ordering = ("position",)


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ("last_names", "first_names", "owner", "publication_status")
    search_fields = ("last_names", "first_names", "middle_names")
    list_filter = ("publication_status",)
    ordering = ("last_names", "first_names")


@admin.register(Licence)
class LicenceAdmin(admin.ModelAdmin):
    list_display = ("name", "reference_url", "owner", "publication_status")
    search_fields = ("name",)
    list_filter = ("publication_status",)
    ordering = ("name",)


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    inlines = [SourceAuthorInline]
    list_display = (
        "abbreviation",
        "title",
        "year",
        "type",
        "owner",
        "publication_status",
    )
    search_fields = ("abbreviation", "title", "doi")
    list_filter = ("publication_status", "type")
    ordering = ("abbreviation",)
    autocomplete_fields = ("licence",)
