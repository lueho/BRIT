from django.db.models import Q
from django_filters import CharFilter, FilterSet, ModelChoiceFilter
from django_tomselect.app_settings import TomSelectConfig
from django_tomselect.widgets import TomSelectModelWidget

from utils.filters import BaseCrispyFilterSet
from .models import Author, Source


class AuthorFilterSet(BaseCrispyFilterSet):
    last_names = CharFilter(lookup_expr='icontains')
    first_names = CharFilter(lookup_expr='icontains')

    class Meta:
        model = Author
        fields = ('last_names', 'first_names')


def author_icontains(queryset, _, value):
    return queryset.filter(
        Q(authors__last_names__icontains=value) | Q(authors__first_names__icontains=value)
    ).distinct()


class SourceModelFilterSet(FilterSet):
    abbreviation = CharFilter(lookup_expr='icontains')
    authors = ModelChoiceFilter(
        queryset=Author.objects.all(),
        field_name='authors',
        label='Author',
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url='author-autocomplete',
                value_field='id',
                label_field='label',
                placeholder='Search authors...',
            )
        ),
    )
    title = ModelChoiceFilter(
        queryset=Source.objects.all(),
        label='Title',
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url='source-autocomplete',
                value_field='id',
                label_field='text',
                placeholder='Search by title...',
            )
        ),
        method='filter_title',
    )

    @staticmethod
    def filter_title(queryset, name, value):
        if value:
            return queryset.filter(pk=value.pk)
        return queryset

    class Meta:
        model = Source
        fields = ('abbreviation', 'authors', 'title', 'type', 'year')


class SourceFilter(BaseCrispyFilterSet):
    abbreviation = CharFilter(lookup_expr='icontains')
    authors = ModelChoiceFilter(
        queryset=Author.objects.all(),
        field_name='authors',
        label='Author',
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url='author-autocomplete',
                value_field='id',
                label_field='label',
                placeholder='Search authors...',
            )
        ),
    )
    title = ModelChoiceFilter(
        queryset=Source.objects.all(),
        label='Title',
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url='source-autocomplete',
                value_field='id',
                label_field='text',
                placeholder='Search by title...',
            )
        ),
        method='filter_title',
    )

    class Meta:
        model = Source
        fields = ('abbreviation', 'authors', 'title', 'type', 'year')

    @staticmethod
    def filter_title(queryset, name, value):
        if value:
            return queryset.filter(pk=value.pk)
        return queryset
