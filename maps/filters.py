from django_filters import CharFilter

from utils.filters import CrispyAutocompleteFilterSet
from .models import Catchment, Region


class CatchmentFilter(CrispyAutocompleteFilterSet):
    name = CharFilter(lookup_expr='icontains')

    class Meta:
        model = Catchment
        fields = ('name', 'type',)


class RegionFilterSet(CrispyAutocompleteFilterSet):
    name_icontains = CharFilter(field_name='name', lookup_expr='icontains', label='Name contains')

    class Meta:
        model = Region
        fields = ('name', 'name_icontains', 'country',)
