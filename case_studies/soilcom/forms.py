from bootstrap_modal_forms.forms import BSModalModelForm, BSModalForm
from crispy_forms.helper import FormHelper

from . import models


class ModalFormHelper(FormHelper):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_id = 'modal-form'


class CollectorModelForm(BSModalModelForm):
    class Meta:
        model = models.Collector
        fields = ('name', 'description')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = ModalFormHelper()
