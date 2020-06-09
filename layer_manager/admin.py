from django.contrib import admin

from .models import Layer, LayerField, LayerAggregatedValue

admin.site.register(Layer)
admin.site.register(LayerField)
admin.site.register(LayerAggregatedValue)
