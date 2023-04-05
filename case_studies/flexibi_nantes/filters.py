from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Field
from django.forms import CheckboxSelectMultiple, RadioSelect
from django_filters.filters import MultipleChoiceFilter, BooleanFilter

from utils.filters import BaseCrispyFilterSet
from .models import NantesGreenhouses

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
