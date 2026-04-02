from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from sources.roadside_trees.models import HamburgRoadsideTrees


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


__all__ = ["HamburgRoadsideTreesAdmin"]
