from django.contrib import admin
from django.contrib.gis.admin import OSMGeoAdmin
from .models import HH_Roadside

@admin.register(HH_Roadside)
class HH_Roadside_Admin(OSMGeoAdmin):
    default_lon = 1400000
    default_lat = 7495000
    default_zoom = 12