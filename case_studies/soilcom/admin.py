from django.contrib import admin

from . import models

admin.site.register(models.Collector)
admin.site.register(models.CollectionSystem)
admin.site.register(models.WasteStreamCategory)
admin.site.register(models.WasteStreamAllowed)
