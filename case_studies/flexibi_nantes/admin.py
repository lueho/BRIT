from django.contrib import admin

from .models import Greenhouse


@admin.register(Greenhouse)
class GreenhouseAdmin(admin.ModelAdmin):
    list_display = (
        'heated', 'lighted', 'high_wire', 'above_ground', 'nb_cycles', 'culture_1', 'culture_2', 'culture_3')
