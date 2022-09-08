from dal import autocomplete
from django.db.models import Q
from django.forms import CheckboxSelectMultiple, RadioSelect, DateInput
from django_filters import (BooleanFilter,
                            ChoiceFilter,
                            DateFilter,
                            FilterSet,
                            ModelChoiceFilter,
                            ModelMultipleChoiceFilter, )

from .forms import CollectionFilterForm, FlyerFilterForm
from .models import Catchment, Collection, Collector, WasteCategory, WasteComponent, WasteFlyer

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
    country = ChoiceFilter(choices=COUNTRY_CHOICES, field_name='catchment__region__country', label='Country')
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


class WasteFlyerFilter(FilterSet):
    url_valid = BooleanFilter(widget=RadioSelect(choices=((True, 'True'), (False, 'False'))))
    url_checked_before = DateFilter(
        field_name='url_checked',
        lookup_expr='lt',
        widget=DateInput(attrs={'type': 'date'}),
        label='Url checked before'
    )
    url_checked_after = DateFilter(
        field_name='url_checked',
        lookup_expr='gt',
        widget=DateInput(attrs={'type': 'date'}),
        label='Url checked after'
    )

    class Meta:
        model = WasteFlyer
        fields = ('url_valid', 'url_checked_before', 'url_checked_after')
        form = FlyerFilterForm
