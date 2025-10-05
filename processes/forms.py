"""Forms for the processes module following shared BRIT conventions."""

import types

from django import forms
from django_tomselect.forms import (
    TomSelectConfig,
    TomSelectModelChoiceField,
    TomSelectModelMultipleChoiceField,
)
from extra_views import InlineFormSetFactory

from bibliography.models import Source
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


# ==============================================================================
# ProcessCategory Forms
# ==============================================================================


class ProcessCategoryModelForm(SimpleModelForm):
    class Meta:
        model = ProcessCategory
        fields = ("name", "description")


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
            "image",
        )
        widgets = {
            "short_description": forms.Textarea(attrs={"rows": 2}),
            "description": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Override TomSelect field validation to use queryset instead of URL endpoint
        # This fixes form validation in tests while maintaining autocomplete in production
        for field_name in ['parent', 'categories']:
            field = self.fields[field_name]
            
            # Override validation methods to use queryset
            def queryset_valid_value(self, value):
                """Validate using queryset instead of URL endpoint."""
                return self.queryset.filter(pk=value).exists()
            
            def queryset_check_values(self, value):
                """Check values using queryset instead of URL endpoint."""
                # For ModelMultipleChoiceField, value is a list of PKs
                if isinstance(value, (list, tuple)):
                    pks = [v for v in value if v]
                    return list(self.queryset.filter(pk__in=pks))
                return []
            
            # Bind methods to the field instance
            field.valid_value = types.MethodType(queryset_valid_value, field)
            if hasattr(field, '_check_values'):
                field._check_values = types.MethodType(queryset_check_values, field)


class ProcessModalModelForm(ModalModelFormMixin, ProcessModelForm):
    class Meta(ProcessModelForm.Meta):
        fields = ("name", "categories", "short_description")


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
        fields = ("source", "title", "url", "reference_type", "order")


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
