from django.db.models import Q
from django_filters import CharFilter, FilterSet

from .forms import SourceFilterForm
from .models import Source


class SourceFilter(FilterSet):
    abbreviation = CharFilter(lookup_expr='icontains')
    authors = CharFilter(method='author_icontains', label='Author names contain')
    title = CharFilter(lookup_expr='icontains')

    class Meta:
        model = Source
        fields = ('abbreviation', 'authors', 'title', 'type', 'year')
        form = SourceFilterForm

    @staticmethod
    def author_icontains(queryset, name, value):
        return queryset.filter(
            Q(authors__last_names__icontains=value) | Q(authors__first_names__icontains=value)
        ).distinct()
