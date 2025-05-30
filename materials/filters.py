from django_filters import ModelChoiceFilter, rest_framework as rf_filters

from utils.filters import CrispyAutocompleteFilterSet
from utils.widgets import BSModelSelect2
from .models import Composition, Material, Sample, SampleSeries


class MaterialFilterSet(rf_filters.FilterSet):
    class Meta:
        model = Material
        fields = {
            'name': ['iexact', 'icontains'],
            'categories': ['iexact']
        }


class CompositionFilterSet(rf_filters.FilterSet):
    class Meta:
        model = Composition
        fields = ('group', 'fractions_of',)


class SampleFilter(CrispyAutocompleteFilterSet):
    name = ModelChoiceFilter(
        queryset=Sample.objects.none(),
        field_name='name',
        label='Sample Name',
        widget=BSModelSelect2(url='sample-autocomplete')
    )
    material = ModelChoiceFilter(queryset=Material.objects.filter(type='material'),
                                 field_name='material__name',
                                 label='Material',
                                 widget=BSModelSelect2(url='material-autocomplete'))

    class Meta:
        model = Sample
        fields = ('name', 'material',)


class PublishedSampleFilter(SampleFilter):
    name = ModelChoiceFilter(
        queryset=Sample.objects.filter(publication_status='published'),
        field_name='name',
        label='Sample Name',
        widget=BSModelSelect2(url='sample-autocomplete-published')
    )


class UserOwnedSampleFilter(SampleFilter):
    name = ModelChoiceFilter(
        queryset=Sample.objects.all(),
        field_name='name',
        label='Sample Name',
        widget=BSModelSelect2(url='sample-autocomplete-owned')
    )


class SampleSeriesFilter(CrispyAutocompleteFilterSet):
    material = ModelChoiceFilter(queryset=Material.objects.filter(type='material'),
                                 field_name='material__name',
                                 label='Material',
                                 widget=BSModelSelect2(url='material-autocomplete'))

    class Meta:
        model = SampleSeries
        fields = ('material',)


class SampleFilterSet(rf_filters.FilterSet):
    class Meta:
        model = Sample
        fields = ('timestep', 'properties',)


class SampleSeriesFilterSet(rf_filters.FilterSet):
    class Meta:
        model = SampleSeries
        fields = ('material',)
