"""Forms for the processes module following shared BRIT conventions."""

import types

from crispy_forms.layout import Layout
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
    QuerysetTomSelectModelChoiceField,
    QuerysetTomSelectModelMultipleChoiceField,
    SimpleModelForm,
    WorkspaceReferenceScopeMixin,
    WorkspaceSectionFormSet,
    image_metadata_section,
)
from utils.properties.models import Unit
from utils.widgets import WorkspaceDocumentInput

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


def queryset_valid_value(self, value):
    """Validate TomSelect values against the configured queryset."""

    return self.queryset.filter(pk=value).exists()


def queryset_check_values(self, value):
    """Check TomSelect multiple values against the configured queryset."""

    if isinstance(value, list | tuple):
        pks = [v for v in value if v]
        return list(self.queryset.filter(pk__in=pks))
    return []


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


class ProcessMaintenanceForm(WorkspaceReferenceScopeMixin, SimpleModelForm):
    parent = QuerysetTomSelectModelChoiceField(
        queryset=Process.objects.all(),
        required=False,
        config=TomSelectConfig(url="processes:process-autocomplete"),
        label="Parent process",
    )
    categories = QuerysetTomSelectModelMultipleChoiceField(
        queryset=ProcessCategory.objects.all(),
        required=False,
        config=TomSelectConfig(url="processes:processcategory-autocomplete"),
        label="Categories",
    )

    class Meta(ProcessModelForm.Meta):
        labels = {"name": "Title"}
        widgets = {
            **ProcessModelForm.Meta.widgets,
            "supplementary_document": WorkspaceDocumentInput,
        }

    def __init__(self, *args, fields=None, **kwargs):
        selected = fields if fields is not None else self.Meta.fields
        super().__init__(*args, field_names=selected, **kwargs)
        if self.instance.pk and "parent" in self.fields:
            self.fields["parent"].queryset = self.fields["parent"].queryset.exclude(
                pk=self.instance.pk
            )
        if self.instance.pk and "supplementary_document" in self.fields:
            self.fields[
                "supplementary_document"
            ].widget.download_url = self.instance.supplementary_document_download_url
        self.helper.layout = Layout(*self.fields)


class ProcessQuickCreateForm(ProcessMaintenanceForm):
    class Meta(ProcessMaintenanceForm.Meta):
        fields = ("name", "short_description", "categories")


class ProcessMaterialSectionForm(
    WorkspaceReferenceScopeMixin, ProcessMaterialInlineForm
):
    material = QuerysetTomSelectModelChoiceField(
        queryset=Material.objects.all(),
        config=TomSelectConfig(url="material-autocomplete"),
        label="Material",
    )
    quantity_unit = QuerysetTomSelectModelChoiceField(
        queryset=Unit.objects.all(),
        required=False,
        config=TomSelectConfig(url="unit-autocomplete"),
        label="Unit",
    )

    class Meta(ProcessMaterialInlineForm.Meta):
        fields = (
            "material",
            "quantity_value",
            "quantity_unit",
            "stage",
            "stream_label",
            "notes",
            "optional",
        )


class ProcessParameterSectionForm(
    WorkspaceReferenceScopeMixin, ProcessOperatingParameterInlineForm
):
    unit = QuerysetTomSelectModelChoiceField(
        queryset=Unit.objects.all(),
        required=False,
        config=TomSelectConfig(url="unit-autocomplete"),
        label="Unit",
    )

    class Meta(ProcessOperatingParameterInlineForm.Meta):
        fields = (
            "parameter",
            "nominal_value",
            "unit",
            "value_min",
            "value_max",
            "basis",
            "name",
            "notes",
        )


class ProcessSourceChoiceField(QuerysetTomSelectModelChoiceField):
    def label_from_instance(self, obj):
        return obj.abbreviation or f"Source #{obj.pk}"


class ProcessSourceSectionForm(WorkspaceReferenceScopeMixin, ProcessSourceInlineForm):
    source = ProcessSourceChoiceField(
        queryset=Source.objects.all(),
        config=TomSelectConfig(url="source-autocomplete", label_field="label"),
        label="Source",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source"].workspace_autocomplete_url += "?label=abbreviation"


class ProcessAuthorSectionForm(WorkspaceReferenceScopeMixin, ProcessAuthorInlineForm):
    pass


class ProcessLinkSectionForm(WorkspaceReferenceScopeMixin, forms.ModelForm):
    class Meta:
        model = ProcessLink
        fields = ("label", "url", "open_in_new_tab")


class ProcessResourceSectionForm(
    WorkspaceReferenceScopeMixin, ProcessInfoResourceInlineForm
):
    class Meta(ProcessInfoResourceInlineForm.Meta):
        fields = ("title", "resource_type", "description", "url", "document")
        widgets = {
            **ProcessInfoResourceInlineForm.Meta.widgets,
            "document": WorkspaceDocumentInput,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields[
                "document"
            ].widget.download_url = self.instance.document_download_url


class ProcessSectionFormSet(WorkspaceSectionFormSet):
    reference_fields = {ProcessAuthor: "author", ProcessSource: "source"}
    position_fields = {ProcessAuthor: "position"}


PROCESS_SECTIONS = {
    "overview": {
        "label": "Overview",
        "fields": ("name", "short_description", "categories", "parent"),
    },
    "image": {
        "label": "Image",
        "fields": ("image", "image_alt_text", "image_caption", "image_rights_notice"),
    },
    "technology": {
        "label": "Description and technology",
        "fields": ("mechanism", "description", "process_technology"),
    },
    "inputs": {
        "label": "Inputs",
        "forms": (
            (
                ProcessMaterialSectionForm,
                {
                    "add_label": "Add input",
                    "row_template": "processes/includes/process_material_row.html",
                },
            ),
        ),
        "role": "input",
    },
    "outputs": {
        "label": "Outputs",
        "forms": (
            (
                ProcessMaterialSectionForm,
                {
                    "add_label": "Add output",
                    "row_template": "processes/includes/process_material_row.html",
                },
            ),
        ),
        "role": "output",
    },
    "parameters": {
        "label": "Conditions and performance",
        "forms": (
            (
                ProcessParameterSectionForm,
                {"heading": "Operating parameters", "add_label": "Add parameter"},
            ),
        ),
    },
    "references": {
        "label": "References and contributors",
        "forms": (
            (
                ProcessAuthorSectionForm,
                {"heading": "Contributors", "add_label": "Add contributor"},
            ),
            (
                ProcessSourceSectionForm,
                {"heading": "Bibliography", "add_label": "Add reference"},
            ),
        ),
    },
    "resources": {
        "label": "Supporting files and links",
        "fields": ("supplementary_document",),
        "forms": (
            (ProcessLinkSectionForm, {"heading": "Links", "add_label": "Add link"}),
            (
                ProcessResourceSectionForm,
                {
                    "heading": "Information resources",
                    "add_label": "Add information resource",
                },
            ),
        ),
    },
}
