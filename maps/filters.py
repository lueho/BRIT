from django_filters import CharFilter

from utils.filters import AutocompleteFilterSet
from .models import Catchment


class CatchmentFilter(AutocompleteFilterSet):
    name = CharFilter(lookup_expr='icontains')

    class Meta:
        model = Catchment
        fields = ('name', 'type',)
