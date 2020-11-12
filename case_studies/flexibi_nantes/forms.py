from crispy_forms.helper import FormHelper, Layout
from crispy_forms.layout import Div, Field
from django.forms import (CheckboxSelectMultiple,
                          ChoiceField,
                          Form,
                          MultipleChoiceField,
                          RadioSelect,
                          )

from case_studies.flexibi_nantes.models import NantesGreenhouses

CROP_CHOICES = (
    (1, "Cucumber"),
    (2, "Tomato"),
)

HEATING_CHOICES = (
    (1, "All"),
    (2, "Heated"),
    (3, "Not heated")
)

LIGHTING_CHOICES = (
    (1, "All"),
    (2, "Lighting"),
    (3, "No Lighting")
)

PROD_MODE_CHOICES = (
    (1, "All"),
    (2, "On Ground"),
    (3, "Above Ground")
)

CULT_MANAGEMENT_CHOICES = (
    (1, "All"),
    (2, "Classic"),
    (3, "High-Wire")
)


class Row(Div):
    css_class = "form-row"


class NantesGreenhousesFilterForm(Form):
    crops = MultipleChoiceField(widget=CheckboxSelectMultiple, choices=CROP_CHOICES, initial=('1', '2'))
    heating = ChoiceField(widget=RadioSelect, choices=HEATING_CHOICES, initial='1')
    lighting = ChoiceField(widget=RadioSelect, choices=LIGHTING_CHOICES, initial='1')
    prod_mode = ChoiceField(widget=RadioSelect, choices=PROD_MODE_CHOICES, initial='1')
    cult_man = ChoiceField(widget=RadioSelect, choices=CULT_MANAGEMENT_CHOICES, initial='1')
    helper = FormHelper()
    helper.layout = Layout(
        Row(
            Field('heating', wrapper_class='col-md-6'),
            Field('lighting', wrapper_class='col-md-6'),
            Field('prod_mode', wrapper_class='col-md-6'),
            Field('cult_man', wrapper_class='col-md-6'),
            Field('crops', wrapper_class='col-md-12')
        )
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['heating'].label = 'Heating'
        self.fields['lighting'].label = 'Lighting'
        self.fields['prod_mode'].label = 'Production Mode'
        self.fields['cult_man'].label = 'Cultivation Management'
        helper = FormHelper()
        helper.layout = Layout(
            Row(
                Field('heating', wrapper_class='col-md-6'),
                Field('lighting', wrapper_class='col-md-6')
            )
        )

    class Meta:
        model = NantesGreenhouses
