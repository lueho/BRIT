from django.contrib import admin

from .models import Greenhouse, GreenhouseGrowthCycle, GrowthTimeStepSet, GrowthShare


@admin.register(Greenhouse)
class GreenhouseAdmin(admin.ModelAdmin):
    list_display = (
        'heated', 'lighted', 'high_wire', 'above_ground',)


admin.site.register(GreenhouseGrowthCycle)
admin.site.register(GrowthTimeStepSet)
admin.site.register(GrowthShare)
