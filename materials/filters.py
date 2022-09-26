from dal import autocomplete
from django_filters import rest_framework as rf_filters
from django_filters import FilterSet, ModelChoiceFilter

from .forms import SampleFilterForm
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


class SampleFilter(FilterSet):
    material = ModelChoiceFilter(queryset=Material.objects.filter(type='material'),
                                 field_name='series__material__name',
                                 label='Material',
                                 widget=autocomplete.ModelSelect2(url='material-autocomplete'))

    class Meta:
        model = Sample
        fields = ('material', 'timestep')
        form = SampleFilterForm


class SampleFilterSet(rf_filters.FilterSet):
    class Meta:
        model = Sample
        fields = ('timestep', 'properties',)


class SampleSeriesFilterSet(rf_filters.FilterSet):
    class Meta:
        model = SampleSeries
        fields = ('material',)
