from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from sources.urban_green_spaces.models import HamburgGreenAreas


@admin.register(HamburgGreenAreas)
class HamburgGreenAreasAdmin(GISModelAdmin):
    list_display = (
        "anlagenname",
        "belegenheit",
        "gruenart",
        "flaeche_ha",
        "bezirksnummer",
    )
    search_fields = ("anlagenname", "belegenheit", "identnummer")
    list_filter = ("gruenart", "bezirksnummer")
    ordering = ("anlagenname",)


__all__ = ["HamburgGreenAreasAdmin"]
