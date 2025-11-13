from bootstrap_modal_forms.mixins import CreateUpdateAjaxMixin, PopRequestMixin
from crispy_forms.helper import FormHelper
from django.core.exceptions import ImproperlyConfigured
from django.forms import (
    BaseFormSet,
    BaseModelFormSet,
    Form,
    ModelForm,
    ModelMultipleChoiceField,
    formset_factory,
    modelformset_factory,
)


class FormHelperMixin:
    """
    Makes it possible to provide the 'helper_class' attribute to the form's class Meta. The form will automatically
    use the provided class is the helper attribute is accessed.
    """

    helper = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if isinstance(self.helper, FormHelper):
            return  # helper already set elsewhere

        if hasattr(self, "Meta") and hasattr(self.Meta, "form_helper_class"):
            self.helper = self.Meta.form_helper_class()
        else:
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


class CreateInlineMixin:
    """
    Form mixin that causes create-inline.js to be automatically
    included whenever this form is rendered with crispy-forms.
    """

    class Media:
        js = ("js/create_inline.min.js",)


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


class BaseFormsetHelper(FormHelper):
    """Base FormHelper class for formsets.

    This abstract base helper provides common functionality for all formset helpers.
    Configure formset_type in subclasses to specify the formset behavior.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.template = "bootstrap5/formset_base.html"
        self.form_method = "post"
        self.form_tag = False
        self.formset_type = "standard"

        # Add formset_type to the helper context
        if not hasattr(self, "attrs"):
            self.attrs = {}
        self.attrs["data-formset-type"] = self.formset_type


class DynamicFormsetHelper(BaseFormsetHelper):
    """FormHelper for standard dynamic formsets.

    Renders formsets with add/remove functionality but no advanced field features.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.formset_type = "standard"


class DynamicTableInlineFormSetHelper(BaseFormsetHelper):
    """FormHelper that renders formsets as a table with add/remove buttons.

    Includes a plus button in the table footer to add additional forms as rows.
    Maintained for backward compatibility.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.template = "bootstrap5/formset_base.html"  # Use the base template directly
        self.formset_type = "standard"


class TomSelectFormsetHelper(BaseFormsetHelper):
    """FormHelper for formsets with TomSelect fields.

    Renders formsets with TomSelect autocomplete functionality and add/remove buttons.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.template = "bootstrap5/formset_tomselect.html"
        self.formset_type = "tomselect"


class M2MInlineFormSet(BaseFormSet):

    def __init__(self, *args, **kwargs):
        self.parent_object = kwargs.pop("parent_object", None)
        self.relation_field_name = kwargs.pop("relation_field_name")
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
    relation_field_name = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.form_class:
            self.model = self.form_class.Meta.model

    def get_formset(self):
        FormSet = formset_factory(
            self.formset_form_class,
            formset=self.formset_class,
            **self.formset_factory_kwargs,
        )
        return FormSet(**self.get_formset_kwargs())

    def get_formset_kwargs(self, **kwargs):
        kwargs.update(
            {
                "initial": self.get_formset_initial(),
                "relation_field_name": self.get_relation_field_name(),
            }
        )
        if self.object:
            kwargs.update({"parent_object": self.object})
        if self.request.method in ("POST", "PUT"):
            kwargs.update({"data": self.request.POST.copy()})
        return kwargs

    def get_formset_initial(self):
        if self.object:
            related_objects = getattr(self.object, self.relation_field_name).all()
            return [
                {
                    name: getattr(obj, name)
                    for name, _ in self.formset_form_class.base_fields.items()
                }
                for obj in related_objects
            ]
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
                "%(rfn)s is not a valid relational field name of model %(cls)s"
                % {"rfn": self.relation_field_name, "cls": self.model.__name__}
            )
        return self.relation_field_name

    def get_context_data(self, **kwargs):
        if "formset" not in kwargs:
            kwargs["formset"] = self.get_formset()
        kwargs["formset_helper"] = self.formset_helper_class
        return super().get_context_data(**kwargs)


class M2MInlineModelFormSet(BaseModelFormSet):

    def __init__(self, *args, **kwargs):
        self.parent_object = kwargs.pop("parent_object", None)
        self.relation_field_name = kwargs.pop("relation_field_name", None)
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
    relation_field_name = ""

    def get_formset(self, **kwargs):
        FormSet = modelformset_factory(
            self.formset_model,
            form=self.formset_form_class,
            formset=self.formset_class,
            **self.formset_factory_kwargs,
        )
        return FormSet(**self.get_formset_kwargs())

    def get_formset_kwargs(self, **kwargs):
        kwargs.update({"queryset": self.get_formset_queryset()})
        if self.object:
            kwargs.update({"parent_object": self.object})
        if self.request.method in ("POST", "PUT"):
            kwargs.update({"data": self.request.POST.copy()})
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
        if "formset" not in kwargs:
            kwargs["formset"] = self.get_formset()
            kwargs["formset_helper"] = self.get_formset_helper_class()()
        return super().get_context_data(**kwargs)


class SourcesFieldMixin:
    """
    Mixin for ModelForms that adds a sources M2M field with autocomplete widget
    and handles permission filtering.

    This mixin provides:
    1. A 'sources' field with SourceListWidget for autocomplete
    2. Automatic queryset population in __init__ based on:
       - Currently assigned sources (if editing)
       - Submitted sources (from POST data)
       - User permissions (via filter_queryset_for_user)

    Usage:
        class MyModelForm(SourcesFieldMixin, SimpleModelForm):
            class Meta:
                model = MyModel
                fields = ('name', 'sources', ...)

        # In the view, pass request to the form:
        def get_form_kwargs(self):
            kwargs = super().get_form_kwargs()
            kwargs['request'] = self.request
            return kwargs

    The mixin expects:
    - Form to be used with a model that has a 'sources' M2M relationship
    - 'sources' to be listed in Meta.fields
    - View to pass 'request' in get_form_kwargs()

    Security:
    - Filters sources by user permissions using filter_queryset_for_user()
    - Ensures users can only select published sources or sources they own
    """

    def __init__(self, *args, **kwargs):
        # Import here to avoid circular imports
        from bibliography.models import Source
        from utils.object_management.permissions import filter_queryset_for_user
        from utils.widgets import SourceListWidget

        # Capture data BEFORE calling super().__init__ (parent consumes it)
        data = kwargs.get("data")

        # DON'T pop 'request' here! PopRequestMixin (later in MRO) needs it.
        # For regular forms without PopRequestMixin, we need to pop it to avoid
        # "unexpected keyword argument" error.
        # Solution: Check if PopRequestMixin is in the MRO
        has_pop_request = any(
            cls.__name__ == 'PopRequestMixin' 
            for cls in self.__class__.__mro__
        )
        
        if not has_pop_request:
            # Regular form - pop request ourselves before super().__init__()
            request = kwargs.pop('request', None)
        else:
            # Modal form - don't pop, let PopRequestMixin handle it
            request = None

        super().__init__(*args, **kwargs)

        # If PopRequestMixin was in MRO, it set self.request
        if has_pop_request:
            request = getattr(self, 'request', None)

        # Ensure sources field exists and has proper widget
        if "sources" not in self.fields:
            return  # Field not included in this form, skip mixin logic

        # Configure the sources field
        self.fields["sources"].required = False  # Sources are optional
        
        # Set widget if not already customized
        if not isinstance(self.fields["sources"].widget, SourceListWidget):
            self.fields["sources"].widget = SourceListWidget(
                autocomplete_url="source-autocomplete",
                label_field="label"
            )

        # Always start with empty queryset (will be populated below)
        self.fields["sources"].queryset = Source.objects.none()

        # For validation, we need to include sources that:
        # 1. Are already assigned to this object (if editing)
        # 2. Are being submitted in the POST data
        # 3. Are accessible to the current user (for permission check)

        source_ids = set()

        # Add currently assigned sources
        if self.instance and self.instance.pk and hasattr(self.instance, 'sources'):
            source_ids.update(self.instance.sources.values_list("id", flat=True))

        # Add submitted sources
        if data and "sources" in data:
            submitted_ids = data.getlist("sources")
            if submitted_ids:
                source_ids.update(int(sid) for sid in submitted_ids if sid)

        # Build queryset with all relevant sources
        if source_ids:
            queryset = Source.objects.filter(id__in=source_ids)
            # Filter by user permissions if we have a user
            if request and hasattr(request, "user"):
                queryset = filter_queryset_for_user(queryset, request.user)
            self.fields["sources"].queryset = queryset
        # else: queryset is already set to Source.objects.none() above
