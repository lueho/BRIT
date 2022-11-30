from bootstrap_modal_forms.mixins import CreateUpdateAjaxMixin, PopRequestMixin
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Field
from django.forms import Form, ModelForm, modelformset_factory


class NoFormTagMixin:
    """
    Removes the form tag without blocking the helper property in subclasses of the respective forms. I.e. helpers
    can be added to subclassed forms without the need to super any helper from the base class. Form tags must
    be added manually to the templates when using this mixin.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not hasattr(self, 'helper'):
            self.helper = FormHelper()

        self.helper.form_tag = False


class ModalFormMixin(NoFormTagMixin, PopRequestMixin):
    """
    Mixin that utilizes the django-bootstrap-modal-forms package to make regular forms usable in bootstrap modal forms.
    Use only with django's Form class. For the same effect on the ModalForm class, use ModalModelFormMixin, instead.
    """


class ModalModelFormMixin(NoFormTagMixin, PopRequestMixin, CreateUpdateAjaxMixin):
    """
    Mixin that utilizes the django-bootstrap-modal-forms package to make regular forms usable in bootstrap modal forms.
    Use only with ModelForm class. For the same effect on the regular Form class, use ModalModelFormMixin, instead.
    """


class SimpleForm(NoFormTagMixin, Form):
    """
    The regular django Form just without form tags by default.
    """


class SimpleModelForm(NoFormTagMixin, ModelForm):
    """
    The regular django ModelForm just without form tags by default.
    """


class ModalForm(ModalFormMixin, Form):
    """
    Form that can be used within bootstrap modals. Makes use of the django-boostrap-modal-forms package.
    """


class ModalModelForm(ModalModelFormMixin, ModelForm):
    """
    ModelForm that can be used within bootstrap modals. Makes use of the django-boostrap-modal-forms package.
    """


class AutoCompleteMixin:
    """
    Allows the integration of django-autocomplete-light with django-crispy-forms and bootstrap 4. When using this
    mixin, form media need to be manually loaded in the template using {{ form.media }}.
    """
    fields: dict

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not hasattr(self, 'helper'):
            self.helper = FormHelper()

        # django-crispy-forms and django-autocomplete-light conflict in the order JQuery needs to be loaded.
        # Suppressing media inclusion here and explicitly adding {{ form.media }} in the template solves this.
        # See https://github.com/yourlabs/django-autocomplete-light/issues/788
        self.helper.include_media = False

        for name, field in self.fields.items():
            field.widget.attrs = {'data-theme': 'bootstrap4'}


class AutoCompleteForm(AutoCompleteMixin, SimpleForm):
    """
    Form that works with django-autocomplete-light in combination with bootstrap 4.
    """


class AutoCompleteModelForm(AutoCompleteMixin, SimpleModelForm):
    """
    Model form that works with django-autocomplete-light in combination with bootstrap 4.
    """


class AutoCompleteModalModelForm(AutoCompleteMixin, ModalModelForm):
    """
    Model form that works with django-autocomplete-light in combination with bootstrap 4 and
    django-bootstrap-modal-forms.
    """


class DynamicTableInlineFormSetHelper(FormHelper):
    """
    Formhelper that is used to render Formsets as table that includes a plus button in the table footer to add
    additional forms as rows.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.template = 'bootstrap4/dynamic_table_inline_formset.html'
        self.form_method = 'post'
        self.form_tag = False


class ForeignkeyField(Field):
    """
    Similar to a ModelChoiceField. Additional to the model choice by dropdown, this adds a plus symbol next to the field
    as a shortcut to create a new model though a modal form.
    """
    template = 'foreignkey-field.html'


class M2MInlineModelFormSetMixin:
    """
    Mixin for class-based views based on ModelFormView. Allows to add one additional ModelFormSet to the view.
    """
    object = None
    formset_model = None
    formset_class = None
    formset_form_class = None
    formset_helper_class = None

    def get_parent_object(self):
        return self.object

    def get_formset(self, **kwargs):
        FormSet = modelformset_factory(
            self.formset_model,
            form=self.formset_form_class,
            formset=self.formset_class
        )
        return FormSet(**self.get_formset_kwargs())

    def get_formset_kwargs(self, **kwargs):
        kwargs.update({'parent_object': self.get_parent_object()})
        kwargs.update({'initial': self.get_formset_initial()})
        if self.request.method in ("POST", "PUT"):
            kwargs.update({'data': self.request.POST.copy()})
        return kwargs

    def get_formset_initial(self):
        flyers = self.object.flyers.all() if self.object else []
        initial = [{'url': flyer.url} for flyer in flyers]
        return initial

    def get_context_data(self, **kwargs):
        if 'formset' not in kwargs:
            kwargs['formset'] = self.get_formset()
        kwargs['formset_helper'] = self.formset_helper_class()
        return super().get_context_data(**kwargs)
