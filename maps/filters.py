from django_filters import CharFilter, FilterSet

from .models import Catchment


class CatchmentFilter(FilterSet):
    name = CharFilter(lookup_expr='icontains')

    class Meta:
        model = Catchment
        fields = ('name', 'type',)
