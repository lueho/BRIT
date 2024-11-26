from django.contrib import admin

from .models import (Attribute, Catchment, GeoDataset, Location, MapConfiguration, MapLayerConfiguration, MapLayerStyle,
                     ModelMapConfiguration, Region, RegionAttributeTextValue, RegionAttributeValue)


@admin.register(Attribute)
class AttributeModelAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(Catchment)
class CatchmentModelAdmin(admin.ModelAdmin):
    autocomplete_fields = ['region', 'parent_region', 'parent']
    search_fields = ['name']


@admin.register(GeoDataset)
class GeoDatasetModelAdmin(admin.ModelAdmin):
    autocomplete_fields = ['region']


@admin.register(Location)
class LocationModelAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(MapLayerStyle)
class LayerStyleModelAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(MapLayerConfiguration)
class LayerModelAdmin(admin.ModelAdmin):
    autocomplete_fields = ['style']
    search_fields = ['name']


@admin.register(MapConfiguration)
class MapConfigurationModelAdmin(admin.ModelAdmin):
    autocomplete_fields = ['layers']
    search_fields = ['name']


@admin.register(ModelMapConfiguration)
class ModelMapConfigurationModelAdmin(admin.ModelAdmin):
    autocomplete_fields = ['map_config']  # TODO autocomplete for model_name


@admin.register(Region)
class RegionModelAdmin(admin.ModelAdmin):
    autocomplete_fields = ['composed_of']
    raw_id_fields = ['borders']
    search_fields = ['name']


@admin.register(RegionAttributeValue)
class RegionAttributeValueModelAdmin(admin.ModelAdmin):
    autocomplete_fields = ['region', 'attribute']


@admin.register(RegionAttributeTextValue)
class RegionAttributeTextValueModelAdmin(admin.ModelAdmin):
    autocomplete_fields = ['region', 'attribute']
