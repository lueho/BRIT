from crispy_forms.helper import FormHelper
from django.contrib.auth.models import AnonymousUser
from django.forms import DecimalField, IntegerField, ModelChoiceField

from utils.forms import SimpleForm
from utils.object_management.permissions import filter_queryset_for_user

from .models import InputMaterial


class SimuCFModelForm(SimpleForm):
    reference_choices_policy_exempt = (
        "InputMaterial choices are explicitly filtered for the requesting user."
    )

    input_material = ModelChoiceField(queryset=InputMaterial.objects.all())
    amount = DecimalField(min_value=1, initial=100, label="Amount (FM) [kg]")
    length_of_treatment = IntegerField(
        min_value=1, max_value=1000, initial=30, label="Length of treatment [d]"
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        user = user or AnonymousUser()
        self.fields["input_material"].queryset = filter_queryset_for_user(
            InputMaterial.objects.all(), user
        )

    @property
    def helper(self):
        helper = FormHelper()
        helper.form_tag = False
        return helper
