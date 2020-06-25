from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.contrib.gis.admin import OSMGeoAdmin
from django.forms import ModelForm, ValidationError
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from .models import (Catchment,
                     InventoryAlgorithm,
                     InventoryAlgorithmParameter,
                     InventoryAlgorithmParameterValue,
                     Material,
                     MaterialComponent,
                     Region,
                     Scenario,
                     ScenarioInventoryConfiguration,
                     SFBSite,
                     GeoDataset, )


class CatchmentForm(ModelForm):
    class Meta:
        model = Catchment
        fields = ('name', 'owner', 'region', 'type', 'description', 'geom',)

    @staticmethod
    def django_contains(region, catchment):
        region_geom = region.geom
        catchment_geom = catchment.get('geom')
        return region_geom.contains(catchment_geom)

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
        queryset = queryset.order_by('type', 'region', 'name', )
        return queryset


@admin.register(Region)
class RegionAdmin(OSMGeoAdmin):
    list_display = ('name', 'country', 'implemented_algorithms',)
    readonly_fields = ('implemented_algorithms',)

    @staticmethod
    def implemented_algorithms(obj):
        algorithms = [(reverse('admin:scenario_builder_inventoryalgorithm_change', args=(alg.id,)),
                       alg.geodataset.name,
                       reverse('admin:scenario_builder_material_change', args=(alg.feedstock.id,)),
                       alg.feedstock.name)
                      for alg in InventoryAlgorithm.objects.filter(geodataset__region=obj)]
        algorithm_list = format_html_join(
            '\n', "<li><a href='{}'>{}</a>: <a href='{}'>{}</a></li>",
            (alg for alg in algorithms)
        )
        return algorithm_list

    def get_queryset(self, request):
        queryset = super(RegionAdmin, self).get_queryset(request)
        queryset = queryset.order_by('name')
        return queryset


@admin.register(Material)
class MaterialAdmin(ModelAdmin):
    list_display = ('name', 'stan_flow_id', 'is_feedstock', 'description',)


@admin.register(InventoryAlgorithm)
class InventoryAlgorithmAdmin(ModelAdmin):
    list_display = ('name', 'geodataset_link', 'feedstock_link', 'parameter_list', 'default', 'description',)

    @staticmethod
    def geodataset_link(obj):
        url = reverse('admin:scenario_builder_geodataset_change', args=(obj.geodataset.id,))
        return format_html("<a href='{}'>{}</a>", url, obj.geodataset.name)

    @staticmethod
    def feedstock_link(obj):
        url = reverse('admin:scenario_builder_material_change', args=(obj.feedstock.id,))
        return format_html("<a href='{}'>{}</a>", url, obj.feedstock.name)

    @staticmethod
    def parameter_list(obj):
        parameter_list = format_html_join(
            '\n', "<li><a href='{}'>{}</a></li>",
            ((reverse('admin:scenario_builder_inventoryalgorithmparameter_change', args=(p.id,)), p) for p in
             InventoryAlgorithmParameter.objects.filter(inventory_algorithm=obj))
        )
        return parameter_list


@admin.register(InventoryAlgorithmParameter)
class InventoryAlgorithmParameterAdmin(ModelAdmin):
    list_display = ('descriptive_name', 'unit', 'algorithm', 'is_required', 'description',)

    @staticmethod
    def algorithm(obj):
        url = reverse('admin:scenario_builder_inventoryalgorithm_change', args=(obj.inventory_algorithm.id,))
        return format_html("<a href='{}'>{}</a>", url, obj.inventory_algorithm.name)


@admin.register(InventoryAlgorithmParameterValue)
class InventoryAlgorithmParameterValueAdmin(ModelAdmin):
    list_display = ('name', 'parameter_link', 'value', 'standard_deviation', 'unit', 'default', 'source',)

    @staticmethod
    def parameter_link(obj):
        url = reverse('admin:scenario_builder_inventoryalgorithmparameter_change', args=(obj.parameter.id,))
        return format_html("<a href='{}'>{}</a>", url, obj.parameter.descriptive_name)

    @staticmethod
    def unit(obj):
        return obj.parameter.unit


@admin.register(ScenarioInventoryConfiguration)
class ScenarioInventoryConfigurationAdmin(ModelAdmin):
    list_display = ('scenario', 'feedstock_link', 'geodataset_link', 'inventory_algorithm_link',
                    'parameter', 'value',)

    @staticmethod
    def feedstock_link(obj):
        url = reverse('admin:scenario_builder_material_change', args=(obj.feedstock.id,))
        return format_html("<a href='{}'>{}</a>", url, obj.feedstock.name)

    @staticmethod
    def geodataset_link(obj):
        url = reverse('admin:scenario_builder_geodataset_change', args=(obj.geodataset.id,))
        return format_html("<a href='{}'>{}</a>", url, obj.geodataset.name)

    @staticmethod
    def inventory_algorithm_link(obj):
        url = reverse('admin:scenario_builder_inventoryalgorithm_change', args=(obj.inventory_algorithm.id,))
        return format_html("<a href='{}'>{}</a>", url, obj.inventory_algorithm.name)

    @staticmethod
    def parameter(obj):
        url = reverse('admin:scenario_builder_inventoryalgorithmparameter_change', args=(obj.inventory_parameter.id,))
        return format_html("<a href='{}'>{}</a>", url, obj.inventory_parameter.descriptive_name)

    @staticmethod
    def value(obj):
        url = reverse('admin:scenario_builder_inventoryalgorithmparametervalue_change', args=(obj.inventory_value.id,))
        return format_html("<a href='{}'>{}</a>", url, obj.inventory_value.name)


@admin.register(GeoDataset)
class GeoDatasetAdmin(ModelAdmin):
    list_display = ('name', 'region', 'description')


@admin.register(Scenario)
class ScenarioAdmin(ModelAdmin):
    list_display = ('name', 'region_link', 'site_link', 'catchment_link', 'description')

    @staticmethod
    def region_link(obj):
        url = reverse('admin:scenario_builder_region_change', args=(obj.region.id,))
        return format_html("<a href='{}'>{}</a>", url, obj.region.name)

    @staticmethod
    def site_link(obj):
        url = reverse('admin:scenario_builder_sfbsite_change', args=(obj.site.id,))
        return format_html("<a href='{}'>{}</a>", url, obj.site.name)

    @staticmethod
    def catchment_link(obj):
        url = reverse('admin:scenario_builder_catchment_change', args=(obj.catchment.id,))
        return format_html("<a href='{}'>{}</a>", url, obj.catchment.name)


admin.site.register(MaterialComponent)
admin.site.register(SFBSite)