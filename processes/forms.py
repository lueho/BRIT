"""Forms for the processes module following shared BRIT conventions."""

import types

from crispy_forms.layout import HTML, Div, Field, Layout
from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.forms import BaseInlineFormSet, inlineformset_factory
from django_tomselect.app_settings import TomSelectConfig
from django_tomselect.forms import (
    TomSelectModelChoiceField,
    TomSelectModelMultipleChoiceField,
)
from extra_views import InlineFormSetFactory

from bibliography.models import Author, Source
from materials.models import Material
from utils.forms import (
    DynamicTableInlineFormSetHelper,
    ModalModelFormMixin,
    SimpleModelForm,
)
from utils.properties.models import Unit

from .models import (
    Process,
    ProcessAuthor,
    ProcessCategory,
    ProcessInfoResource,
    ProcessLink,
    ProcessMaterial,
    ProcessOperatingParameter,
    ProcessSource,
)


def image_metadata_section():
    return Div(
        HTML(
            '<div class="card-header bg-body-tertiary">'
            '<h6 class="mb-0">Image details</h6>'
            '<div class="form-text mb-0">'
            "Alt text, caption, and rights notice belong to the uploaded image."
            "</div>"
            "</div>"
        ),
        Div(
            Field("image"),
            Field("image_alt_text"),
            Field("image_caption"),
            Field("image_rights_notice"),
            css_class="card-body",
        ),
        css_class="card border mb-3",
    )


def queryset_valid_value(self, value):
    """Validate TomSelect values against the configured queryset."""

    return self.queryset.filter(pk=value).exists()


def queryset_check_values(self, value):
    """Check TomSelect multiple values against the configured queryset."""

    if isinstance(value, list | tuple):
        pks = [v for v in value if v]
        return list(self.queryset.filter(pk__in=pks))
    return []


class QuerysetTomSelectModelChoiceField(TomSelectModelChoiceField):
    """TomSelect field that validates submitted pks against its queryset."""

    def clean(self, value):
        if value in self.empty_values:
            if self.required:
                raise ValidationError(self.error_messages["required"], code="required")
            return None

        try:
            key = self.to_field_name or "pk"
            return self.queryset.get(**{key: value})
        except (TypeError, ValueError, self.queryset.model.DoesNotExist) as exc:
            raise ValidationError(
                self.error_messages["invalid_choice"],
                code="invalid_choice",
                params={"value": value},
            ) from exc


# ==============================================================================
# ProcessCategory Forms
# ==============================================================================


class ProcessCategoryModelForm(SimpleModelForm):
    class Meta:
        model = ProcessCategory
        fields = ("name", "description", "supplementary_document")


class ProcessCategoryModalModelForm(ModalModelFormMixin, ProcessCategoryModelForm):
    pass


# ==============================================================================
# Process Forms
# ==============================================================================


class ProcessModelForm(SimpleModelForm):
    # Note: When config with URL is provided, TomSelect validates via the autocomplete
    # endpoint. For proper queryset validation in forms, we override in __init__.
    parent = TomSelectModelChoiceField(
        queryset=Process.objects.all(),
        required=False,
        config=TomSelectConfig(url="processes:process-autocomplete"),
        label="Parent process",
    )
    categories = TomSelectModelMultipleChoiceField(
        queryset=ProcessCategory.objects.all(),
        required=False,
        config=TomSelectConfig(url="processes:processcategory-autocomplete"),
        label="Categories",
    )

    class Meta:
        model = Process
        fields = (
            "name",
            "parent",
            "categories",
            "short_description",
            "mechanism",
            "description",
            "process_technology",
            "image",
            "image_alt_text",
            "image_caption",
            "image_rights_notice",
            "supplementary_document",
        )
        widgets = {
            "short_description": forms.Textarea(attrs={"rows": 2}),
            "description": forms.Textarea(attrs={"rows": 6}),
            "process_technology": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Override TomSelect field validation to use queryset instead of URL endpoint
        # This fixes form validation in tests while maintaining autocomplete in production
        for field_name in ["parent", "categories"]:
            field = self.fields[field_name]

            # Bind methods to the field instance
            field.valid_value = types.MethodType(queryset_valid_value, field)
            if hasattr(field, "_check_values"):
                field._check_values = types.MethodType(queryset_check_values, field)
        self.helper.layout = Layout(
            "name",
            "parent",
            "categories",
            "short_description",
            "mechanism",
            "description",
            "process_technology",
            image_metadata_section(),
            "supplementary_document",
        )


class ProcessModalModelForm(ModalModelFormMixin, ProcessModelForm):
    class Meta(ProcessModelForm.Meta):
        fields = ("name", "categories", "short_description")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.layout = Layout("name", "categories", "short_description")


# ==============================================================================
# Inline form helpers
# ==============================================================================


class OrderedUniqueInlineFormSet(BaseInlineFormSet):
    related_field_name = None
    position_field_name = "position"
    duplicate_message = "Each item can only be added once."

    def clean(self):
        super().clean()
        if any(self.errors):
            return

        seen = []
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get("DELETE", False):
                related_object = form.cleaned_data.get(self.related_field_name)
                if related_object:
                    if related_object in seen:
                        raise ValidationError(self.duplicate_message)
                    seen.append(related_object)

    def save(self, commit=True):
        with transaction.atomic():
            valid_forms = [
                form
                for form in self.forms
                if form.cleaned_data
                and not form.cleaned_data.get("DELETE", False)
                and form.cleaned_data.get(self.related_field_name)
            ]

            if not commit:
                return [form.save(commit=False) for form in valid_forms]

            saved_objects = []
            for position, form in enumerate(valid_forms, 1):
                setattr(form.instance, self.position_field_name, position)
                saved_objects.append(form.save(commit=True))

            for form in self.forms:
                if (
                    form.cleaned_data
                    and form.cleaned_data.get("DELETE", False)
                    and form.instance.pk
                ):
                    form.instance.delete()

            self._normalize_positions()
            return saved_objects

    def _normalize_positions(self):
        if not self.instance.pk:
            return

        related_manager = getattr(
            self.instance, self.fk.remote_field.get_accessor_name()
        )
        objects = list(related_manager.all().order_by(self.position_field_name, "id"))
        for position, obj in enumerate(objects, 1):
            if getattr(obj, self.position_field_name) != position:
                setattr(obj, self.position_field_name, position)
                obj.save(update_fields=[self.position_field_name])


class ProcessAuthorInlineForm(forms.ModelForm):
    author = QuerysetTomSelectModelChoiceField(
        queryset=Author.objects.all(),
        config=TomSelectConfig(
            url="author-autocomplete",
            label_field="label",
        ),
        label="Author",
    )

    class Meta:
        model = ProcessAuthor
        fields = ("author",)


class ProcessAuthorFormSet(OrderedUniqueInlineFormSet):
    related_field_name = "author"
    position_field_name = "position"
    duplicate_message = "Each author can only be added once."


class ProcessAuthorInline(InlineFormSetFactory):
    model = ProcessAuthor
    form_class = ProcessAuthorInlineForm
    formset_class = ProcessAuthorFormSet
    factory_kwargs = {"extra": 1, "can_delete": True}
    formset_helper_class = DynamicTableInlineFormSetHelper


class ProcessSourceInlineForm(forms.ModelForm):
    source = QuerysetTomSelectModelChoiceField(
        queryset=Source.objects.filter(publication_status="published"),
        config=TomSelectConfig(
            url="source-autocomplete",
            label_field="label",
        ),
        label="Source",
    )

    class Meta:
        model = ProcessSource
        fields = ("source",)

    def __init__(self, *args, **kwargs):
        request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        if request and hasattr(request, "user"):
            from utils.object_management.permissions import filter_queryset_for_user

            qs = filter_queryset_for_user(Source.objects.all(), request.user)
            if self.instance and self.instance.pk and self.instance.source_id:
                qs = qs | Source.objects.filter(pk=self.instance.source_id)
            self.fields["source"].queryset = qs


class ProcessSourceFormSet(OrderedUniqueInlineFormSet):
    related_field_name = "source"
    position_field_name = "order"
    duplicate_message = "Each source can only be added once."


class ProcessSourceInline(InlineFormSetFactory):
    model = ProcessSource
    form_class = ProcessSourceInlineForm
    formset_class = ProcessSourceFormSet
    factory_kwargs = {"extra": 1, "can_delete": True}
    formset_helper_class = DynamicTableInlineFormSetHelper

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs


class ProcessMaterialInlineForm(forms.ModelForm):
    material = TomSelectModelChoiceField(
        queryset=Material.objects.filter(publication_status="published"),
        config=TomSelectConfig(
            url="material-autocomplete",
            label_field="name",
        ),
        label="Material",
    )
    quantity_unit = TomSelectModelChoiceField(
        queryset=Unit.objects.filter(publication_status="published"),
        required=False,
        config=TomSelectConfig(
            url="unit-autocomplete",
            label_field="name",
        ),
        label="Quantity Unit",
    )

    class Meta:
        model = ProcessMaterial
        fields = (
            "material",
            "role",
            "order",
            "stage",
            "stream_label",
            "quantity_value",
            "quantity_unit",
            "notes",
            "optional",
        )
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}


class ProcessMaterialInline(InlineFormSetFactory):
    model = ProcessMaterial
    form_class = ProcessMaterialInlineForm
    factory_kwargs = {"extra": 1, "can_delete": True}
    formset_helper_class = DynamicTableInlineFormSetHelper


def build_process_material_formset(**kwargs):
    """Return the inline formset class used for process materials."""

    return inlineformset_factory(
        Process,
        ProcessMaterial,
        form=ProcessMaterialInlineForm,
        extra=1,
        can_delete=True,
        **kwargs,
    )


class ProcessOperatingParameterInlineForm(forms.ModelForm):
    unit = TomSelectModelChoiceField(
        queryset=Unit.objects.filter(publication_status="published"),
        required=False,
        config=TomSelectConfig(
            url="unit-autocomplete",
            label_field="name",
        ),
        label="Unit",
    )

    class Meta:
        model = ProcessOperatingParameter
        fields = (
            "parameter",
            "name",
            "unit",
            "value_min",
            "value_max",
            "nominal_value",
            "basis",
            "notes",
            "order",
        )
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}


class ProcessOperatingParameterInline(InlineFormSetFactory):
    model = ProcessOperatingParameter
    form_class = ProcessOperatingParameterInlineForm
    factory_kwargs = {"extra": 1, "can_delete": True}
    formset_helper_class = DynamicTableInlineFormSetHelper


def build_process_operating_parameter_formset(**kwargs):
    """Return the inline formset class used for process operating parameters."""

    return inlineformset_factory(
        Process,
        ProcessOperatingParameter,
        form=ProcessOperatingParameterInlineForm,
        extra=1,
        can_delete=True,
        **kwargs,
    )


class ProcessLinkInline(InlineFormSetFactory):
    model = ProcessLink
    fields = ("label", "url", "open_in_new_tab", "order")
    factory_kwargs = {"extra": 1, "can_delete": True}
    formset_helper_class = DynamicTableInlineFormSetHelper


class ProcessInfoResourceInlineForm(forms.ModelForm):
    class Meta:
        model = ProcessInfoResource
        fields = ("title", "resource_type", "description", "url", "document", "order")
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}


class ProcessInfoResourceInline(InlineFormSetFactory):
    model = ProcessInfoResource
    form_class = ProcessInfoResourceInlineForm
    factory_kwargs = {"extra": 1, "can_delete": True}
    formset_helper_class = DynamicTableInlineFormSetHelper


# ==============================================================================
# Utility Forms
# ==============================================================================


class ProcessAddMaterialForm(SimpleModelForm):
    material = TomSelectModelChoiceField(
        queryset=Material.objects.filter(publication_status="published"),
        config=TomSelectConfig(
            url="material-autocomplete",
            label_field="name",
        ),
        label="Material",
    )
    quantity_unit = TomSelectModelChoiceField(
        queryset=Unit.objects.filter(publication_status="published"),
        required=False,
        config=TomSelectConfig(
            url="unit-autocomplete",
            label_field="name",
        ),
        label="Quantity Unit",
    )

    class Meta:
        model = ProcessMaterial
        fields = (
            "material",
            "role",
            "stage",
            "stream_label",
            "quantity_value",
            "quantity_unit",
            "notes",
            "optional",
        )
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}


class ProcessAddParameterForm(SimpleModelForm):
    unit = TomSelectModelChoiceField(
        queryset=Unit.objects.filter(publication_status="published"),
        required=False,
        config=TomSelectConfig(
            url="unit-autocomplete",
            label_field="name",
        ),
        label="Unit",
    )

    class Meta:
        model = ProcessOperatingParameter
        fields = (
            "parameter",
            "name",
            "unit",
            "value_min",
            "value_max",
            "nominal_value",
            "basis",
            "notes",
        )
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}
