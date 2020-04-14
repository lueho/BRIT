import django_filters

from .models import Catchment


class CatchmentFilter(django_filters.FilterSet):
    class Meta:
        model = Catchment
        fields = ['title']
