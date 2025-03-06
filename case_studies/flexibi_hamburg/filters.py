from crispy_forms.helper import FormHelper
from crispy_forms.layout import Field, Layout
from django.db.models import Max, Min
from django.forms import CheckboxSelectMultiple
from django_filters.filters import ModelChoiceFilter, MultipleChoiceFilter

from maps.models import Catchment
from utils.crispy_fields import RangeSliderField
from utils.filters import CrispyAutocompleteFilterSet, NullableRangeFilter
from utils.widgets import BSModelSelect2, NullableRangeSliderWidget
from .models import HamburgRoadsideTrees

GATTUNG_CHOICES = (
    ('Linde', 'Linden'),
    ('Eiche', 'Oak'),
    ('Ahorn', 'Maple'),
    ('Other', 'Other')
)

BEZIRK_CHOICES = (
    ('Harburg', 'Harburg'),
    ('Altona', 'Altona'),
    ('Bergedorf', 'Bergedorf'),
    ('Hamburg-Mitte', 'Hamburg-Mitte'),
    ('Hamburg-Nord', 'Hamburg-Nord'),
    ('Eimsbüttel', 'Eimsbüttel'),
    ('Wandsbek', 'Wandsbek')
)


class HamburgRoadsideTreeFilterFormHelper(FormHelper):
    layout = Layout(
        Field('catchment'),
        Field('gattung_deutsch'),
        RangeSliderField('plantation_year'),
        RangeSliderField('stem_circumference'),
    )


class PlantationYearFilter(NullableRangeFilter):
    def set_min_max(self):
        self.range_min = HamburgRoadsideTrees.objects.all().aggregate(min_year=Min('pflanzjahr'))['min_year']
        self.range_max = HamburgRoadsideTrees.objects.all().aggregate(max_year=Max('pflanzjahr'))['max_year']
        self.default_range_min = 1500
        self.default_range_max = 2025
        self.extra['widget'] = NullableRangeSliderWidget(attrs={
            'data-range_min': self.range_min,
            'data-range_max': self.range_max,
            'data-step': self.default_range_step,
            'data-is_null': self.default_include_null,
            'data-unit': ''
        })


class StemCircumferenceFilter(NullableRangeFilter):
    def set_min_max(self):
        self.range_min = HamburgRoadsideTrees.objects.all().aggregate(min_circ=Min('stammumfang'))['min_circ']
        self.range_max = HamburgRoadsideTrees.objects.all().aggregate(max_circ=Max('stammumfang'))['max_circ']
        self.default_range_min = 1
        self.default_range_max = 300
        self.extra['widget'] = NullableRangeSliderWidget(attrs={
            'data-range_min': self.range_min,
            'data-range_max': self.range_max,
            'data-step': self.default_range_step,
            'data-is_null': self.default_include_null,
            'data-unit': ''
        })


class HamburgRoadsideTreesFilterSet(CrispyAutocompleteFilterSet):
    catchment = ModelChoiceFilter(queryset=Catchment.objects.all(),
                                  widget=BSModelSelect2(url='hamburgroadsidetrees-catchment-autocomplete'),
                                  method='catchment_filter',
                                  label='Catchment')
    gattung_deutsch = MultipleChoiceFilter(widget=CheckboxSelectMultiple, choices=GATTUNG_CHOICES, label='Tree genus',
                                           method='filter_genus')
    plantation_year = PlantationYearFilter(field_name='pflanzjahr', label='Plantation year')
    stem_circumference = StemCircumferenceFilter(field_name='stammumfang', label='Stem circumference [cm]')

    class Meta:
        model = HamburgRoadsideTrees
        fields = ('catchment', 'gattung_deutsch', 'plantation_year', 'stem_circumference')

        form_helper = HamburgRoadsideTreeFilterFormHelper

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filters['plantation_year'].set_min_max()
        self.filters['stem_circumference'].set_min_max()

    @staticmethod
    def catchment_filter(qs, __, value):
        return qs.filter(geom__within=value.region.borders.geom)

    @staticmethod
    def filter_genus(qs, _, value):
        if 'Other' in value:
            qs = qs.exclude(gattung_deutsch__in=[choice[0] for choice in GATTUNG_CHOICES if choice[0] not in value])
        else:
            qs = qs.filter(gattung_deutsch__in=value)
        return qs
