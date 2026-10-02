"""Forms for the processes module following shared BRIT conventions."""

from crispy_forms.layout import Layout
from django import forms
from django_tomselect.app_settings import TomSelectConfig
from django_tomselect.forms import TomSelectModelChoiceField

from bibliography.models import Author, Source
from materials.models import Material
from utils.forms import (
    ModalModelFormMixin,
    PermissiveQuerysetTomSelectModelMultipleChoiceField,
    QuerysetTomSelectModelChoiceField,
    QuerysetTomSelectModelMultipleChoiceField,
    SimpleModelForm,
    WorkspaceReferenceScopeMixin,
    WorkspaceSectionFormSet,
    image_metadata_section,
)
from utils.object_management.permissions import filter_queryset_for_user
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
    parent = QuerysetTomSelectModelChoiceField(
        queryset=Process.objects.all(),
        required=False,
        config=TomSelectConfig(url="processes:process-autocomplete"),
        label="Parent process",
    )
    # Categories outside the request-scoped queryset are silently dropped
    # rather than rejecting the submission.
    categories = PermissiveQuerysetTomSelectModelMultipleChoiceField(
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
        # Scope category choices to the request user's read policy, matching
        # the processcategory-autocomplete endpoint. Existing selections stay
        # valid so edits do not drop values the user can no longer see.
        request = getattr(self, "request", None)
        if request is not None and hasattr(request, "user"):
            categories_field = self.fields["categories"]
            queryset = filter_queryset_for_user(
                ProcessCategory.objects.all(), request.user
            ).exclude(publication_status=ProcessCategory.STATUS_ARCHIVED)
            if self.instance.pk:
                queryset = queryset | ProcessCategory.objects.filter(
                    pk__in=self.instance.categories.all()
                )
            categories_field.queryset = queryset.distinct()
            # TomSelect fields re-resolve their queryset from the widget
            # during clean(); pin the widget to the scoped queryset.
            categories_field.widget.get_queryset = lambda field=categories_field: (
                field.queryset
            )
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
# Process section forms
# ==============================================================================


class ProcessAuthorForm(forms.ModelForm):
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


class ProcessSourceForm(forms.ModelForm):
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


class ProcessMaterialForm(forms.ModelForm):
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


class ProcessOperatingParameterForm(forms.ModelForm):
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


class ProcessInfoResourceForm(forms.ModelForm):
    class Meta:
        model = ProcessInfoResource
        fields = ("title", "resource_type", "description", "url", "document", "order")
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}


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


class ProcessMaterialSectionForm(WorkspaceReferenceScopeMixin, ProcessMaterialForm):
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

    class Meta(ProcessMaterialForm.Meta):
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
    WorkspaceReferenceScopeMixin, ProcessOperatingParameterForm
):
    unit = QuerysetTomSelectModelChoiceField(
        queryset=Unit.objects.all(),
        required=False,
        config=TomSelectConfig(url="unit-autocomplete"),
        label="Unit",
    )

    class Meta(ProcessOperatingParameterForm.Meta):
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


class ProcessSourceSectionForm(WorkspaceReferenceScopeMixin, ProcessSourceForm):
    source = ProcessSourceChoiceField(
        queryset=Source.objects.all(),
        config=TomSelectConfig(url="source-autocomplete", label_field="label"),
        label="Source",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source"].workspace_autocomplete_url += "?label=abbreviation"


class ProcessAuthorSectionForm(WorkspaceReferenceScopeMixin, ProcessAuthorForm):
    pass


class ProcessLinkSectionForm(WorkspaceReferenceScopeMixin, forms.ModelForm):
    class Meta:
        model = ProcessLink
        fields = ("label", "url", "open_in_new_tab")


class ProcessResourceSectionForm(WorkspaceReferenceScopeMixin, ProcessInfoResourceForm):
    class Meta(ProcessInfoResourceForm.Meta):
        fields = ("title", "resource_type", "description", "url", "document")
        widgets = {
            **ProcessInfoResourceForm.Meta.widgets,
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
