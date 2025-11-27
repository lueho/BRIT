from bootstrap_modal_forms.mixins import CreateUpdateAjaxMixin, PopRequestMixin
from crispy_forms.helper import FormHelper
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.forms import (
    BaseFormSet,
    BaseModelFormSet,
    Form,
    ModelForm,
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
                f"{self.relation_field_name} is not a valid relational field name of model {self.model.__name__}"
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


class UserCreatedObjectFormMixin:
    """
    Mixin that validates all UserCreatedObject references in the form have
    proper permissions for the current user.

    This provides centralized, consistent permission checking for all fields
    that reference UserCreatedObject models (single or M2M), preventing users
    from POSTing IDs of objects they don't have access to.

    Usage:
        class MyModelForm(UserCreatedObjectFormMixin, SimpleModelForm):
            # Your fields...
            class Meta:
                model = MyModel
                fields = (...)

        # In the view:
        def get_form_kwargs(self):
            kwargs = super().get_form_kwargs()
            kwargs['request'] = self.request
            return kwargs

    Security:
    - Validates at form.clean() time (backend validation)
    - Complements autocomplete filtering (frontend UX)
    - Prevents bypass via browser devtools or direct POST
    - Works with both single (ForeignKey) and multiple (M2M) relationships

    The mixin expects:
    - Form to be used with a view that passes 'request' in get_form_kwargs()
    - Will validate any field containing UserCreatedObject instances
    """

    def __init__(self, *args, **kwargs):
        """Capture request and adjust UserCreatedObject field querysets."""
        from django.forms import ModelChoiceField, ModelMultipleChoiceField

        from utils.object_management.models import UserCreatedObject

        # Capture request for permission validation in clean()
        # Only pop request if PopRequestMixin is NOT in the MRO (it will pop it itself)
        has_pop_request_mixin = any(
            cls.__name__ == "PopRequestMixin" for cls in self.__class__.__mro__
        )

        if not has_pop_request_mixin:
            # Pop it ourselves if PopRequestMixin isn't present
            request = kwargs.pop("request", None)
            if request:
                self.request = request
            elif not hasattr(self, "request"):
                self.request = None

        # Get data before super().__init__ consumes it
        data = kwargs.get("data")

        super().__init__(*args, **kwargs)

        # If PopRequestMixin is in the MRO, it has already set self.request during super().__init__()

        # After fields are initialized, adjust querysets for all UserCreatedObject fields
        # to include submitted values (prevents Django field validation from rejecting
        # them before our clean() method can run permission checks)
        if data:
            for field_name, field in self.fields.items():
                # Only process ModelChoiceField and ModelMultipleChoiceField
                if not isinstance(field, ModelChoiceField | ModelMultipleChoiceField):
                    continue

                # Get the model from the queryset
                # Even TomSelect fields should have queryset initialized by now
                try:
                    if field.queryset is None:
                        # Some fields may have None queryset - skip them
                        continue
                    model = field.queryset.model
                except (AttributeError, TypeError):
                    continue

                # Check if this field references UserCreatedObject
                try:
                    if not issubclass(model, UserCreatedObject):
                        continue
                except TypeError:
                    continue

                # Collect submitted IDs for this field
                submitted_ids = set()

                # Handle both single and multiple choice fields
                if field_name in data:
                    values = (
                        data.getlist(field_name)
                        if hasattr(data, "getlist")
                        else [data.get(field_name)]
                    )
                    for val in values:
                        if val:
                            try:
                                submitted_ids.add(int(val))
                            except (ValueError, TypeError):
                                pass

                # Collect existing IDs (for update forms)
                existing_ids = set()
                if self.instance and self.instance.pk:
                    if hasattr(self.instance, field_name):
                        attr = getattr(self.instance, field_name)
                        if hasattr(attr, "all"):  # M2M field
                            existing_ids.update(attr.values_list("pk", flat=True))
                        elif hasattr(attr, "pk"):  # FK field
                            existing_ids.add(attr.pk)

                # Expand queryset to include all relevant IDs
                all_ids = submitted_ids | existing_ids
                if all_ids:
                    field.queryset = model.objects.filter(pk__in=all_ids)

    def clean(self):
        """
        Validate that all UserCreatedObject references are accessible to the user.
        Raises ValidationError if user tries to reference objects they can't access.
        """
        from utils.object_management.models import UserCreatedObject
        from utils.object_management.permissions import filter_queryset_for_user

        cleaned_data = super().clean()
        request = getattr(self, "request", None)

        # Skip validation if no request (shouldn't happen in normal usage)
        if not request or not hasattr(request, "user"):
            return cleaned_data

        # Check all fields for UserCreatedObject references
        for field_name, value in cleaned_data.items():
            if value is None:
                continue

            # Handle both single objects and iterables (M2M, multiple choice)
            objects_to_check = []
            if hasattr(value, "__iter__") and not isinstance(value, str | bytes):
                # M2M or multiple choice field
                objects_to_check = list(value)
            else:
                # Single object (ForeignKey, OneToOne)
                objects_to_check = [value]

            # Validate each object
            for obj in objects_to_check:
                if not isinstance(obj, UserCreatedObject):
                    continue

                # Use existing permission system to check access
                filtered_qs = filter_queryset_for_user(
                    obj.__class__.objects.filter(pk=obj.pk), request.user
                )

                if not filtered_qs.exists():
                    # User doesn't have permission to access this object
                    raise ValidationError(
                        {
                            field_name: (
                                f"You don't have permission to access the selected "
                                f"{obj.__class__._meta.verbose_name}: {obj}"
                            )
                        },
                        code="permission_denied",
                    )

        return cleaned_data


class SourcesFieldMixin:
    """
    Mixin for ModelForms that adds a sources M2M field with SourceListWidget.

    This mixin handles:
    1. Automatic widget setup (SourceListWidget with autocomplete)
    2. Queryset population for validation (assigned + submitted sources)
    3. Makes sources field optional by default

    Note: Permission validation is handled by UserCreatedObjectFormMixin.clean()
    This mixin only needs to ensure submitted/assigned sources are in the queryset
    so Django's validation doesn't reject them before our permission check runs.

    Usage:
        class MyModelForm(UserCreatedObjectFormMixin, SourcesFieldMixin, SimpleModelForm):
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
    - View to pass 'request' in get_form_kwargs() (for UserCreatedObjectFormMixin)
    """

    def __init__(self, *args, **kwargs):
        # Import here to avoid circular imports
        from bibliography.models import Source
        from utils.widgets import SourceListWidget

        # Capture data BEFORE calling super().__init__ (parent consumes it)
        data = kwargs.get("data")

        # DON'T pop 'request' if another mixin already handles it
        # Check if PopRequestMixin or UserCreatedObjectFormMixin is in the MRO
        has_request_handler = any(
            cls.__name__ in ("PopRequestMixin", "UserCreatedObjectFormMixin")
            for cls in self.__class__.__mro__
        )

        if not has_request_handler:
            # Regular form - pop request ourselves before super().__init__()
            kwargs.pop("request", None)

        super().__init__(*args, **kwargs)

        # Ensure sources field exists and has proper widget
        if "sources" not in self.fields:
            return  # Field not included in this form, skip mixin logic

        # Configure the sources field
        self.fields["sources"].required = False  # Sources are optional

        # Set widget if not already customized
        if not isinstance(self.fields["sources"].widget, SourceListWidget):
            self.fields["sources"].widget = SourceListWidget(
                autocomplete_url="source-autocomplete", label_field="label"
            )

        # Populate queryset with assigned + submitted sources for validation
        # Permission check happens in UserCreatedObjectFormMixin.clean()
        source_ids = set()

        # Add currently assigned sources
        if self.instance and self.instance.pk and hasattr(self.instance, "sources"):
            source_ids.update(self.instance.sources.values_list("id", flat=True))

        # Add submitted sources (from POST data)
        if data and "sources" in data:
            submitted_ids = data.getlist("sources")
            if submitted_ids:
                source_ids.update(int(sid) for sid in submitted_ids if sid)

        # Set queryset to include all relevant sources (permission check in clean())
        if source_ids:
            self.fields["sources"].queryset = Source.objects.filter(id__in=source_ids)
        else:
            self.fields["sources"].queryset = Source.objects.none()
