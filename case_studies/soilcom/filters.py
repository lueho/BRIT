import math

from crispy_forms.bootstrap import Accordion
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Field, Layout, Row, Submit
from dal import autocomplete
from django.db.models import Avg, Count, Max, Q, Sum
from django.forms import CheckboxInput, CheckboxSelectMultiple, DateInput, RadioSelect
from django.utils import timezone
from django_filters import (BooleanFilter, CharFilter, DateFilter, ModelChoiceFilter, ModelMultipleChoiceFilter)

from utils.crispy_fields import FilterAccordionGroup, RangeSliderField
from utils.filters import (CrispyAutocompleteFilterSet, BaseCrispyFilterSet, NullableRangeFilter)
from utils.widgets import NullableRangeSliderWidget
from .models import (Collection, CollectionCatchment, CollectionCountOptions, CollectionFrequency,
                     CollectionPropertyValue, Collector, FeeSystem, WasteCategory, WasteComponent, WasteFlyer, )


class CollectorFilter(BaseCrispyFilterSet):
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
        Accordion(
            FilterAccordionGroup(
                'Filters',
                'catchment',
                'collector',
                'collection_system',
                'waste_category',
                Submit('filter', 'Filter', css_id='submit-id-basic-filter', css_class='submit-filter')
            ),
            FilterAccordionGroup(
                'Advanced filters',
                'allowed_materials',
                'forbidden_materials',
                RangeSliderField('connection_rate'),
                Row(Column(Field('seasonal_frequency'), css_class='col-md'),
                    Column(Field('optional_frequency'), css_class='col-md')),
                RangeSliderField('collections_per_year'),
                RangeSliderField('spec_waste_collected'),
                'fee_system',
                'valid_on',
                Field('load_features', type='hidden'),
                Submit('filter', 'Filter', css_id='submit-id-basic-filter', css_class='submit-filter')
            )
        )
    )


class CollectionsPerYearFilter(NullableRangeFilter):

    def set_min_max(self):
        frequencies = CollectionFrequency.objects.annotate(collection_count=Sum('collectioncountoptions__standard'))
        if frequencies.exists():
            max_value = frequencies.aggregate(Max('collection_count'))['collection_count__max']
        else:
            max_value = 1000
        self.extra['widget'] = NullableRangeSliderWidget(attrs={
            'data-range_min': 0,
            'data-range_max': max_value,
            'data-step': 1,
            'data-is_null': self.default_include_null,
            'data-unit': ''
        })

    def filter(self, qs, range_with_null_flag):
        if not range_with_null_flag:
            return qs
        range_vals, is_null = range_with_null_flag
        frequencies = CollectionFrequency.objects.annotate(collection_count=Sum('collectioncountoptions__standard'))
        frequencies = frequencies.filter(collection_count__gte=range_vals.start, collection_count__lte=range_vals.stop)
        if is_null:
            return qs.filter(Q(frequency__in=frequencies) | Q(frequency__isnull=True))
        return qs.filter(frequency__in=frequencies)


class NullableCollectionPropertyValueRangeFilter(NullableRangeFilter):
    """Filter for CollectionPropertyValue model. It is used to filter by average value of property."""
    property_name = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.property_name = kwargs.get('property_name', self.property_name)

    def set_min_max(self):
        values = CollectionPropertyValue.objects.filter(property__name=self.property_name)
        if self.range_min is None:
            self.range_min = self.default_range_min
        if self.range_max is None:
            if values.exists():
                self.range_max = math.ceil(values.aggregate(Max('average'))['average__max'])
            else:
                self.range_max = self.default_range_max
        if self.range_step is None:
            self.range_step = self.default_range_step
        self.extra['widget'] = NullableRangeSliderWidget(
            attrs={
                'data-range_min': self.range_min,
                'data-range_max': self.range_max,
                'data-step': self.range_step,
                'data-is_null': self.default_include_null,
                'data-unit': self.unit}
        )

    def filter(self, qs, percentage_range_with_null_flag):
        if not percentage_range_with_null_flag:
            return qs
        range_, is_null = percentage_range_with_null_flag
        property_filter = Q(
            collectionpropertyvalue__property__name=self.property_name,
            collectionpropertyvalue__average__gt=0.0
        )
        qs = qs.annotate(
            average_collectionpropertyvalue_average=Avg('collectionpropertyvalue__average', filter=property_filter))
        if is_null:
            qs = qs.filter(
                Q(average_collectionpropertyvalue_average__gte=range_.start,
                  average_collectionpropertyvalue_average__lte=range_.stop) |
                Q(average_collectionpropertyvalue_average__isnull=True)
            )
        else:
            qs = qs.filter(average_collectionpropertyvalue_average__gte=range_.start,
                           average_collectionpropertyvalue_average__lte=range_.stop)
        return qs


class ConnectionRateFilter(NullableCollectionPropertyValueRangeFilter):
    property_name = 'Connection rate'
    unit = '%'


class SpecWasteCollectedFilter(NullableCollectionPropertyValueRangeFilter):
    property_name = 'specific waste collected'
    default_range_max = 1000


class CollectionFilterSet(CrispyAutocompleteFilterSet):
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
    forbidden_materials = ModelMultipleChoiceFilter(queryset=WasteComponent.objects.all(),
                                                    field_name='waste_stream__forbidden_materials',
                                                    label='Forbidden materials',
                                                    widget=CheckboxSelectMultiple)
    connection_rate = ConnectionRateFilter(label='Connection rate')
    seasonal_frequency = BooleanFilter(widget=RadioSelect(
        choices=SEASONAL_FREQUENCY_CHOICES),
        label='Seasonal frequency',
        method='get_seasonal_frequency')
    optional_frequency = BooleanFilter(widget=RadioSelect(
        choices=OPTIONAL_FREQUENCY_CHOICES),
        label='Optional frequency',
        method='get_optional_frequency')
    collections_per_year = CollectionsPerYearFilter(
        label='Collections per year'
    )
    spec_waste_collected = SpecWasteCollectedFilter(
        label='Specific waste collected [kg/(cap.*a)]',
    )
    fee_system = ModelChoiceFilter(
        queryset=FeeSystem.objects.all(),
    )
    valid_on = DateFilter(method='filter_valid_on', widget=DateInput(attrs={'type': 'date'}),
                          initial=timezone.now().date(), label='Valid on')
    load_features = BooleanFilter(
        label='Load features',
        initial=True,
        widget=CheckboxInput(), method='get_load_features'
    )

    class Meta:
        model = Collection
        fields = ('catchment', 'collector', 'collection_system', 'waste_category', 'allowed_materials',
                  'forbidden_materials', 'connection_rate', 'seasonal_frequency', 'optional_frequency',
                  'collections_per_year', 'spec_waste_collected', 'fee_system', 'valid_on', 'load_features')
        # catchment_filter must always be applied first, because it grabs the initial queryset and does not filter any
        # existing queryset.
        order_by = ['catchment_filter']
        form_helper = CollectionFilterFormHelper

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filters['connection_rate'].set_min_max()
        self.filters['collections_per_year'].set_min_max()
        self.filters['spec_waste_collected'].set_min_max()

    @staticmethod
    def catchment_filter(_, __, value):
        if value.type == 'custom':
            qs = value.inside_collections.order_by('name')
        else:
            qs = value.downstream_collections.order_by('name')
        if not qs.exists():
            qs = value.upstream_collections.order_by('name')
        return qs

    @staticmethod
    def get_seasonal_frequency(queryset, _, value):
        if value is None:
            return queryset
        if 'season_count' not in queryset.query.annotations:
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
    def filter_valid_on(qs, _, value):
        return qs.filter(Q(valid_from__lte=value), Q(valid_until__gte=value) | Q(valid_until=None))

    @staticmethod
    def get_load_features(qs, _, __):
        return qs


class WasteFlyerFilter(CrispyAutocompleteFilterSet):
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
                                  method='get_catchment')

    class Meta:
        model = WasteFlyer
        fields = ('url_valid', 'url_checked_before', 'url_checked_after', 'catchment')

    @staticmethod
    def get_catchment(qs, _, value):
        return qs.filter(collections__in=value.downstream_collections).distinct()
