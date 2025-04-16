from django.contrib import admin

from . import models
from .models import AnalyticalMethod


@admin.register(AnalyticalMethod)
class AnalyticalMethodAdmin(admin.ModelAdmin):
    """
    Admin interface for the AnalyticalMethod model with autocomplete for sources.
    """
    list_display = ('name', 'ontology_uri', 'technique', 'standard', 'display_sources')
    search_fields = (
        'name', 'description', 'ontology_uri', 'technique', 'standard', 'instrument_type', 'sources__title')
    fieldsets = (
        (None, {
            'fields': ('name', 'description')
        }),
        ('External Ontology', {
            'fields': ('ontology_uri',)
        }),
        ('Method Details', {
            'fields': ('technique', 'standard', 'instrument_type', 'lower_detection_limit')
        }),
        ('Sources', {
            'fields': ('sources',)
        }),
    )
    ordering = ('name',)
    exclude = ('created_by_id', 'updated_by_id', 'created_at', 'updated_at')
    autocomplete_fields = ('sources',)  # Enable autocomplete for the 'sources' field

    def display_sources(self, obj):
        return ", ".join([source.title for source in obj.sources.all()])

    display_sources.short_description = 'Sources'


admin.site.register(models.Material)
admin.site.register(models.SampleSeries)
admin.site.register(models.Sample)
admin.site.register(models.MaterialComponentGroup)
admin.site.register(models.MaterialProperty)
admin.site.register(models.MaterialPropertyValue)
admin.site.register(models.MaterialComponent)
admin.site.register(models.WeightShare)
admin.site.register(models.Composition)
