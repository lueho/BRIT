from dal import autocomplete
from django.db.models import Q
from django.forms import CheckboxSelectMultiple
from django_filters import ModelChoiceFilter, ModelMultipleChoiceFilter, FilterSet, ChoiceFilter
from django_filters import rest_framework as rf_filters

from .forms import CollectionFilterForm
from .models import Catchment, Collection, Collector, WasteCategory, WasteComponent

COUNTRY_CHOICES = (
    ('BE', 'BE'),
    ('DE', 'DE'),
    ('DK', 'DK'),
    ('NL', 'NL'),
    ('UK', 'UK'),
    ('SE', 'SE'),
)


class CollectionFilter(FilterSet):
    catchment = ModelChoiceFilter(queryset=Catchment.objects.all(),
                                  widget=autocomplete.ModelSelect2(url='catchment-autocomplete'))
    collector = ModelChoiceFilter(queryset=Collector.objects.all(),
                                  widget=autocomplete.ModelSelect2(url='collector-autocomplete'))
    country = ChoiceFilter(choices=COUNTRY_CHOICES, label='Country', method='filter_by_country')
    waste_category = ModelMultipleChoiceFilter(queryset=WasteCategory.objects.all(),
                                               field_name='waste_stream__category',
                                               label='Waste categories',
                                               widget=CheckboxSelectMultiple)
    allowed_materials = ModelMultipleChoiceFilter(queryset=WasteComponent.objects.all(),
                                                  field_name='waste_stream__allowed_materials',
                                                  label='Allowed materials',
                                                  widget=CheckboxSelectMultiple)

    class Meta:
        model = Collection
        fields = ('catchment', 'collector', 'collection_system', 'country', 'waste_category', 'allowed_materials')
        form = CollectionFilterForm

    def filter_by_country(self, qs, name, value):
        qs = qs.filter(
            Q(catchment__region__nutsregion__cntr_code=value) |
            Q(catchment__region__lauregion__cntr_code=value))
        return qs
