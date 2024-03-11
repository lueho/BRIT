from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.contrib.gis.admin import OSMGeoAdmin
from django.forms import ModelForm, ValidationError
from .models import Region, Catchment, Location, SFBSite, GeoDataset


class CatchmentForm(ModelForm):
    class Meta:
        model = Catchment
        fields = ('name', 'owner', 'parent_region', 'type', 'description',)

    @staticmethod
    def django_contains(region, catchment):
        region_geom = region.geom
        catchment_geom = catchment.get('geom')
        return region_geom.contains(catchment_geom)

    def clean(self):
        catchment = super().clean()
        region = catchment.get('parent_region')
        if region and catchment:
            if not self.django_contains(region, catchment):
                raise ValidationError('The catchment must be within the defined region.')


@admin.register(Catchment)
class CatchmentAdmin(OSMGeoAdmin):
    form = CatchmentForm
    list_display = ('name', 'parent_region', 'type', 'description')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.order_by('type', 'region', 'name', )
        return queryset


@admin.register(Region)
class RegionAdmin(OSMGeoAdmin):
    list_display = ('name', 'country',)

    # readonly_fields = ('implemented_algorithms',)

    # @staticmethod
    # def implemented_algorithms(obj):
    #     algorithms = [(reverse('admin:inventories_inventoryalgorithm_change', args=(alg.id,)),
    #                    alg.geodataset.name,
    #                    reverse('admin:inventories_material_change', args=(alg.feedstock.id,)),
    #                    alg.feedstock.name)
    #                   for alg in InventoryAlgorithm.objects.filter(geodataset__region=obj)]
    #     algorithm_list = format_html_join(
    #         '\n', "<li><a href='{}'>{}</a>: <a href='{}'>{}</a></li>",
    #         (alg for alg in algorithms)
    #     )
    #     return algorithm_list

    def get_queryset(self, request):
        queryset = super(RegionAdmin, self).get_queryset(request)
        queryset = queryset.order_by('name')
        return queryset


@admin.register(GeoDataset)
class GeoDatasetAdmin(ModelAdmin):
    list_display = ('name', 'region', 'description')


admin.site.register(SFBSite)
admin.site.register(Location)
