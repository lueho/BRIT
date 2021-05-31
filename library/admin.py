from django.contrib import admin

from .models import LiteratureSource


@admin.register(LiteratureSource)
class LiteratureSourceAdmin(admin.ModelAdmin):
    list_display = ('owner', 'authors', 'title', 'abbreviation', 'abstract')
