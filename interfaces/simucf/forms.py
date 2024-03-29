from crispy_forms.helper import FormHelper
from django.forms import ModelChoiceField, DecimalField, IntegerField

from utils.forms import SimpleForm

from .models import InputMaterial


class SimuCFModelForm(SimpleForm):
    input_material = ModelChoiceField(queryset=InputMaterial.objects.all())
    amount = DecimalField(min_value=1, initial=100, label='Amount (FM) [kg]')
    length_of_treatment = IntegerField(min_value=1, max_value=1000, initial=30, label='Length of treatment [d]')

    @property
    def helper(self):
        helper = FormHelper()
        helper.form_tag = False
        return helper
