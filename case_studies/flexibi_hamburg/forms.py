from crispy_forms.helper import FormHelper
from crispy_forms.layout import Field, Layout
from django import forms
from django_filters.fields import RangeField


class TreeFilterForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_method = 'get'
        layout_fields = []
        for field_name, field in self.fields.items():
            if isinstance(field, RangeField):
                layout_field = Field(field_name, template="range-slider.html")
            else:
                layout_field = Field(field_name)
            layout_fields.append(layout_field)
        self.helper.layout = Layout(*layout_fields)
