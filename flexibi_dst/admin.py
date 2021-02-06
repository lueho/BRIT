from django.contrib import admin
from django.contrib.admin import ModelAdmin

from .models import LiteratureSource, Timestep, TemporalDistribution


@admin.register(LiteratureSource)
class LiteratureSourceAdmin(ModelAdmin):
    list_display = ('authors', 'title', 'abbreviation',)


admin.site.register(TemporalDistribution)
admin.site.register(Timestep)
