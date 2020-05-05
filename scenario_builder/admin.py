from django.contrib import admin
from django.contrib.gis.admin import OSMGeoAdmin
from django.db import connection
from django.forms import ModelForm, ValidationError
from django.utils.html import format_html_join

from .models import (Catchment,
                     InventoryAlgorithm,
                     InventoryAlgorithmParameter,
                     Material,
                     MaterialComponent,
                     Region,
                     Scenario,
                     SFBSite,
                     GeoDataset, )


class CatchmentForm(ModelForm):
    class Meta:
        model = Catchment
        fields = ('name', 'region', 'type', 'description', 'geom',)

    @staticmethod
    def django_contains(region, catchment):
        region_geom = region.geom
        catchment_geom = catchment.get('geom')
        return region_geom.contains(catchment_geom)

    @staticmethod
    def postgis_contains(region, catchment):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT ST_CONTAINS((SELECT geom FROM scenario_builder_region WHERE name=%s),"
                "(SELECT geom FROM scenario_builder_catchment WHERE name=%s))",
                [region.name, catchment.get('name')]
            )
            return cursor.fetchone()

    def clean(self):
        catchment = super().clean()
        region = catchment.get('region')
        if region and catchment:
            if not self.django_contains(region, catchment):
                raise ValidationError('The catchment must be within the defined region.')


@admin.register(Catchment)
class CatchmentAdmin(OSMGeoAdmin):
    form = CatchmentForm
    list_display = ('name', 'region', 'type', 'description')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.order_by('type', 'region', 'name')
        return queryset


@admin.register(Region)
class RegionAdmin(OSMGeoAdmin):
    list_display = ('name', 'country', 'available_feedstock_inventories',)
    readonly_fields = ('available_feedstock_inventories',)

    @staticmethod
    def available_feedstock_inventories(obj):
        feedstocks = list(set([ds.feedstock.name for ds in GeoDataset.objects.filter(region=obj)]))
        feedstock_list = format_html_join(
            '\n', "<li>{}</li>",
            ((f,) for f in feedstocks)
        )
        return feedstock_list

    def get_queryset(self, request):
        queryset = super(RegionAdmin, self).get_queryset(request)
        queryset = queryset.order_by('name')
        return queryset


admin.site.register(Material)
admin.site.register(MaterialComponent)
admin.site.register(Scenario)
admin.site.register(SFBSite)
admin.site.register(GeoDataset)
admin.site.register(InventoryAlgorithm)
admin.site.register(InventoryAlgorithmParameter)
