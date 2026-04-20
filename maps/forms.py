from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Field, Layout, Row
from django.contrib.gis.forms import MultiPolygonField
from django.db.models import Subquery
from django.forms import (
    BaseFormSet,
    CharField,
    ChoiceField,
    DateField,
    DateInput,
    ModelChoiceField,
    MultipleChoiceField,
    Textarea,
    ValidationError,
)
from django.forms.widgets import CheckboxSelectMultiple, RadioSelect
from django.urls import reverse
from django_tomselect.forms import (
    TomSelectConfig,
    TomSelectModelChoiceField,
)
from leaflet.forms.widgets import LeafletWidget

from utils.forms import (
    ModalModelFormMixin,
    SimpleForm,
    SimpleModelForm,
    SourcesFieldMixin,
    UserCreatedObjectFormMixin,
)
from utils.properties.forms import NumericMeasurementFieldsFormMixin

from .models import (
    BACKEND_TYPE_CHOICES,
    Attribute,
    Catchment,
    GeoDataset,
    GeoDatasetColumnPolicy,
    GeoDatasetRuntimeConfiguration,
    GeoPolygon,
    LauRegion,
    Location,
    NutsRegion,
    Region,
    RegionAttributeValue,
    RegionProperty,
)


class GeoDataSetModelForm(
    UserCreatedObjectFormMixin, SourcesFieldMixin, SimpleModelForm
):
    # sources field and __init__ logic provided by SourcesFieldMixin

    backend_type = ChoiceField(choices=BACKEND_TYPE_CHOICES, required=False)
    runtime_model_name = CharField(required=False)
    schema_name = CharField(required=False)
    relation_name = CharField(required=False)
    geometry_column = CharField(required=False)
    primary_key_column = CharField(required=False)
    label_field = CharField(required=False)
    features_api_basename = CharField(required=False)
    visible_columns = CharField(required=False, widget=Textarea)
    filterable_columns = CharField(required=False, widget=Textarea)
    searchable_columns = CharField(required=False, widget=Textarea)
    exportable_columns = CharField(required=False, widget=Textarea)

    class Meta:
        model = GeoDataset
        fields = (
            "name",
            "publish",
            "model_name",
            "sources",
            "description",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        runtime_configuration = None
        if self.instance and self.instance.pk:
            runtime_configuration = self.instance.get_runtime_configuration()

        self.initial.setdefault(
            "backend_type",
            (
                runtime_configuration.backend_type
                if runtime_configuration
                else "legacy_model"
            ),
        )
        self.initial.setdefault(
            "runtime_model_name",
            (runtime_configuration.runtime_model_name if runtime_configuration else ""),
        )
        self.initial.setdefault(
            "schema_name",
            runtime_configuration.schema_name if runtime_configuration else "",
        )
        self.initial.setdefault(
            "relation_name",
            runtime_configuration.relation_name if runtime_configuration else "",
        )
        self.initial.setdefault(
            "geometry_column",
            runtime_configuration.geometry_column if runtime_configuration else "",
        )
        self.initial.setdefault(
            "primary_key_column",
            (runtime_configuration.primary_key_column if runtime_configuration else ""),
        )
        self.initial.setdefault(
            "label_field",
            runtime_configuration.label_field if runtime_configuration else "",
        )
        self.initial.setdefault(
            "features_api_basename",
            (
                runtime_configuration.features_api_basename
                if runtime_configuration
                else ""
            ),
        )
        self.initial.setdefault(
            "visible_columns",
            "\n".join(self.instance.get_visible_columns())
            if self.instance and self.instance.pk
            else "",
        )
        self.initial.setdefault(
            "filterable_columns",
            "\n".join(self.instance.get_filterable_columns())
            if self.instance and self.instance.pk
            else "",
        )
        self.initial.setdefault(
            "searchable_columns",
            "\n".join(self.instance.get_searchable_columns())
            if self.instance and self.instance.pk
            else "",
        )
        self.initial.setdefault(
            "exportable_columns",
            "\n".join(self.instance.get_exportable_columns())
            if self.instance and self.instance.pk
            else "",
        )

    @staticmethod
    def _parse_column_names(raw_value):
        column_names = []
        seen = set()
        for line in (raw_value or "").splitlines():
            for part in line.split(","):
                column_name = part.strip()
                if column_name and column_name not in seen:
                    seen.add(column_name)
                    column_names.append(column_name)
        return column_names

    def save(self, commit=True):
        instance = super().save(commit=commit)
        runtime_configuration, _ = GeoDatasetRuntimeConfiguration.objects.get_or_create(
            dataset=instance
        )
        runtime_configuration.backend_type = (
            self.cleaned_data.get("backend_type") or "legacy_model"
        )
        runtime_configuration.runtime_model_name = self.cleaned_data.get(
            "runtime_model_name", ""
        )
        runtime_configuration.schema_name = self.cleaned_data.get("schema_name", "")
        runtime_configuration.relation_name = self.cleaned_data.get("relation_name", "")
        runtime_configuration.geometry_column = self.cleaned_data.get(
            "geometry_column", ""
        )
        runtime_configuration.primary_key_column = self.cleaned_data.get(
            "primary_key_column", ""
        )
        runtime_configuration.label_field = self.cleaned_data.get("label_field", "")
        runtime_configuration.features_api_basename = self.cleaned_data.get(
            "features_api_basename", ""
        )
        runtime_configuration.save()

        visible_columns = set(
            self._parse_column_names(self.cleaned_data.get("visible_columns", ""))
        )
        filterable_columns = set(
            self._parse_column_names(self.cleaned_data.get("filterable_columns", ""))
        )
        searchable_columns = set(
            self._parse_column_names(self.cleaned_data.get("searchable_columns", ""))
        )
        exportable_columns = set(
            self._parse_column_names(self.cleaned_data.get("exportable_columns", ""))
        )

        all_columns = (
            visible_columns
            | filterable_columns
            | searchable_columns
            | exportable_columns
        )
        existing_policies = {
            policy.column_name: policy
            for policy in GeoDatasetColumnPolicy.objects.filter(dataset=instance)
        }
        for column_name in all_columns:
            policy = existing_policies.pop(column_name, None)
            if policy is None:
                policy = GeoDatasetColumnPolicy(
                    dataset=instance, column_name=column_name
                )
            policy.is_visible = column_name in visible_columns
            policy.is_filterable = column_name in filterable_columns
            policy.is_searchable = column_name in searchable_columns
            policy.is_exportable = column_name in exportable_columns
            policy.save()

        if existing_policies:
            GeoDatasetColumnPolicy.objects.filter(
                pk__in=[policy.pk for policy in existing_policies.values()]
            ).delete()

        return instance


class LocationModelForm(SimpleModelForm):
    class Meta:
        model = Location
        fields = ("name", "geom", "address")
        widgets = {"geom": LeafletWidget()}


class RegionModelForm(SimpleModelForm):
    geom = MultiPolygonField(widget=LeafletWidget())

    class Meta:
        model = Region
        fields = ("name", "geom", "country", "description")

    def __init__(self, *args, **kwargs):
        instance = kwargs.get("instance")
        super().__init__(*args, **kwargs)
        if (
            instance
            and getattr(instance, "pk", None)
            and instance.geom is not None
            and "geom" not in self.initial
        ):
            self.initial["geom"] = instance.geom

    def save(self, commit=True):
        geom = self.cleaned_data.pop("geom")
        instance = super().save(commit=False)
        instance.geom = geom
        if commit:
            instance.save()
        return instance


class AttributeModelForm(SimpleModelForm):
    class Meta:
        model = Attribute
        fields = ("name", "unit", "description")


class AttributeModalModelForm(ModalModelFormMixin, AttributeModelForm):
    pass


class RegionAttributeValueModelForm(NumericMeasurementFieldsFormMixin, SimpleModelForm):
    measurement_field_names = ("value", "standard_deviation")

    region = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="region-autocomplete",
            label_field="name",
        ),
        label="Region",
    )
    property = TomSelectModelChoiceField(
        queryset=RegionProperty.objects.all(),
        config=TomSelectConfig(
            url="regionproperty-autocomplete",
            label_field="name",
        ),
        label="Property",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["region"].queryset = Region.objects.all()
        self.fields["unit"].required = False

    def clean(self):
        cleaned_data = super().clean()
        property_obj = cleaned_data.get("property")
        value = RegionAttributeValue(
            property=property_obj,
            unit=cleaned_data.get("unit"),
        )

        if not property_obj:
            return cleaned_data

        value.assign_default_unit()
        cleaned_data["unit"] = value.unit
        return cleaned_data

    date = DateField(widget=DateInput(attrs={"type": "date"}))

    class Meta:
        model = RegionAttributeValue
        fields = ("region", "property", "unit", "date", "value", "standard_deviation")


class RegionAttributeValueModalModelForm(
    ModalModelFormMixin, RegionAttributeValueModelForm
):
    pass


# ----------- Catchments -----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CatchmentModelForm(SimpleModelForm):
    region = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="region-autocomplete",
            label_field="name",
        ),
        label="Region",
    )
    parent_region = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="region-autocomplete",
            label_field="name",
        ),
        label="Parent region",
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["region"].queryset = Region.objects.all()
        self.fields["parent_region"].queryset = Region.objects.all()

    class Meta:
        model = Catchment
        fields = ("name", "region", "parent_region", "description")


class CatchmentCreateDrawCustomForm(SimpleModelForm):
    geom = MultiPolygonField(widget=LeafletWidget())
    parent_region = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="region-autocomplete",
            label_field="name",
        ),
        label="Parent region",
        required=False,
    )

    class Meta:
        model = Catchment
        fields = ("name", "geom", "parent_region", "description")

    def save(self, commit=True):
        geom = self.cleaned_data.pop("geom")
        instance = super().save(commit=False)
        borders = GeoPolygon.objects.create(geom=geom)
        instance.region = Region.objects.create(name=instance.name, borders=borders)
        if commit:
            instance.save()
        return instance


class CatchmentCreateMergeLauForm(SimpleModelForm):
    parent_region = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="region-autocomplete",
        ),
        label="Parent region",
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["parent_region"].queryset = Region.objects.all()

    class Meta:
        model = Catchment
        fields = ("name", "parent_region", "description")


class RegionMergeFormHelper(FormHelper):
    form_tag = False
    disable_csrf = True
    layout = Row(Column(Field("region")), css_class="formset-form")


class RegionMergeForm(SimpleForm):
    region = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="region-of-lau-autocomplete",
            label_field="text",
        ),
        label="Regions",
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["region"].queryset = Region.objects.filter(
            pk__in=Subquery(LauRegion.objects.all().values("pk"))
        )


class RegionMergeFormSet(BaseFormSet):
    def clean(self):
        if any(self.errors):
            return
        non_empty_forms = 0
        for form in self.forms:
            if "region" not in form.cleaned_data or not form.cleaned_data["region"]:
                continue
            else:
                non_empty_forms += 1
        if non_empty_forms < 1:
            raise ValidationError("You must select at least one region.")


class CatchmentQueryForm(SimpleForm):
    schema = ChoiceField(
        choices=(
            ("nuts", "NUTS"),
            ("custom", "Custom"),
        ),
        widget=RadioSelect,
    )
    region = ModelChoiceField(queryset=Region.objects.all())
    category = MultipleChoiceField(
        choices=(
            ("standard", "Standard"),
            ("custom", "Custom"),
        ),
        widget=CheckboxSelectMultiple,
    )
    catchment = ModelChoiceField(queryset=Catchment.objects.all())


class NutsRegionQueryForm(SimpleForm):
    level_0 = ModelChoiceField(queryset=NutsRegion.objects.none())
    level_1 = ModelChoiceField(queryset=NutsRegion.objects.none(), required=False)
    level_2 = ModelChoiceField(queryset=NutsRegion.objects.none(), required=False)
    level_3 = ModelChoiceField(queryset=NutsRegion.objects.none(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["level_0"].queryset = NutsRegion.objects.filter(
            levl_code=0
        ).order_by("nuts_id")
        self.fields["level_1"].queryset = NutsRegion.objects.filter(
            levl_code=1
        ).order_by("nuts_id")
        self.fields["level_2"].queryset = NutsRegion.objects.filter(
            levl_code=2
        ).order_by("nuts_id")
        self.fields["level_3"].queryset = NutsRegion.objects.filter(
            levl_code=3
        ).order_by("nuts_id")

    @property
    def helper(self):
        helper = FormHelper()
        helper.layout = Layout(
            Field(
                "level_0",
                data_optionsapi=f"{reverse("data.nuts_region_options")}",
                data_lvl=0,
            ),
            Field(
                "level_1",
                data_optionsapi=f"{reverse("data.nuts_region_options")}",
                data_lvl=1,
            ),
            Field(
                "level_2",
                data_optionsapi=f"{reverse("data.nuts_region_options")}",
                data_lvl=2,
            ),
            Field(
                "level_3",
                data_optionsapi=f"{reverse("data.nuts_region_options")}",
                data_lvl=3,
            ),
        )
        return helper


class NutsAndLauCatchmentQueryForm(SimpleForm):
    region = ModelChoiceField(queryset=Region.objects.none())
    catchment = ModelChoiceField(queryset=Catchment.objects.none())
    level_0 = ModelChoiceField(queryset=Catchment.objects.none())
    level_1 = ModelChoiceField(queryset=Catchment.objects.none(), required=False)
    level_2 = ModelChoiceField(queryset=Catchment.objects.none(), required=False)
    level_3 = ModelChoiceField(queryset=Catchment.objects.none(), required=False)
    level_4 = ModelChoiceField(queryset=Catchment.objects.none(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["region"].queryset = Region.objects.all()
        self.fields["catchment"].queryset = Catchment.objects.all()
        self.fields["level_0"].queryset = Catchment.objects.filter(
            region__nutsregion__levl_code=0
        )
        self.fields["level_1"].queryset = Catchment.objects.filter(
            region__nutsregion__levl_code=1
        )
        self.fields["level_2"].queryset = Catchment.objects.filter(
            region__nutsregion__levl_code=2
        )
        self.fields["level_3"].queryset = Catchment.objects.filter(
            region__nutsregion__levl_code=3
        )
        self.fields["level_4"].queryset = Catchment.objects.none()

    @property
    def helper(self):
        helper = FormHelper()
        helper.layout = Layout(
            Field(
                "level_0",
                data_optionsapi=f"{reverse("data.nuts_lau_catchment_options")}",
                data_lvl=0,
            ),
            Field(
                "level_1",
                data_optionsapi=f"{reverse("data.nuts_lau_catchment_options")}",
                data_lvl=1,
            ),
            Field(
                "level_2",
                data_optionsapi=f"{reverse("data.nuts_lau_catchment_options")}",
                data_lvl=2,
            ),
            Field(
                "level_3",
                data_optionsapi=f"{reverse("data.nuts_lau_catchment_options")}",
                data_lvl=3,
            ),
            Field("level_4", data_lvl=4),
        )
        return helper
