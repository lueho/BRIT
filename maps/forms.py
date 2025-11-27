from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Field, Layout, Row
from django.contrib.gis.forms import MultiPolygonField
from django.db.models import Subquery
from django.forms import (
    BaseFormSet,
    ChoiceField,
    DateField,
    DateInput,
    ModelChoiceField,
    MultipleChoiceField,
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

from .models import (
    Attribute,
    Catchment,
    GeoDataset,
    GeoPolygon,
    LauRegion,
    Location,
    NutsRegion,
    Region,
    RegionAttributeValue,
)


class GeoDataSetModelForm(
    UserCreatedObjectFormMixin, SourcesFieldMixin, SimpleModelForm
):
    # sources field and __init__ logic provided by SourcesFieldMixin

    class Meta:
        model = GeoDataset
        fields = ("name", "publish", "model_name", "sources", "description")


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

    def save(self, commit=True):
        geom = self.cleaned_data.pop("geom")
        instance = super().save(commit=False)
        instance.borders = GeoPolygon.objects.create(geom=geom)
        if commit:
            instance.save()
        return instance


class AttributeModelForm(SimpleModelForm):
    class Meta:
        model = Attribute
        fields = ("name", "unit", "description")


class AttributeModalModelForm(ModalModelFormMixin, AttributeModelForm):
    pass


class RegionAttributeValueModelForm(SimpleModelForm):
    region = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="region-autocomplete",
            label_field="name",
        ),
        label="Region",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["region"].queryset = Region.objects.all()

    date = DateField(widget=DateInput(attrs={"type": "date"}))

    class Meta:
        model = RegionAttributeValue
        fields = ("region", "attribute", "date", "value", "standard_deviation")


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
                data_optionsapi=f"{reverse('data.nuts_region_options')}",
                data_lvl=0,
            ),
            Field(
                "level_1",
                data_optionsapi=f"{reverse('data.nuts_region_options')}",
                data_lvl=1,
            ),
            Field(
                "level_2",
                data_optionsapi=f"{reverse('data.nuts_region_options')}",
                data_lvl=2,
            ),
            Field(
                "level_3",
                data_optionsapi=f"{reverse('data.nuts_region_options')}",
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
                data_optionsapi=f"{reverse('data.nuts_lau_catchment_options')}",
                data_lvl=0,
            ),
            Field(
                "level_1",
                data_optionsapi=f"{reverse('data.nuts_lau_catchment_options')}",
                data_lvl=1,
            ),
            Field(
                "level_2",
                data_optionsapi=f"{reverse('data.nuts_lau_catchment_options')}",
                data_lvl=2,
            ),
            Field(
                "level_3",
                data_optionsapi=f"{reverse('data.nuts_lau_catchment_options')}",
                data_lvl=3,
            ),
            Field("level_4", data_lvl=4),
        )
        return helper
