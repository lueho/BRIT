from crispy_forms.helper import FormHelper
from dal_select2.widgets import Select2WidgetMixin
from django_filters import FilterSet


class SimpleFilterSet(FilterSet):

    def get_form_helper(self):
        if hasattr(self.Meta, 'form_helper'):
            return self.Meta.form_helper()
        else:
            return FormHelper()

    @property
    def form(self):
        form = super().form
        if not hasattr(form, 'helper'):
            form.helper = self.get_form_helper()
        form.helper.form_tag = False
        return form


class AutocompleteFilterSet(SimpleFilterSet):

    @property
    def form(self):
        form = super().form
        form.helper.include_media = False
        for name, field in form.fields.items():
            if isinstance(field.widget, Select2WidgetMixin):
                field.widget.attrs = {'data-theme': 'bootstrap4'}
        return form
