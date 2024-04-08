from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Field
from dal import autocomplete
from django.forms import CheckboxSelectMultiple, RadioSelect
from django_filters.filters import ModelChoiceFilter, MultipleChoiceFilter, BooleanFilter

from maps.models import Catchment
from utils.filters import BaseCrispyFilterSet, CrispyAutocompleteFilterSet
from .models import Greenhouse, NantesGreenhouses

HEATING_CHOICES = (
    ('', 'All'),
    (True, 'Heated'),
    (False, 'Not heated'),
)

LIGHTING_CHOICES = (
    ('', 'All'),
    (True, 'Lighting'),
    (False, 'No lighting'),
)

ABOVE_GROUND_CHOICES = (
    ('', 'All'),
    (True, 'Above Ground'),
    (False, 'On Ground'),
)

HIGH_WIRE_CHOICES = (
    ('', 'All'),
    (True, 'High-Wire'),
    (False, 'Classic'),
)

CROP_CHOICES = (
    ('Tomato', 'Tomato'),
    ('Cucumber', 'Cucumber')
)


class GreenhouseTypeFilterFormHelper(FormHelper):
    layout = Layout(
        Row(
            Field('heated', wrapper_class='col-md-6'),
            Field('lighted', wrapper_class='col-md-6'),
            Field('above_ground', wrapper_class='col-md-6'),
            Field('high_wire', wrapper_class='col-md-6'),
        )
    )


class GreenhouseTypeFilter(BaseCrispyFilterSet):
    heated = BooleanFilter(widget=RadioSelect(choices=HEATING_CHOICES), label='Heating')
    lighted = BooleanFilter(widget=RadioSelect(choices=LIGHTING_CHOICES), label='Lighting')
    above_ground = BooleanFilter(widget=RadioSelect(choices=ABOVE_GROUND_CHOICES), label='Production mode')
    high_wire = BooleanFilter(widget=RadioSelect(choices=HIGH_WIRE_CHOICES), label='Culture management')

    class Meta:
        model = Greenhouse
        fields = ('heated', 'lighted', 'above_ground', 'high_wire')
        form_helper = GreenhouseTypeFilterFormHelper


class NantesGreenhouseFilterSetFormHelper(FormHelper):
    layout = Layout(
        Row(
            Field('catchment', wrapper_class='col-md-12'),
        ),
        Row(
            Field('heated', wrapper_class='col-md-6'),
            Field('lighted', wrapper_class='col-md-6'),
            Field('above_ground', wrapper_class='col-md-6'),
            Field('high_wire', wrapper_class='col-md-6'),
            Field('crops', wrapper_class='col-md-12')
        )
    )


class NantesGreenhousesFilterSet(CrispyAutocompleteFilterSet):
    catchment = ModelChoiceFilter(queryset=Catchment.objects.all(),
                                  widget=autocomplete.ModelSelect2(url='nantesgreenhouses-catchment-autocomplete'),
                                  method='catchment_filter',
                                  label='Catchment')
    crops = MultipleChoiceFilter(field_name='culture_1', widget=CheckboxSelectMultiple(), choices=CROP_CHOICES)
    heated = BooleanFilter(widget=RadioSelect(choices=HEATING_CHOICES), label='Heating')
    lighted = BooleanFilter(widget=RadioSelect(choices=LIGHTING_CHOICES), label='Lighting')
    above_ground = BooleanFilter(widget=RadioSelect(choices=ABOVE_GROUND_CHOICES), label='Production mode')
    high_wire = BooleanFilter(widget=RadioSelect(choices=HIGH_WIRE_CHOICES), label='Culture management')

    class Meta:
        model = NantesGreenhouses
        fields = ('catchment', 'heated', 'lighted', 'above_ground', 'high_wire', 'crops')
        form_helper = NantesGreenhouseFilterSetFormHelper

    @staticmethod
    def catchment_filter(qs, __, value):
        return qs.filter(geom__within=value.region.borders.geom)


class GreenhouseFilterFormHelper(FormHelper):
    layout = Layout(
        Row(
            Field('heated', wrapper_class='col-md-6'),
            Field('lighted', wrapper_class='col-md-6'),
            Field('above_ground', wrapper_class='col-md-6'),
            Field('high_wire', wrapper_class='col-md-6'),
            Field('crops', wrapper_class='col-md-12')
        )
    )


class GreenhouseFilter(BaseCrispyFilterSet):
    crops = MultipleChoiceFilter(field_name='culture_1', widget=CheckboxSelectMultiple(), choices=CROP_CHOICES)
    heated = BooleanFilter(widget=RadioSelect(choices=HEATING_CHOICES), label='Heating')
    lighted = BooleanFilter(widget=RadioSelect(choices=LIGHTING_CHOICES), label='Lighting')
    above_ground = BooleanFilter(widget=RadioSelect(choices=ABOVE_GROUND_CHOICES), label='Production mode')
    high_wire = BooleanFilter(widget=RadioSelect(choices=HIGH_WIRE_CHOICES), label='Culture management')

    class Meta:
        model = NantesGreenhouses
        fields = ('heated', 'lighted', 'above_ground', 'high_wire', 'crops')
        form_helper = GreenhouseFilterFormHelper
