from .models import Catchment
import django_filters

class CatchmentFilter(django_filters.FilterSet):

    class Meta:
        model = Catchment
        fields = ['title']