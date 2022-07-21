from django_filters import rest_framework as rf_filters
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


class SampleFilterSet(rf_filters.FilterSet):
    class Meta:
        model = Sample
        fields = ('timestep', 'properties',)


class SampleSeriesFilterSet(rf_filters.FilterSet):
    class Meta:
        model = SampleSeries
        fields = ('material',)
