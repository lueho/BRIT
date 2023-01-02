from django.contrib import admin

from . import models

admin.site.register(models.Collector)
admin.site.register(models.CollectionFrequency)
admin.site.register(models.CollectionSystem)
admin.site.register(models.CollectionSeason)
admin.site.register(models.WasteCategory)
admin.site.register(models.WasteComponent)
admin.site.register(models.WasteStream)
admin.site.register(models.WasteFlyer)
admin.site.register(models.Collection)
