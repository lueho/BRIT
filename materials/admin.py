from django.contrib import admin

from . import models

admin.site.register(models.Material)
admin.site.register(models.SampleSeries)
admin.site.register(models.Sample)
admin.site.register(models.MaterialComponentGroup)
admin.site.register(models.MaterialProperty)
admin.site.register(models.MaterialPropertyValue)
admin.site.register(models.MaterialComponent)
admin.site.register(models.WeightShare)
admin.site.register(models.Composition)
