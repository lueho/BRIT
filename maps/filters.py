from dal import forward
from django.forms import HiddenInput
from django_filters import CharFilter, ModelChoiceFilter, NumberFilter

from utils.filters import BaseCrispyFilterSet, CrispyAutocompleteFilterSet
from utils.widgets import BSModelSelect2
from .models import Catchment, GeoDataset, NutsRegion, Region


class CatchmentFilterSet(CrispyAutocompleteFilterSet):
    id = NumberFilter(widget=HiddenInput())
    name = CharFilter(lookup_expr='icontains')

    class Meta:
        model = Catchment
        fields = ('id', 'name', 'type',)


class RegionFilterSet(CrispyAutocompleteFilterSet):
    name_icontains = CharFilter(field_name='name', lookup_expr='icontains', label='Name contains')

    class Meta:
        model = Region
        fields = ('id', 'name', 'name_icontains', 'country',)


class NutsRegionFilterSet(CrispyAutocompleteFilterSet):
    level_0 = ModelChoiceFilter(queryset=NutsRegion.objects.filter(levl_code=0),
                                field_name='levl_code',
                                widget=BSModelSelect2(url='nutsregion-autocomplete',
                                                      forward=(forward.Const(0, 'levl_code'),)),
                                label='Level 0')
    level_1 = ModelChoiceFilter(queryset=NutsRegion.objects.filter(levl_code=1),
                                field_name='levl_code',
                                widget=BSModelSelect2(
                                    url='nutsregion-autocomplete',
                                    forward=(
                                        forward.Const(1, 'levl_code'),
                                        forward.Field('level_0', 'parent')
                                    )
                                ),
                                label='Level 1')
    level_2 = ModelChoiceFilter(queryset=NutsRegion.objects.filter(levl_code=2),
                                field_name='levl_code',
                                widget=BSModelSelect2(
                                    url='nutsregion-autocomplete',
                                    forward=(
                                        forward.Const(2, 'levl_code'),
                                        forward.Field('level_0', 'grandparent'),
                                        forward.Field('level_1', 'parent')
                                    )
                                ),
                                label='Level 2')
    level_3 = ModelChoiceFilter(queryset=NutsRegion.objects.filter(levl_code=3),
                                field_name='levl_code',
                                widget=BSModelSelect2(
                                    url='nutsregion-autocomplete',
                                    forward=(
                                        forward.Const(3, 'levl_code'),
                                        forward.Field('level_0', 'great_grandparent'),
                                        forward.Field('level_1', 'grandparent'),
                                        forward.Field('level_2', 'parent')
                                    )
                                ),
                                label='Level 3')

    class Meta:
        model = NutsRegion
        fields = ['level_0', 'level_1', 'level_2', 'level_3']


class GeoDataSetFilterSet(BaseCrispyFilterSet):
    class Meta:
        model = GeoDataset
        fields = ('id',)
