from django.contrib import admin

from . import models

admin.site.register(models.Material)
admin.site.register(models.MaterialSettings)
admin.site.register(models.MaterialComponentGroup)
admin.site.register(models.CompositionSet)
admin.site.register(models.MaterialComponent)
admin.site.register(models.MaterialComponentShare)
admin.site.register(models.MaterialComponentGroupSettings)
