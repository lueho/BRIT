from django.contrib import admin

from . import models

admin.site.register(models.Collector)
admin.site.register(models.CollectionSystem)
admin.site.register(models.WasteCategory)
admin.site.register(models.WasteStream)
