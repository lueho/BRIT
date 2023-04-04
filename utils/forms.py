from bootstrap_modal_forms.mixins import CreateUpdateAjaxMixin, PopRequestMixin
from crispy_forms.helper import FormHelper
from dal_select2.widgets import Select2WidgetMixin
from django.core.exceptions import ImproperlyConfigured
from django.forms import BaseFormSet, BaseModelFormSet, Form, formset_factory, ModelForm, modelformset_factory

from .models import Property, Unit


class FormHelperMixin:
    """
    Makes it possible to provide the 'helper_class' attribute to the form's class Meta. The form will automatically
    use the provided class is the helper attribute is accessed.
    """

    helper = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not isinstance(self.helper, FormHelper):
            if hasattr(self, 'Meta'):
                if hasattr(self.Meta, 'helper_class'):
                    self.helper = self.Meta.helper_class()
                    return self.helper
            self.helper = FormHelper()


class NoFormTagMixin(FormHelperMixin):
    """
    Removes the form tag without blocking the helper property in subclasses of the respective forms. I.e. helpers
    can be added to subclassed forms without the need to super any helper from the base class. Form tags must
    be added manually to the templates when using this mixin.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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

        # django-crispy-forms and django-autocomplete-light conflict in the order JQuery needs to be loaded.
        # Suppressing media inclusion here and explicitly adding {{ form.media }} in the template solves this.
        # See https://github.com/yourlabs/django-autocomplete-light/issues/788
        self.helper.include_media = False

        for name, field in self.fields.items():
            if isinstance(field.widget, Select2WidgetMixin):
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


class M2MInlineFormSet(BaseFormSet):

    def __init__(self, *args, **kwargs):
        self.parent_object = kwargs.pop('parent_object', None)
        self.relation_field_name = kwargs.pop('relation_field_name')
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        child_objects = []
        for form in self.forms:
            child = form.save()
            if child:
                child_objects.append(child)
        getattr(self.parent_object, self.relation_field_name).set(child_objects)
        return child_objects


class M2MInlineFormSetMixin:
    """
    Mixin for class-based views based on ModelFormView. Allows to add one additional ModelFormSet to the view.
    """
    object = None
    form_class = None
    formset_model = None
    formset_class = None
    formset_form_class = None
    formset_helper_class = None
    formset_factory_kwargs = {}
    relation_field_name = ''

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.form_class:
            self.model = self.form_class.Meta.model

    def get_formset(self):
        FormSet = formset_factory(
            self.formset_form_class,
            formset=self.formset_class,
            **self.formset_factory_kwargs
        )
        return FormSet(**self.get_formset_kwargs())

    def get_formset_kwargs(self, **kwargs):
        kwargs.update({
            'initial': self.get_formset_initial(),
            'relation_field_name': self.get_relation_field_name()
        })
        if self.object:
            kwargs.update({'parent_object': self.object})
        if self.request.method in ("POST", "PUT"):
            kwargs.update({'data': self.request.POST.copy()})
        return kwargs

    def get_formset_initial(self):
        if self.object:
            related_objects = getattr(self.object, self.relation_field_name).all()
            return [{name: getattr(obj, name) for name, _ in self.formset_form_class.base_fields.items()} for obj in related_objects]
        else:
            return []

    def get_formset_helper_class(self):
        if self.formset_helper_class:
            return self.formset_helper_class
        else:
            return FormHelper

    def get_relation_field_name(self):
        if not hasattr(self.model, self.relation_field_name):
            raise ImproperlyConfigured(
                '%(rfn)s is not a valid relational field name of model %(cls)s'
                % {'rfn': self.relation_field_name, 'cls': self.model.__name__}
            )
        return self.relation_field_name

    def get_context_data(self, **kwargs):
        if 'formset' not in kwargs:
            kwargs['formset'] = self.get_formset()
        kwargs['formset_helper'] = self.formset_helper_class
        return super().get_context_data(**kwargs)


class M2MInlineModelFormSet(BaseModelFormSet):

    def __init__(self, *args, **kwargs):
        self.parent_object = kwargs.pop('parent_object', None)
        self.relation_field_name = kwargs.pop('relation_field_name', None)
        super().__init__(*args, **kwargs)


class M2MInlineModelFormSetMixin:
    """
    Mixin for class-based views based on ModelFormView. Allows to add one additional ModelFormSet to the view.
    """
    object = None
    formset_model = None
    formset_class = M2MInlineModelFormSet
    formset_form_class = SimpleModelForm
    formset_factory_kwargs = {}
    formset_helper_class = None
    relation_field_name = ''

    def get_formset(self, **kwargs):
        FormSet = modelformset_factory(
            self.formset_model,
            form=self.formset_form_class,
            formset=self.formset_class,
            **self.formset_factory_kwargs
        )
        return FormSet(**self.get_formset_kwargs())

    def get_formset_kwargs(self, **kwargs):
        kwargs.update({'queryset': self.get_formset_queryset()})
        if self.object:
            kwargs.update({'parent_object': self.object})
        if self.request.method in ("POST", "PUT"):
            kwargs.update({'data': self.request.POST.copy()})
        return kwargs

    def get_formset_queryset(self):
        if not self.object:
            return self.formset_model.objects.none()
        if not hasattr(self.object, self.relation_field_name):
            raise ImproperlyConfigured(
                "The field that relates the provided model of the main form to the related model"
                "of the formset must be provided as property 'related_field_name' and valid. "
            )
        return getattr(self.object, self.relation_field_name).all()

    def get_formset_helper_class(self):
        if self.formset_helper_class:
            return self.formset_helper_class
        else:
            return self.formset_class.helper

    def get_context_data(self, **kwargs):
        if 'formset' not in kwargs:
            kwargs['formset'] = self.get_formset()
            kwargs['formset_helper'] = self.get_formset_helper_class()()
        return super().get_context_data(**kwargs)


class UnitModelForm(SimpleModelForm):
    class Meta:
        model = Unit
        fields = ['name', 'dimensionless', 'reference_quantity', 'description']


class PropertyModelForm(SimpleModelForm):
    class Meta:
        model = Property
        fields = ['name', 'allowed_units', 'description']
