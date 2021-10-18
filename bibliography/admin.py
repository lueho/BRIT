from django.contrib import admin

from .models import Source, Licence


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ('owner', 'authors', 'title', 'abbreviation', 'abstract')


admin.site.register(Licence)
