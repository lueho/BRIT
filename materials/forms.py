from django.core.exceptions import ValidationError
from django.forms import (
    DateTimeInput,
    ModelChoiceField,
)
from django.urls import reverse
from django_tomselect.forms import (
    TomSelectConfig,
    TomSelectModelChoiceField,
)

from bibliography.models import Source
from distributions.models import TemporalDistribution
from utils.forms import (
    CreateEnabledTomSelectModelChoiceField,
    ModalForm,
    ModalModelForm,
    ModalModelFormMixin,
    SimpleModelForm,
    SourcesFieldMixin,
    UserCreatedObjectFormMixin,
    configure_tomselect_inline_create,
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
        queryset=MaterialComponent.objects.filter(type="component"),
        required=False,
        config=TomSelectConfig(
            url="materialcomponent-autocomplete",
            label_field="name",
        ),
        label="Comparable as",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = MaterialComponent.objects.filter(type="component")
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
        fields = ("name", "description", "comparable_component")


class ComponentModalModelForm(ModalModelFormMixin, ComponentModelForm):
    pass


class ComponentGroupModelForm(SimpleModelForm):
    class Meta:
        model = MaterialComponentGroup
        fields = ("name", "description")


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
        fields = ("name", "unit", "description", "comparable_property")


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
        queryset=Unit.objects.all(),
        config=TomSelectConfig(
            url="unit-autocomplete",
            label_field="name",
        ),
        label="Unit",
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
        queryset=MaterialComponent.objects.filter(type="component"),
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
            if unit is None and property_obj.unit:
                unit = Unit.resolve_legacy_label(
                    property_obj.unit, owner=property_obj.owner
                )
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
    class Meta:
        model = SampleSeries
        fields = ("name", "material", "image", "publish", "description")
        labels = {"publish": "featured"}


class SampleSeriesModalModelForm(ModalModelFormMixin, SampleSeriesModelForm):
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        substrate_category, _ = get_or_create_sample_substrate_category()
        material_queryset = Material.objects.filter(
            type="material",
            categories=substrate_category,
        )
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

    class Meta:
        model = Sample
        fields = (
            "name",
            "material",
            "image",
            "datetime",
            "location",
            "description",
            "series",
            "timestep",
            "sources",
        )
        widgets = {
            "datetime": DateTimeInput(attrs={"type": "datetime-local"}),
        }
        labels = {
            "datetime": "Date/Time",
            "image": "Image",
        }


class SampleModalModelForm(ModalModelFormMixin, SampleModelForm):
    pass


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


class AddLiteratureSourceForm(ModalForm):
    source = ModelChoiceField(queryset=Source.objects.all(), label="Reference")

    class Meta:
        fields = ("source",)


class AddSeasonalVariationForm(ModalForm):
    temporal_distribution = ModelChoiceField(
        queryset=TemporalDistribution.objects.all()
    )

    class Meta:
        fields = ("temporal_distribution",)
