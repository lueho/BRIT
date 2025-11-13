from django.contrib import admin

from .models import TemporalDistribution, Timestep

admin.site.register(TemporalDistribution)
admin.site.register(Timestep)
