from django_filters import FilterSet, CharFilter

from .forms import SourceFilterForm
from .models import Source


class SourceFilter(FilterSet):
    abbreviation = CharFilter(lookup_expr='icontains')
    authors = CharFilter(lookup_expr='icontains')
    title = CharFilter(lookup_expr='icontains')

    class Meta:
        model = Source
        fields = ('abbreviation', 'authors', 'title', 'type', 'year')
        form = SourceFilterForm
