from django_filters import CharFilter

from utils.filters import CrispyAutocompleteFilterSet
from .models import Catchment


class CatchmentFilter(CrispyAutocompleteFilterSet):
    name = CharFilter(lookup_expr='icontains')

    class Meta:
        model = Catchment
        fields = ('name', 'type',)
