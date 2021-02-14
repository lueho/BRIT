from django.contrib import admin

from .models import Timestep, TemporalDistribution

admin.site.register(TemporalDistribution)
admin.site.register(Timestep)
