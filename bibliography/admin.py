from django.contrib import admin

from .forms import SourceAuthorFormSet
from .models import Author, Licence, Source, SourceAuthor


class SourceAuthorInline(admin.TabularInline):
    model = SourceAuthor
    formset = SourceAuthorFormSet
    fields = ('author', 'position')
    readonly_fields = ('position',)
    extra = 1
    ordering = ('position',)


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    inlines = [SourceAuthorInline]
    list_display = ('abbreviation', 'title', 'year')


admin.site.register(Author)
admin.site.register(Licence)
