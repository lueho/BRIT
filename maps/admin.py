from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.forms import ModelForm, ValidationError

from .models import Catchment, Location, GeoDataset


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


@admin.register(GeoDataset)
class GeoDatasetAdmin(ModelAdmin):
    list_display = ('name', 'region', 'description')


admin.site.register(Location)
