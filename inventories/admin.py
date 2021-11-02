from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
                     InventoryAlgorithm,
                     InventoryAlgorithmParameter,
                     InventoryAlgorithmParameterValue,
                     InventoryAmountShare,
                     Scenario,
                     ScenarioInventoryConfiguration,
                     ScenarioStatus,
                     RunningTask)


@admin.register(InventoryAlgorithm)
class InventoryAlgorithmAdmin(ModelAdmin):
    list_display = ('name', 'geodataset_link', 'default', 'description',)

    @staticmethod
    def geodataset_link(obj):
        url = reverse('admin:inventories_geodataset_change', args=(obj.geodataset.id,))
        return format_html("<a href='{}'>{}</a>", url, obj.geodataset.name)

    # @staticmethod
    # def feedstock_link(obj):
    #     url = reverse('admin:inventories_material_change', args=(obj.feedstock.id,))
    #     return format_html("<a href='{}'>{}</a>", url, obj.feedstock.name)

    # @staticmethod
    # def parameter_list(obj):
    #     parameter_list = format_html_join(
    #         '\n', "<li><a href='{}'>{}</a></li>",
    #         ((reverse('admin:inventories_inventoryalgorithmparameter_change', args=(p.id,)), p) for p in
    #          InventoryAlgorithmParameter.objects.filter(inventory_algorithm=obj))
    #     )
    #     return parameter_list


@admin.register(InventoryAlgorithmParameter)
class InventoryAlgorithmParameterAdmin(ModelAdmin):
    list_display = ('descriptive_name', 'unit', 'is_required', 'description',)

    # @staticmethod
    # def algorithm(obj):
    #     url = reverse('admin:inventories_inventoryalgorithm_change', args=(obj.inventory_algorithm.id,))
    #     return format_html("<a href='{}'>{}</a>", url, obj.inventory_algorithm.name)


@admin.register(InventoryAlgorithmParameterValue)
class InventoryAlgorithmParameterValueAdmin(ModelAdmin):
    list_display = ('name', 'value', 'standard_deviation', 'default', 'source',)

    # @staticmethod
    # def parameter_link(obj):
    #     url = reverse('admin:inventories_inventoryalgorithmparameter_change', args=(obj.parameter.id,))
    #     return format_html("<a href='{}'>{}</a>", url, obj.parameter.descriptive_name)

    # @staticmethod
    # def unit(obj):
    #     return obj.parameter.unit


@admin.register(ScenarioInventoryConfiguration)
class ScenarioInventoryConfigurationAdmin(ModelAdmin):
    list_display = ('scenario', 'feedstock_link', 'geodataset_link', 'inventory_algorithm_link',
                    'parameter', 'value',)

    @staticmethod
    def feedstock_link(obj):
        url = reverse('admin:material_manager_materialsettings_change', args=(obj.feedstock.id,))
        return format_html("<a href='{}'>{}</a>", url, obj.feedstock.name)

    @staticmethod
    def geodataset_link(obj):
        url = reverse('admin:inventories_geodataset_change', args=(obj.geodataset.id,))
        return format_html("<a href='{}'>{}</a>", url, obj.geodataset.name)

    @staticmethod
    def inventory_algorithm_link(obj):
        url = reverse('admin:inventories_inventoryalgorithm_change', args=(obj.inventory_algorithm.id,))
        return format_html("<a href='{}'>{}</a>", url, obj.inventory_algorithm.name)

    @staticmethod
    def parameter(obj):
        url = reverse('admin:inventories_inventoryalgorithmparameter_change', args=(obj.inventory_parameter.id,))
        return format_html("<a href='{}'>{}</a>", url, obj.inventory_parameter.descriptive_name)

    @staticmethod
    def value(obj):
        url = reverse('admin:inventories_inventoryalgorithmparametervalue_change', args=(obj.inventory_value.id,))
        return format_html("<a href='{}'>{}</a>", url, obj.inventory_value.name)


@admin.register(Scenario)
class ScenarioAdmin(ModelAdmin):
    list_display = ('name', 'region_link', 'catchment_link', 'description', 'status')

    @staticmethod
    def region_link(obj):
        url = reverse('admin:inventories_region_change', args=(obj.region.id,))
        return format_html("<a href='{}'>{}</a>", url, obj.region.name)

    @staticmethod
    def catchment_link(obj):
        url = reverse('admin:inventories_catchment_change', args=(obj.catchment.id,))
        return format_html("<a href='{}'>{}</a>", url, obj.catchment.name)

    @staticmethod
    def status(obj):
        return obj.status


@admin.register(ScenarioStatus)
class ScenarioStatusAdmin(ModelAdmin):
    list_display = ('scenario', 'status')


# @admin.register(SeasonalDistribution)
# class LiteratureSourceAdmin(ModelAdmin):
#     list_display = ('id', 'timesteps', 'cycles', 'start_stop', 'values', 'material', 'component')


admin.site.register(InventoryAmountShare)
admin.site.register(RunningTask)
