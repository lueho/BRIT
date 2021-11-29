from bootstrap_modal_forms.forms import BSModalModelForm
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Field, Layout, Submit
from django.forms import ModelForm


class CustomModelForm(ModelForm):

    @property
    def helper(self):
        helper = FormHelper()
        helper.layout = Layout(
        )
        for field in self.Meta().fields:
            helper.layout.append(
                Field(field)
            )
        helper.add_input(Submit('submit', 'Save'))
        return helper


class ModalFormHelper(FormHelper):

    @property
    def form_id(self):
        return 'modal-form'


class CustomModalModelForm(BSModalModelForm):

    @property
    def helper(self):
        return ModalFormHelper()
