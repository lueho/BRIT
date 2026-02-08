from django.contrib import admin

from .models import Layer, LayerAggregatedValue, LayerField


@admin.register(Layer)
class LayerAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "table_name",
        "geom_type",
        "scenario",
        "feedstock",
        "algorithm",
    )
    search_fields = ("name", "table_name")
    list_filter = ("geom_type",)
    ordering = ("name",)


@admin.register(LayerField)
class LayerFieldAdmin(admin.ModelAdmin):
    list_display = ("field_name", "data_type")
    search_fields = ("field_name",)
    list_filter = ("data_type",)
    ordering = ("field_name",)


@admin.register(LayerAggregatedValue)
class LayerAggregatedValueAdmin(admin.ModelAdmin):
    list_display = ("name", "value", "unit", "layer")
    search_fields = ("name",)
    ordering = ("layer", "name")
