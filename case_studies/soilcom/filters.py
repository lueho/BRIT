from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Field, Layout, Row
from dal import autocomplete
from django.db.models import Count, Q
from django.forms import CheckboxInput, CheckboxSelectMultiple, RadioSelect, DateInput
from django_filters import (BooleanFilter, CharFilter, DateFilter, ModelChoiceFilter, ModelMultipleChoiceFilter,
                            RangeFilter)

from utils.filters import AutocompleteFilterSet, SimpleFilterSet
from utils.widgets import RangeSlider
from .models import (Collection, CollectionCatchment, CollectionCountOptions, Collector, WasteCategory,
                     WasteComponent, WasteFlyer, )


class CollectorFilter(SimpleFilterSet):
    name = CharFilter(lookup_expr='icontains')
    catchment = CharFilter(lookup_expr='name__icontains', label='Catchment name contains')

    class Meta:
        model = Collector
        fields = ('name', 'catchment')


SEASONAL_FREQUENCY_CHOICES = (
    ('', 'All'),
    (True, 'Seasonal'),
    (False, 'Not seasonal'),
)
OPTIONAL_FREQUENCY_CHOICES = (
    ('', 'All'),
    (True, 'Options'),
    (False, 'No options'),
)


class CollectionFilterFormHelper(FormHelper):
    layout = Layout(
        'catchment',
        'collector',
        'collection_system',
        'waste_category',
        'allowed_materials',
        Field('connection_rate', template="fields/range_slider_field.html"),
        'connection_rate_include_unknown',
        Row(Column(Field('seasonal_frequency')), Column(Field('optional_frequency'))),
        'fee_system'
    )


class CollectionFilter(AutocompleteFilterSet):
    catchment = ModelChoiceFilter(queryset=CollectionCatchment.objects.all(),
                                  widget=autocomplete.ModelSelect2(url='catchment-autocomplete'),
                                  method='catchment_filter')
    collector = ModelChoiceFilter(queryset=Collector.objects.all(),
                                  widget=autocomplete.ModelSelect2(url='collector-autocomplete'))
    waste_category = ModelMultipleChoiceFilter(queryset=WasteCategory.objects.all(),
                                               field_name='waste_stream__category',
                                               label='Waste categories',
                                               widget=CheckboxSelectMultiple)
    allowed_materials = ModelMultipleChoiceFilter(queryset=WasteComponent.objects.all(),
                                                  field_name='waste_stream__allowed_materials',
                                                  label='Allowed materials',
                                                  widget=CheckboxSelectMultiple)
    connection_rate = RangeFilter(
        widget=RangeSlider(attrs={'data-range_min': 0, 'data-range_max': 100, 'data-step': 1}),
        method='get_connection_rate'
    )
    connection_rate_include_unknown = BooleanFilter(label='Include unknown connection rate',
                                                    widget=CheckboxInput,
                                                    initial=True,
                                                    method='get_connection_rate_include_unknown')
    seasonal_frequency = BooleanFilter(widget=RadioSelect(
        choices=SEASONAL_FREQUENCY_CHOICES),
        label='Seasonal frequency',
        method='get_seasonal_frequency')
    optional_frequency = BooleanFilter(widget=RadioSelect(
        choices=OPTIONAL_FREQUENCY_CHOICES),
        label='Optional frequency',
        method='get_optional_frequency')

    class Meta:
        model = Collection
        fields = ('catchment', 'collector', 'collection_system', 'waste_category', 'allowed_materials',
                  'connection_rate', 'connection_rate_include_unknown', 'seasonal_frequency', 'optional_frequency',
                  'fee_system')
        # catchment_filter must always be applied first, because it grabs the initial queryset and does not filter any
        # existing queryset.
        order_by = ['catchment_filter']
        form_helper = CollectionFilterFormHelper

    @staticmethod
    def catchment_filter(_, __, value):
        qs = value.downstream_collections.order_by('name')
        if not qs.exists():
            qs = value.upstream_collections.order_by('name')
        return qs

    @staticmethod
    def get_connection_rate(qs, _, value):
        return qs.filter(
            Q(connection_rate__range=(value.start / 100, value.stop / 100)) | Q(connection_rate__isnull=True)
        )

    @staticmethod
    def get_connection_rate_include_unknown(qs, _, value):
        if not value:
            return qs.exclude(connection_rate__isnull=True)
        else:
            return qs

    @staticmethod
    def get_seasonal_frequency(queryset, _, value):
        if value is None:
            return queryset
        queryset = queryset.annotate(season_count=Count('frequency__seasons'))
        if value is True:
            return queryset.filter(season_count__gt=1)
        elif value is False:
            return queryset.filter(season_count__lte=1)

    @staticmethod
    def get_optional_frequency(queryset, _, value):
        if value is None:
            return queryset
        if value is True:
            opts = CollectionCountOptions.objects.filter(Q(option_1__isnull=False) | Q(option_2__isnull=False) |
                                                         Q(option_3__isnull=False))
            return queryset.filter(frequency__in=opts.values_list('frequency'))
        elif value is False:
            opts = CollectionCountOptions.objects.filter(Q(option_1__isnull=True) & Q(option_2__isnull=True) &
                                                         Q(option_3__isnull=True))
            return queryset.filter(frequency__in=opts.values_list('frequency'))


class WasteFlyerFilter(SimpleFilterSet):
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
