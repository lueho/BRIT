"""Forms for the processes module following shared BRIT conventions."""

import types

from crispy_forms.layout import HTML, Div, Field, Layout
from django import forms
from django.forms import inlineformset_factory
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
    ProcessCategory,
    ProcessInfoResource,
    ProcessLink,
    ProcessMaterial,
    ProcessOperatingParameter,
    ProcessReference,
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
    authors = TomSelectModelMultipleChoiceField(
        queryset=Author.objects.all(),
        required=False,
        config=TomSelectConfig(
            url="author-autocomplete",
            label_field="label",
        ),
        label="Authors",
    )

    class Meta:
        model = Process
        fields = (
            "name",
            "parent",
            "categories",
            "authors",
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
        for field_name in ["parent", "categories", "authors"]:
            field = self.fields[field_name]

            # Override validation methods to use queryset
            def queryset_valid_value(self, value):
                """Validate using queryset instead of URL endpoint."""
                return self.queryset.filter(pk=value).exists()

            def queryset_check_values(self, value):
                """Check values using queryset instead of URL endpoint."""
                # For ModelMultipleChoiceField, value is a list of PKs
                if isinstance(value, list | tuple):
                    pks = [v for v in value if v]
                    return list(self.queryset.filter(pk__in=pks))
                return []

            # Bind methods to the field instance
            field.valid_value = types.MethodType(queryset_valid_value, field)
            if hasattr(field, "_check_values"):
                field._check_values = types.MethodType(queryset_check_values, field)
        self.helper.layout = Layout(
            "name",
            "parent",
            "categories",
            "authors",
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


class ProcessReferenceInlineForm(forms.ModelForm):
    source = TomSelectModelChoiceField(
        queryset=Source.objects.filter(publication_status="published"),
        required=False,
        config=TomSelectConfig(
            url="source-autocomplete",
            label_field="label",
        ),
        label="Source",
    )

    class Meta:
        model = ProcessReference
        fields = ("source", "title", "url", "reference_type")


class ProcessReferenceInline(InlineFormSetFactory):
    model = ProcessReference
    form_class = ProcessReferenceInlineForm
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
