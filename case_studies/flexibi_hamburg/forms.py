from crispy_forms.helper import FormHelper
from crispy_forms.layout import Field, Layout

from utils.forms import SimpleForm


# from django_filters.fields import RangeField


class TreeFilterForm(SimpleForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.helper = FormHelper(self)
        self.helper.form_method = 'get'
        layout_fields = []
        for field_name, field in self.fields.items():
            layout_field = Field(field_name)
            layout_fields.append(layout_field)
        self.helper.layout = Layout(*layout_fields)
