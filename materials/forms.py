import re

from crispy_forms.layout import Fieldset, Layout
from django.core.exceptions import ValidationError
from django.forms import (
    CharField,
    DateTimeField,
    DateTimeInput,
    ModelChoiceField,
    TextInput,
)
from django.urls import reverse
from django.utils import timezone
from django_tomselect.forms import (
    TomSelectConfig,
    TomSelectModelChoiceField,
    TomSelectModelMultipleChoiceField,
)

from bibliography.models import Source
from distributions.models import TemporalDistribution
from utils.forms import (
    CreateEnabledTomSelectModelChoiceField,
    ModalForm,
    ModalModelForm,
    ModalModelFormMixin,
    QuerysetTomSelectModelChoiceField,
    QuerysetTomSelectModelMultipleChoiceField,
    SimpleModelForm,
    SourcesFieldMixin,
    UserCreatedObjectFormMixin,
    WorkspaceReferenceScopeMixin,
    configure_tomselect_inline_create,
    image_metadata_section,
)
from utils.properties.forms import NumericMeasurementFieldsFormMixin
from utils.properties.models import Unit, get_default_unit_pk

from .models import (
    AnalyticalMethod,
    ComponentMeasurement,
    Composition,
    Material,
    MaterialCategory,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialProperty,
    MaterialPropertyValue,
    Sample,
    SampleGroup,
    SampleSeries,
    get_or_create_sample_substrate_category,
)


class MaterialCategoryModelForm(SimpleModelForm):
    class Meta:
        model = MaterialCategory
        fields = ("name", "description")


class MaterialCategoryModalModelForm(ModalModelFormMixin, MaterialCategoryModelForm):
    pass


class MaterialModelForm(SimpleModelForm):
    class Meta:
        model = Material
        fields = ("name", "description", "categories")


class MaterialModalModelForm(ModalModelFormMixin, MaterialModelForm):
    pass


class ComponentModelForm(SimpleModelForm):
    comparable_component = TomSelectModelChoiceField(
        queryset=MaterialComponent.objects.all(),
        required=False,
        config=TomSelectConfig(
            url="materialcomponent-autocomplete",
            label_field="name",
        ),
        label="Comparable as",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = MaterialComponent.objects.all()
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        self.fields["comparable_component"].queryset = queryset

    def clean_comparable_component(self):
        comparable_component = self.cleaned_data.get("comparable_component")
        if comparable_component is None:
            return None
        if self.instance.pk and comparable_component.pk == self.instance.pk:
            raise ValidationError("A component cannot be comparable to itself.")
        return comparable_component.canonical_component

    class Meta:
        model = MaterialComponent
        fields = ("name", "description", "comparable_component", "is_aggregate")


class ComponentModalModelForm(ModalModelFormMixin, ComponentModelForm):
    pass


class ComponentGroupModelForm(SimpleModelForm):
    class Meta:
        model = MaterialComponentGroup
        fields = ("name", "description", "is_compositional")


class ComponentGroupModalModelForm(ModalModelFormMixin, ComponentGroupModelForm):
    pass


class MaterialPropertyModelForm(SimpleModelForm):
    comparable_property = TomSelectModelChoiceField(
        queryset=MaterialProperty.objects.all(),
        required=False,
        config=TomSelectConfig(
            url="materialproperty-autocomplete",
            label_field="name",
        ),
        label="Comparable as",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = MaterialProperty.objects.all()
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        self.fields["comparable_property"].queryset = queryset

    def clean_comparable_property(self):
        comparable_property = self.cleaned_data.get("comparable_property")
        if comparable_property is None:
            return None
        if self.instance.pk and comparable_property.pk == self.instance.pk:
            raise ValidationError("A property cannot be comparable to itself.")
        return comparable_property.canonical_property

    class Meta:
        model = MaterialProperty
        fields = ("name", "allowed_units", "description", "comparable_property")


class MaterialPropertyModalModelForm(ModalModelFormMixin, MaterialPropertyModelForm):
    pass


class ComponentMeasurementModelForm(
    NumericMeasurementFieldsFormMixin,
    UserCreatedObjectFormMixin,
    SourcesFieldMixin,
    SimpleModelForm,
):
    group = TomSelectModelChoiceField(
        queryset=MaterialComponentGroup.objects.all(),
        config=TomSelectConfig(
            url="materialcomponentgroup-autocomplete",
            label_field="name",
        ),
        label="Group",
    )
    component = TomSelectModelChoiceField(
        queryset=MaterialComponent.objects.all(),
        config=TomSelectConfig(
            url="materialcomponent-autocomplete",
            label_field="name",
        ),
        label="Component",
    )
    basis_component = TomSelectModelChoiceField(
        queryset=MaterialComponent.objects.all(),
        required=False,
        config=TomSelectConfig(
            url="materialcomponent-autocomplete",
            label_field="name",
        ),
        label="Basis component",
    )
    analytical_method = TomSelectModelChoiceField(
        queryset=AnalyticalMethod.objects.all(),
        required=False,
        config=TomSelectConfig(
            url="analyticalmethod-autocomplete",
            label_field="name",
        ),
        label="Analytical method",
    )
    unit = TomSelectModelChoiceField(
        queryset=Unit.objects.filter(Unit.weight_fraction_q()),
        config=TomSelectConfig(
            url="unit-autocomplete-weight-fraction",
            label_field="name",
        ),
        label="Unit",
        help_text="Weight-fraction units only (e.g. %, g/kg, mg/kg).",
    )

    class Meta:
        model = ComponentMeasurement
        fields = (
            "group",
            "component",
            "basis_component",
            "analytical_method",
            "sources",
            "unit",
            "average",
            "standard_deviation",
            "sample_size",
            "comment",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["standard_deviation"].required = False
        self.fields["standard_deviation"].widget.is_required = False
        self.fields["standard_deviation"].widget.attrs.pop("required", None)


class ComponentMeasurementModalModelForm(
    ModalModelFormMixin, ComponentMeasurementModelForm
):
    pass


class ComponentMeasurementSectionForm(
    WorkspaceReferenceScopeMixin, ComponentMeasurementModelForm
):
    """One measurement row in the Sample maintenance workspace table."""

    group = QuerysetTomSelectModelChoiceField(
        queryset=MaterialComponentGroup.objects.all(),
        config=TomSelectConfig(
            url="materialcomponentgroup-autocomplete",
            label_field="name",
        ),
        label="Group",
    )
    component = QuerysetTomSelectModelChoiceField(
        queryset=MaterialComponent.objects.all(),
        config=TomSelectConfig(
            url="materialcomponent-autocomplete",
            label_field="name",
        ),
        label="Component",
    )
    basis_component = QuerysetTomSelectModelChoiceField(
        queryset=MaterialComponent.objects.all(),
        required=False,
        config=TomSelectConfig(
            url="materialcomponent-autocomplete",
            label_field="name",
        ),
        label="Basis component",
    )
    analytical_method = QuerysetTomSelectModelChoiceField(
        queryset=AnalyticalMethod.objects.all(),
        required=False,
        config=TomSelectConfig(
            url="analyticalmethod-autocomplete",
            label_field="name",
        ),
        label="Analytical method",
    )
    unit = QuerysetTomSelectModelChoiceField(
        queryset=Unit.objects.filter(Unit.weight_fraction_q()),
        config=TomSelectConfig(
            url="unit-autocomplete-weight-fraction",
            label_field="name",
        ),
        label="Unit",
        help_text="Weight-fraction units only (e.g. %, g/kg, mg/kg).",
    )
    sources = QuerysetTomSelectModelMultipleChoiceField(
        queryset=Source.objects.all(),
        required=False,
        config=TomSelectConfig(url="source-autocomplete", label_field="label"),
        label="Sources",
    )


class MaterialPropertyValueModelForm(
    NumericMeasurementFieldsFormMixin,
    UserCreatedObjectFormMixin,
    SourcesFieldMixin,
    SimpleModelForm,
):
    property = TomSelectModelChoiceField(
        queryset=MaterialProperty.objects.all(),
        config=TomSelectConfig(
            url="materialproperty-autocomplete",
            label_field="name",
        ),
        label="Property",
    )
    basis_component = TomSelectModelChoiceField(
        queryset=MaterialComponent.objects.all(),
        required=False,
        config=TomSelectConfig(
            url="materialcomponent-autocomplete",
            label_field="name",
        ),
        label="Basis",
    )
    unit = TomSelectModelChoiceField(
        queryset=Unit.objects.all(),
        required=False,
        config=TomSelectConfig(
            url="unit-autocomplete",
            label_field="name",
        ),
        label="Unit",
    )
    analytical_method = TomSelectModelChoiceField(
        queryset=AnalyticalMethod.objects.all(),
        required=False,
        config=TomSelectConfig(
            url="analyticalmethod-autocomplete",
            label_field="name",
        ),
        label="Analytical method",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["unit"].required = False
        self.fields["basis_component"].required = False
        self.fields["standard_deviation"].required = False
        self.fields["standard_deviation"].widget.is_required = False
        self.fields["standard_deviation"].widget.attrs.pop("required", None)
        if not self.is_bound and not self.instance.pk:
            property_obj = self.initial.get("property")
            if property_obj and getattr(property_obj, "default_basis_component", None):
                self.initial.setdefault(
                    "basis_component", property_obj.default_basis_component
                )

    class Meta:
        model = MaterialPropertyValue
        fields = (
            "property",
            "basis_component",
            "unit",
            "analytical_method",
            "sources",
            "average",
            "standard_deviation",
        )

    def clean(self):
        cleaned_data = super().clean()
        property_obj = cleaned_data.get("property")
        basis_component = cleaned_data.get("basis_component")
        unit = cleaned_data.get("unit")
        if property_obj and basis_component is None:
            basis_component = property_obj.default_basis_component
            cleaned_data["basis_component"] = basis_component
        if property_obj and not unit:
            unit = property_obj.allowed_units.first()
            if unit is None:
                unit = Unit.objects.filter(pk=get_default_unit_pk()).first()
            cleaned_data["unit"] = unit

        if not property_obj or not unit:
            return cleaned_data

        allowed_units = property_obj.allowed_units.all()
        if allowed_units.exists() and not allowed_units.filter(pk=unit.pk).exists():
            self.add_error(
                "unit",
                "Selected unit is not allowed for this property.",
            )
        return cleaned_data

    def save(self, commit=True):
        value = super().save(commit=commit)
        if value.property_id and value.unit_id:
            if not value.property.allowed_units.filter(pk=value.unit_id).exists():
                value.property.allowed_units.add(value.unit)
        return value


class MaterialPropertyValueModalModelForm(
    ModalModelFormMixin, MaterialPropertyValueModelForm
):
    pass


class MaterialPropertyValueSectionForm(
    WorkspaceReferenceScopeMixin, MaterialPropertyValueModelForm
):
    """One property value row in the Sample maintenance workspace table."""

    property = QuerysetTomSelectModelChoiceField(
        queryset=MaterialProperty.objects.all(),
        config=TomSelectConfig(
            url="materialproperty-autocomplete",
            label_field="name",
        ),
        label="Property",
    )
    basis_component = QuerysetTomSelectModelChoiceField(
        queryset=MaterialComponent.objects.all(),
        required=False,
        config=TomSelectConfig(
            url="materialcomponent-autocomplete",
            label_field="name",
        ),
        label="Basis",
    )
    unit = QuerysetTomSelectModelChoiceField(
        queryset=Unit.objects.all(),
        required=False,
        config=TomSelectConfig(
            url="unit-autocomplete",
            label_field="name",
        ),
        label="Unit",
    )
    analytical_method = QuerysetTomSelectModelChoiceField(
        queryset=AnalyticalMethod.objects.all(),
        required=False,
        config=TomSelectConfig(
            url="analyticalmethod-autocomplete",
            label_field="name",
        ),
        label="Analytical method",
    )
    sources = QuerysetTomSelectModelMultipleChoiceField(
        queryset=Source.objects.all(),
        required=False,
        config=TomSelectConfig(url="source-autocomplete", label_field="label"),
        label="Sources",
    )


class AnalyticalMethodModelForm(
    UserCreatedObjectFormMixin, SourcesFieldMixin, SimpleModelForm
):
    class Meta:
        model = AnalyticalMethod
        fields = (
            "name",
            "technique",
            "standard",
            "lower_detection_limit",
            "description",
            "sources",
        )


class SampleSeriesModelForm(SimpleModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.layout = Layout(
            "name",
            "material",
            image_metadata_section(),
            "publish",
            "description",
        )

    class Meta:
        model = SampleSeries
        fields = (
            "name",
            "material",
            "image",
            "image_alt_text",
            "image_caption",
            "image_rights_notice",
            "publish",
            "description",
        )
        labels = {"publish": "featured"}


class SampleSeriesModalModelForm(ModalModelFormMixin, SampleSeriesModelForm):
    pass


def _editable_by(queryset, user):
    if getattr(user, "is_staff", False):
        return queryset.all()
    if getattr(user, "is_authenticated", False):
        return queryset.editable_by_user(user)
    return queryset.none()


def _sample_groups_editable_by(user):
    return _editable_by(SampleGroup.objects, user)


def _samples_editable_by(user):
    return _editable_by(Sample.objects, user)


class SampleGroupModelForm(
    UserCreatedObjectFormMixin, SourcesFieldMixin, SimpleModelForm
):
    samples = QuerysetTomSelectModelMultipleChoiceField(
        queryset=Sample.objects.all(),
        required=False,
        config=TomSelectConfig(
            url="sample-autocomplete-editable",
            label_field="name",
            value_field="id",
        ),
        label="Samples",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = getattr(self, "request", None)
        editable = (
            _samples_editable_by(request.user)
            if request is not None
            else Sample.objects.none()
        )
        self.fields["samples"].queryset = editable
        self._locked_sample_ids = []
        if self.instance.pk:
            self.initial["samples"] = self.instance.samples.filter(pk__in=editable)
            self._locked_sample_ids = list(
                self.instance.samples.exclude(pk__in=editable).values_list(
                    "pk", flat=True
                )
            )
        self.helper.layout = Layout(
            "name",
            "kind",
            "samples",
            "description",
            "sources",
        )

    def _save_m2m(self):
        super()._save_m2m()
        self.instance.samples.set(self.cleaned_data["samples"])
        self.instance.samples.add(*self._locked_sample_ids)

    class Meta:
        model = SampleGroup
        fields = ("name", "kind", "description", "sources")


class SampleGroupModalModelForm(ModalModelFormMixin, SampleGroupModelForm):
    pass


class SampleSeriesAddTemporalDistributionModalModelForm(ModalModelForm):
    distribution = ModelChoiceField(queryset=TemporalDistribution.objects.all())

    class Meta:
        model = SampleSeries
        fields = ("distribution",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["distribution"].queryset = TemporalDistribution.objects.difference(
            self.instance.temporal_distributions.all()
        )


class SampleModelForm(UserCreatedObjectFormMixin, SourcesFieldMixin, SimpleModelForm):
    datetime = CharField(
        required=False,
        label="Sampling date/time",
        widget=TextInput(attrs={"placeholder": "e.g. 2024 or 2024-08-27"}),
    )
    material = CreateEnabledTomSelectModelChoiceField(
        config=TomSelectConfig(
            url="sample-substrate-material-autocomplete",
            label_field="name",
            value_field="id",
            placeholder="Select or create a substrate",
            create=True,
        ),
        required=False,
        label="Substrate",
    )
    series = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="sampleseries-autocomplete",
            label_field="name",
            value_field="id",
        ),
        required=False,
        label="Series",
    )
    sample_groups = TomSelectModelMultipleChoiceField(
        queryset=SampleGroup.objects.all(),
        required=False,
        config=TomSelectConfig(
            url="samplegroup-autocomplete-editable",
            label_field="name",
            value_field="id",
        ),
        label="Sample groups",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "datetime" not in (kwargs.get("initial") or {}):
            self.initial["datetime"] = self.instance.sampling_date_input
        self.fields["datetime"].help_text = (
            "Enter only what is known: year (2024), date (2024-08-27), "
            "or date and time (2024-08-27 14:30). "
            f"Times use {timezone.get_default_timezone()}. Leave blank if unknown."
        )
        substrate_category, _ = get_or_create_sample_substrate_category()
        material_queryset = Material.objects.filter(categories=substrate_category)
        if self.instance.pk and self.instance.material_id:
            material_queryset = material_queryset | Material.objects.filter(
                pk=self.instance.material_id
            )
        substrate_field = self.fields["material"]
        substrate_field.queryset = material_queryset.distinct()
        substrate_field.help_text = (
            "Select an existing substrate. If it is not listed, type a new name "
            "and press Enter to create it automatically."
        )

        request = getattr(self, "request", None)
        if request and request.user.has_perm("materials.add_material"):
            configure_tomselect_inline_create(
                substrate_field,
                create_url=reverse("sample-substrate-material-quick-create"),
                error_message="Could not create substrate.",
            )
        self._locked_group_ids = []
        groups_field = self.fields.get("sample_groups")
        if groups_field is not None:
            groups_field.queryset = (
                _sample_groups_editable_by(request.user)
                if request is not None
                else SampleGroup.objects.none()
            )
            if self.instance.pk:
                self.initial["sample_groups"] = self.instance.sample_groups.filter(
                    pk__in=groups_field.queryset
                )
                self._locked_group_ids = list(
                    self.instance.sample_groups.exclude(
                        pk__in=groups_field.queryset
                    ).values_list("pk", flat=True)
                )
        self.helper.layout = Layout(
            "name",
            "material",
            image_metadata_section(),
            "datetime",
            "location",
            "description",
            "standalone",
            "series",
            "timestep",
            "sample_groups",
            "sources",
            Fieldset(
                "Analysis",
                "analysis_date",
                "analysis_laboratory",
                "lab_accreditation",
                "analysis_objective",
            ),
        )

    def _save_m2m(self):
        super()._save_m2m()
        if "sample_groups" in self.fields:
            self.instance.sample_groups.add(*self._locked_group_ids)

    def clean_datetime(self):
        value = self.cleaned_data["datetime"]
        if not value:
            self.instance.datetime_precision = ""
            return None
        if self.instance.datetime and value == self.instance.sampling_date_input:
            return self.instance.datetime
        if re.fullmatch(r"[0-9]{4}", value):
            precision = "year"
            value += "-01-01"
        elif re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            precision = "date"
        elif re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}[ T][0-9]{2}:[0-9]{2}"
            r"(?::[0-9]{2}(?:\.[0-9]{1,6})?)?",
            value,
        ):
            precision = "time"
        else:
            raise ValidationError(
                "Enter a year (2024), date (2024-08-27), "
                "or date and time (2024-08-27 14:30)."
            )
        with timezone.override(timezone.get_default_timezone()):
            parsed = DateTimeField().clean(value)
        self.instance.datetime_precision = precision
        return parsed

    def clean(self):
        cleaned_data = super().clean()
        if "series" in self.fields:
            series = cleaned_data.get("series")
        else:
            series = self.instance.series if self.instance.series_id else None
        if "standalone" in self.fields or "series" in self.fields:
            standalone = cleaned_data.get("standalone", False)
            if not standalone and series is None:
                self.add_error(
                    "series",
                    "A series is required when the sample is not standalone. "
                    "Either assign a series or check 'Standalone'.",
                )
        if series is not None:
            # A sample's material always matches the material of its series.
            cleaned_data["material"] = series.material
            self.instance.material = series.material
        return cleaned_data

    class Meta:
        model = Sample
        fields = (
            "name",
            "material",
            "image",
            "image_alt_text",
            "image_caption",
            "image_rights_notice",
            "datetime",
            "location",
            "description",
            "standalone",
            "series",
            "timestep",
            "sample_groups",
            "sources",
            "analysis_date",
            "analysis_laboratory",
            "lab_accreditation",
            "analysis_objective",
        )
        widgets = {
            "analysis_date": DateTimeInput(
                format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}
            ),
        }
        labels = {
            "datetime": "Sampling date/time",
            "analysis_date": "Analysis date/time",
            "image": "Image",
            "image_alt_text": "Image alt text",
            "image_caption": "Image caption",
            "image_rights_notice": "Image rights notice",
        }


class SampleModalModelForm(ModalModelFormMixin, SampleModelForm):
    pass


class SampleMaintenanceForm(WorkspaceReferenceScopeMixin, SampleModelForm):
    """Section-scoped Sample form for the maintenance workspace."""

    material = QuerysetTomSelectModelChoiceField(
        queryset=Material.objects.all(),
        config=TomSelectConfig(
            url="sample-substrate-material-autocomplete",
            label_field="name",
            value_field="id",
        ),
        required=True,
        label="Substrate",
    )
    series = QuerysetTomSelectModelChoiceField(
        queryset=SampleSeries.objects.all(),
        required=False,
        config=TomSelectConfig(
            url="sampleseries-autocomplete",
            label_field="name",
            value_field="id",
        ),
        label="Series",
    )
    sample_groups = QuerysetTomSelectModelMultipleChoiceField(
        queryset=SampleGroup.objects.all(),
        required=False,
        config=TomSelectConfig(
            url="samplegroup-autocomplete-editable",
            label_field="name",
            value_field="id",
        ),
        label="Sample groups",
    )
    sources = QuerysetTomSelectModelMultipleChoiceField(
        queryset=Source.objects.all(),
        required=False,
        config=TomSelectConfig(url="source-autocomplete", label_field="label"),
        label="Sources",
    )

    class Meta(SampleModelForm.Meta):
        pass

    def __init__(self, *args, fields=None, **kwargs):
        selected = fields if fields is not None else self.Meta.fields
        super().__init__(*args, field_names=selected, **kwargs)
        request = getattr(self, "request", None)
        if request is not None and "sample_groups" in self.fields:
            self.fields["sample_groups"].queryset = _sample_groups_editable_by(
                request.user
            )
        if "sources" in self.fields:
            self.fields["sources"].workspace_autocomplete_url += "?label=abbreviation"
        self.helper.layout = Layout(*self.fields)

    def _update_errors(self, errors):
        # Sample.clean() reports the standalone/series invariant against
        # "series" and the series-material consistency against "material";
        # sections that cannot edit the respective field cannot fix or
        # display the error.
        if hasattr(errors, "error_dict"):
            if "standalone" not in self.fields and "series" not in self.fields:
                errors.error_dict.pop("series", None)
            if "material" not in self.fields:
                errors.error_dict.pop("material", None)
            if not errors.error_dict:
                return
        super()._update_errors(errors)


class SampleQuickCreateForm(SampleMaintenanceForm):
    """Minimal fields needed to start a private Sample draft."""

    class Meta(SampleMaintenanceForm.Meta):
        fields = ("name", "material", "datetime", "standalone", "series")


SAMPLE_SECTIONS = {
    "overview": {
        "label": "Overview",
        "fields": ("name", "material", "description"),
    },
    "sampling": {
        "label": "Sampling",
        "fields": (
            "datetime",
            "location",
            "standalone",
            "series",
            "timestep",
            "sample_groups",
        ),
    },
    "analysis": {
        "label": "Analysis",
        "fields": (
            "analysis_date",
            "analysis_laboratory",
            "lab_accreditation",
            "analysis_objective",
        ),
    },
    "image": {
        "label": "Image",
        "fields": (
            "image",
            "image_alt_text",
            "image_caption",
            "image_rights_notice",
        ),
    },
    "sources": {
        "label": "Sources",
        "fields": ("sources",),
    },
    "measurements": {
        "label": "Component measurements",
        "policy": "can_manage_samples",
        "forms": (
            (
                ComponentMeasurementSectionForm,
                {
                    "heading": "Component measurements",
                    "add_label": "Add measurement",
                    "row_template": "materials/includes/sample_measurement_row.html",
                    "paste": {
                        "label": "measurements",
                        "columns": "group,component,average,unit,standard_deviation,sample_size",
                        "hint": "One row per line: group, component, value, unit, standard deviation, sample size (tab-separated).",
                    },
                },
            ),
        ),
    },
    "properties": {
        "label": "Property values",
        "policy": "can_add_property",
        "forms": (
            (
                MaterialPropertyValueSectionForm,
                {
                    "heading": "Property values",
                    "add_label": "Add property value",
                    "row_template": "materials/includes/sample_property_value_row.html",
                    "paste": {
                        "label": "property values",
                        "columns": "property,average,unit,standard_deviation",
                        "hint": "One row per line: property, value, unit, standard deviation (tab-separated).",
                    },
                },
            ),
        ),
    },
}


class CompositionModelForm(SimpleModelForm):
    class Meta:
        model = Composition
        fields = ("group", "sample", "fractions_of")


class CompositionModalModelForm(ModalModelFormMixin, CompositionModelForm):
    pass


class SampleAddCompositionForm(SimpleModelForm):
    sample = ModelChoiceField(queryset=Sample.objects.none())

    class Meta:
        model = Composition
        fields = ("sample", "group", "fractions_of")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        sample = kwargs["initial"].get("sample")
        self.fields["sample"].queryset = Sample.objects.filter(id=sample.id)
        self.fields["sample"].empty_label = None
        self.fields["group"].queryset = MaterialComponentGroup.objects.exclude(
            id__in=sample.group_ids
        )
        self.fields["group"].empty_label = None
        self.fields["fractions_of"].queryset = MaterialComponent.objects.filter(
            id__in=[
                *sample.components.values_list("id", flat=True),
                MaterialComponent.objects.default().id,
            ]
        )
        self.fields["fractions_of"].empty_label = None


class AddCompositionModalForm(ModalModelForm):
    group = ModelChoiceField(queryset=MaterialComponentGroup.objects.all())
    fractions_of = ModelChoiceField(queryset=MaterialComponent.objects.all())

    class Meta:
        model = SampleSeries
        fields = [
            "group",
            "fractions_of",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["group"].queryset = MaterialComponentGroup.objects.exclude(
            id__in=self.instance.blocked_ids
        )
        self.fields["fractions_of"].queryset = MaterialComponent.objects.filter(
            id__in=[
                *self.instance.components.values_list("id", flat=True),
                MaterialComponent.objects.default().id,
            ]
        )
        self.fields["fractions_of"].empty_label = None


class AddSeasonalVariationForm(ModalForm):
    temporal_distribution = ModelChoiceField(
        queryset=TemporalDistribution.objects.all()
    )

    class Meta:
        fields = ("temporal_distribution",)
