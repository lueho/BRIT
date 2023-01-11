import math

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Field, Layout, Row
from dal import autocomplete
from django.db.models import Avg, Count, Max, Q, Sum
from django.forms import CheckboxInput, CheckboxSelectMultiple, DateInput, RadioSelect
from django_filters import (BooleanFilter, CharFilter, ChoiceFilter, DateFilter, ModelChoiceFilter,
                            ModelMultipleChoiceFilter,
                            RangeFilter)

from utils.crispy_fields import RangeSliderField
from utils.filters import AutocompleteFilterSet, SimpleFilterSet
from utils.widgets import PercentageRangeSlider, RangeSlider
from .models import (Collection, CollectionCatchment, CollectionCountOptions, CollectionFrequency,
                     CollectionPropertyValue, Collector, WasteCategory, WasteComponent, WasteFlyer, )


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

SPEC_WASTE_COLLECTED_FILTER_MODE_CHOICES = (
    ('average', 'average'),
    # ('exists', 'exists'),
    # ('latest', 'latest')
)


class CollectionFilterFormHelper(FormHelper):
    layout = Layout(
        'catchment',
        'collector',
        'collection_system',
        'waste_category',
        'allowed_materials',
        RangeSliderField('connection_rate'),
        'connection_rate_include_unknown',
        Row(Column(Field('seasonal_frequency')), Column(Field('optional_frequency'))),
        RangeSliderField('collections_per_year'),
        'collections_per_year_include_unknown',
        RangeSliderField('spec_waste_collected'),
        'spec_waste_collected_filter_method',
        'spec_waste_collected_include_unknown',
        'fee_system'
    )


class CollectionsPerYearFilter(RangeFilter):

    def set_min_max(self):
        frequencies = CollectionFrequency.objects.annotate(collection_count=Sum('collectioncountoptions__standard'))
        if frequencies.exists():
            max_value = frequencies.aggregate(Max('collection_count'))['collection_count__max']
        else:
            max_value = 1000
        self.extra['widget'] = RangeSlider(attrs={'data-range_min': 0, 'data-range_max': max_value, 'data-step': 1})


class SpecWasteCollectedFilter(RangeFilter):

    def set_min_max(self):
        values = CollectionPropertyValue.objects.filter(property__name='specific waste collected')
        if values.exists():
            max_value = math.ceil(values.aggregate(Max('average'))['average__max'])
        else:
            max_value = 1000
        self.extra['widget'] = RangeSlider(attrs={'data-range_min': 0, 'data-range_max': max_value, 'data-step': 1})


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
        widget=PercentageRangeSlider(attrs={'data-range_min': 0, 'data-range_max': 100, 'data-step': 1}),
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
    collections_per_year = CollectionsPerYearFilter(
        method='get_collections_per_year',
        label='Collections per year'
    )
    collections_per_year_include_unknown = BooleanFilter(label='Include unknown collection frequency',
                                                         widget=CheckboxInput,
                                                         initial=True,
                                                         method='get_collections_per_year_include_unknown')
    spec_waste_collected = SpecWasteCollectedFilter(
        label='Specific waste collected [kg/(cap.*a)]',
        method='get_spec_waste_collected'
    )
    spec_waste_collected_filter_method = ChoiceFilter(
        label='Filter method',
        empty_label=None,
        choices=SPEC_WASTE_COLLECTED_FILTER_MODE_CHOICES,
        method='get_spec_waste_collected_filter_method',
        initial='average'
    )
    spec_waste_collected_include_unknown = BooleanFilter(label='Include unknown collected amounts',
                                                         widget=CheckboxInput,
                                                         initial=True,
                                                         method='get_spec_waste_collected_include_unknown')

    class Meta:
        model = Collection
        fields = ('catchment', 'collector', 'collection_system', 'waste_category', 'allowed_materials',
                  'connection_rate', 'connection_rate_include_unknown', 'seasonal_frequency', 'optional_frequency',
                  'collections_per_year', 'collections_per_year_include_unknown', 'spec_waste_collected_filter_method',
                  'spec_waste_collected_include_unknown', 'spec_waste_collected', 'fee_system')
        # catchment_filter must always be applied first, because it grabs the initial queryset and does not filter any
        # existing queryset.
        order_by = ['catchment_filter']
        form_helper = CollectionFilterFormHelper

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filters['collections_per_year'].set_min_max()
        self.filters['spec_waste_collected'].set_min_max()

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

    @staticmethod
    def get_collections_per_year_include_unknown(qs, _, value):
        if not value:
            return qs.exclude(frequency__isnull=True)
        else:
            return qs

    @staticmethod
    def get_collections_per_year(qs, _, value):
        frequencies = CollectionFrequency.objects.annotate(collection_count=Sum('collectioncountoptions__standard'))
        frequencies = frequencies.filter(collection_count__gte=value.start, collection_count__lte=value.stop)
        return qs.filter(Q(frequency__in=frequencies) | Q(frequency__isnull=True))

    def get_spec_waste_collected(self, qs, _, value):
        if self.spec_waste_collected_filter_setting == 'latest':
            # TODO: implement this filter method
            return qs
        elif self.spec_waste_collected_filter_setting == 'exists':
            # TODO: implement this filter method
            return qs
        elif self.spec_waste_collected_filter_setting == 'average':
            property_filter = Q(
                collectionpropertyvalue__property__name='specific waste collected',
                collectionpropertyvalue__average__gt=0.0
            )
            qs = qs.annotate(average_amount=Avg('collectionpropertyvalue__average', filter=property_filter))
            if self.spec_waste_collected_include_unknown:
                qs = qs.filter(
                    Q(average_amount__gte=value.start, average_amount__lte=value.stop) | Q(average_amount__isnull=True))
            else:
                qs = qs.filter(average_amount__gte=value.start, average_amount__lte=value.stop)
            return qs
        return qs

    def get_spec_waste_collected_filter_method(self, qs, _, value):
        self.spec_waste_collected_filter_setting = value
        return qs

    def get_spec_waste_collected_include_unknown(self, qs, _, value):
        self.spec_waste_collected_include_unknown = value
        return qs


class WasteFlyerFilter(AutocompleteFilterSet):
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
    catchment = ModelChoiceFilter(queryset=CollectionCatchment.objects.all(),
                                  label='Catchment',
                                  widget=autocomplete.ModelSelect2(url='catchment-autocomplete'),
                                  field_name='collections__catchment')

    class Meta:
        model = WasteFlyer
        fields = ('url_valid', 'url_checked_before', 'url_checked_after', 'catchment')
