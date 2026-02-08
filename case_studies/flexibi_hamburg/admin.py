from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from .models import HamburgGreenAreas, HamburgRoadsideTrees


@admin.register(HamburgRoadsideTrees)
class HamburgRoadsideTreesAdmin(GISModelAdmin):
    list_display = (
        "baumid",
        "gattung_deutsch",
        "art_deutsch",
        "pflanzjahr",
        "stammumfang",
        "bezirk",
        "stadtteil",
    )
    search_fields = ("baumid", "gattung_deutsch", "art_deutsch", "strasse")
    list_filter = ("bezirk", "gattung_deutsch")
    ordering = ("baumid",)


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
