from datetime import timedelta

from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Column, Div, Field, Layout, Row
from django.core.exceptions import ValidationError
from django.forms import (
    CheckboxSelectMultiple,
    ChoiceField,
    DateInput,
    HiddenInput,
    IntegerField,
    ModelChoiceField,
    ModelMultipleChoiceField,
    RadioSelect,
)
from django.utils.translation import gettext as _

from distributions.models import TemporalDistribution, Timestep
from materials.models import Material, Sample
from utils.crispy_fields import ForeignkeyField
from utils.forms import (
    AutoCompleteModelForm,
    CreateInlineMixin,
    M2MInlineFormSet,
    ModalModelFormMixin,
    SimpleForm,
    SimpleModelForm,
)
from utils.models import get_default_owner
from utils.widgets import BSModelSelect2, BSModelSelect2Multiple

from .models import (
    CONNECTION_TYPE_CHOICES,
    REQUIRED_BIN_CAPACITY_REFERENCE_CHOICES,
    AggregatedCollectionPropertyValue,
    Collection,
    CollectionCatchment,
    CollectionCountOptions,
    CollectionFrequency,
    CollectionPropertyValue,
    CollectionSeason,
    CollectionSystem,
    Collector,
    FeeSystem,
    WasteCategory,
    WasteComponent,
    WasteFlyer,
    WasteStream,
)


class CollectorModelForm(AutoCompleteModelForm):
    catchment = ModelChoiceField(
        queryset=CollectionCatchment.objects.all(),
        widget=BSModelSelect2(url="catchment-autocomplete"),
        required=False,
    )

    class Meta:
        model = Collector
        fields = ("name", "website", "catchment", "description")


class CollectorModalModelForm(ModalModelFormMixin, CollectorModelForm):
    pass


class CollectionSystemModelForm(SimpleModelForm):
    class Meta:
        model = CollectionSystem
        fields = ("name", "description")


class CollectionSystemModalModelForm(ModalModelFormMixin, CollectionSystemModelForm):
    pass


class WasteCategoryModelForm(SimpleModelForm):
    class Meta:
        model = WasteCategory
        fields = ("name", "description")


class WasteCategoryModalModelForm(ModalModelFormMixin, WasteCategoryModelForm):
    pass


class WasteComponentModelForm(SimpleModelForm):
    class Meta:
        model = WasteComponent
        fields = ("name", "description")


class WasteComponentModalModelForm(ModalModelFormMixin, WasteComponentModelForm):
    pass


class FeeSystemModelForm(SimpleModelForm):
    class Meta:
        model = FeeSystem
        fields = ("name", "description")


class FeeSystemModalModelForm(ModalModelFormMixin, FeeSystemModelForm):
    pass


class CollectionFrequencyModelForm(SimpleModelForm):
    class Meta:
        model = CollectionFrequency
        fields = ("name", "type", "description")


class CollectionFrequencyModalModelForm(
    ModalModelFormMixin, CollectionFrequencyModelForm
):
    pass


class CollectionSeasonFormHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_tag = False
        self.disable_csrf = True
        self.layout = Layout(
            Div(
                HTML(
                    '<p><strong class="title-strong">Season {{ forloop.counter }}</strong></p>'
                ),
                "distribution",
                Row(Column(Field("first_timestep")), Column(Field("last_timestep"))),
                HTML("<p>Total collections in this season</p>"),
                Row(
                    Column(Field("standard")),
                    Column(Field("option_1")),
                    Column(Field("option_2")),
                    Column(Field("option_3")),
                    css_class="formset-form",
                ),
            )
        )


class CollectionSeasonForm(SimpleForm):
    distribution = ModelChoiceField(
        queryset=TemporalDistribution.objects.none(),
        initial=None,
        empty_label=None,
        widget=HiddenInput(),
    )
    first_timestep = ModelChoiceField(queryset=Timestep.objects.none(), label="Start")
    last_timestep = ModelChoiceField(queryset=Timestep.objects.none(), label="End")
    standard = IntegerField(required=False, min_value=0)
    option_1 = IntegerField(required=False, min_value=0)
    option_2 = IntegerField(required=False, min_value=0)
    option_3 = IntegerField(required=False, min_value=0)

    class Meta:
        fields = (
            "distribution",
            "first_timestep",
            "last_timestep",
            "standard",
            "option_1",
            "option_2",
            "option_3",
        )

    def __init__(self, *args, **kwargs):
        super(CollectionSeasonForm, self).__init__(*args, **kwargs)
        self.fields["distribution"].queryset = TemporalDistribution.objects.filter(
            name="Months of the year"
        )
        try:
            self.fields["distribution"].initial = TemporalDistribution.objects.get(
                name="Months of the year"
            )
        except TemporalDistribution.DoesNotExist:
            pass
        distribution_qs = TemporalDistribution.objects.filter(name="Months of the year")
        if distribution_qs.exists():
            distribution = distribution_qs.first()
            self.fields["first_timestep"].queryset = Timestep.objects.filter(
                distribution=distribution
            )
            self.fields["last_timestep"].queryset = Timestep.objects.filter(
                distribution=distribution
            )
        else:
            self.fields["first_timestep"].queryset = Timestep.objects.none()
            self.fields["last_timestep"].queryset = Timestep.objects.none()

    def save(self):
        self.instance, _ = CollectionSeason.objects.get_or_create(
            distribution=self.cleaned_data["distribution"],
            first_timestep=self.cleaned_data["first_timestep"],
            last_timestep=self.cleaned_data["last_timestep"],
        )
        return self.instance


class CollectionSeasonFormSet(M2MInlineFormSet):

    def clean(self):
        for i, form in enumerate(self.forms):
            if (
                i > 0
                and self.forms[i - 1].cleaned_data.get("last_timestep").order
                >= self.forms[i].cleaned_data.get("first_timestep").order
            ):
                raise ValidationError(
                    _("The seasons must not overlap and must be given in order."),
                    code="invalid",
                )

    def save(self, commit=True):
        child_objects = super().save(commit=commit)

        for form in self.forms:
            options = CollectionCountOptions.objects.get(
                frequency=self.parent_object, season=form.instance
            )
            options.standard = form.cleaned_data["standard"]
            options.option_1 = form.cleaned_data["option_1"]
            options.option_2 = form.cleaned_data["option_2"]
            options.option_3 = form.cleaned_data["option_3"]
            options.save()

        CollectionSeason.objects.exclude(
            distribution=TemporalDistribution.objects.get(name="Months of the year"),
            first_timestep=Timestep.objects.get(name="January"),
            last_timestep=Timestep.objects.get(name="December"),
        ).filter(collectionfrequency=None).delete()
        return child_objects


class WasteFlyerModelForm(SimpleModelForm):
    class Meta:
        model = WasteFlyer
        fields = ("url",)
        labels = {"url": "Sources (Urls)"}

    def save(self, commit=True):
        if commit:
            defaults = {
                "owner": self.instance.owner,
                "title": "Waste flyer",
                "abbreviation": "WasteFlyer",
            }
            url = self.cleaned_data.get("url")
            if url:
                instance, _ = WasteFlyer.objects.get_or_create(
                    url=self.cleaned_data["url"], defaults=defaults
                )
                return instance
        else:
            return super().save(commit=False)


class WasteFlyerModalModelForm(ModalModelFormMixin, WasteFlyerModelForm):
    pass


class BaseWasteFlyerUrlFormSet(M2MInlineFormSet):

    def __init__(self, *args, **kwargs):
        self.owner = kwargs.pop("owner", get_default_owner())
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        child_objects = super().save(commit=commit)
        WasteFlyer.objects.filter(collections=None).delete()
        return child_objects


class CollectionPropertyValueModelForm(AutoCompleteModelForm):
    class Meta:
        model = CollectionPropertyValue
        fields = (
            "collection",
            "property",
            "unit",
            "year",
            "average",
            "standard_deviation",
        )
        widgets = {
            "collection": BSModelSelect2(url="collection-autocomplete"),
        }


class AggregatedCollectionPropertyValueModelForm(AutoCompleteModelForm):
    class Meta:
        model = AggregatedCollectionPropertyValue
        fields = (
            "collections",
            "property",
            "unit",
            "year",
            "average",
            "standard_deviation",
        )
        widgets = {"collections": BSModelSelect2Multiple(url="collection-autocomplete")}


class CollectionModelFormHelper(FormHelper):
    form_tag = False
    layout = Layout(
        Field("catchment"),
        ForeignkeyField("collector"),
        ForeignkeyField("collection_system"),
        ForeignkeyField("waste_category"),
        Field("connection_type"),
        Field("allowed_materials"),
        Field("forbidden_materials"),
        ForeignkeyField("fee_system"),
        Field("frequency"),
        Field("min_bin_size"),
        Field("required_bin_capacity"),
        Field("required_bin_capacity_reference"),
        Field("valid_from"),
        Field("valid_until"),
        Field("description"),
    )


class CollectionModelForm(CreateInlineMixin, AutoCompleteModelForm):
    """
    Model form for Collection, including all collection parameters and waste stream fields.
    """

    catchment = ModelChoiceField(
        queryset=CollectionCatchment.objects.all(),
        widget=BSModelSelect2(url="catchment-autocomplete"),
        required=True,
    )
    collector = ModelChoiceField(
        queryset=Collector.objects.all(),
        widget=BSModelSelect2(url="collector-autocomplete"),
        required=True,
    )
    collection_system = ModelChoiceField(
        queryset=CollectionSystem.objects.all(), required=True
    )
    waste_category = ModelChoiceField(queryset=WasteCategory.objects.all())
    allowed_materials = ModelMultipleChoiceField(
        queryset=WasteComponent.objects.all(),
        widget=CheckboxSelectMultiple,
        required=False,
    )
    forbidden_materials = ModelMultipleChoiceField(
        queryset=WasteComponent.objects.all(),
        widget=CheckboxSelectMultiple,
        required=False,
    )
    frequency = ModelChoiceField(
        queryset=CollectionFrequency.objects.all(),
        widget=BSModelSelect2(url="collectionfrequency-autocomplete"),
        required=False,
    )
    fee_system = ModelChoiceField(queryset=FeeSystem.objects.all(), required=False)
    connection_type = ChoiceField(
        choices=[("", "---------")] + list(CONNECTION_TYPE_CHOICES),
        required=False,
        label="Connection type",
        help_text="Indicates whether connection to the collection system is mandatory, voluntary, or not specified. Leave blank for never set; select 'not specified' for explicit user choice.",
    )
    min_bin_size = IntegerField(required=False, min_value=0)
    required_bin_capacity = IntegerField(required=False, min_value=0)
    required_bin_capacity_reference = ChoiceField(
        choices=[("", "---------")] + REQUIRED_BIN_CAPACITY_REFERENCE_CHOICES,
        required=False,
        label="Reference unit for required bin capacity",
        help_text="Defines the unit (person, household, property) for which the required bin capacity applies. Leave blank if not specified.",
    )

    class Meta:
        model = Collection
        fields = (
            "catchment",
            "collector",
            "collection_system",
            "waste_category",
            "connection_type",
            "allowed_materials",
            "forbidden_materials",
            "frequency",
            "fee_system",
            "valid_from",
            "valid_until",
            "description",
            "min_bin_size",
            "required_bin_capacity",
            "required_bin_capacity_reference",
        )
        labels = {
            "description": "Comments",
            "connection_type": "Connection type",
        }
        widgets = {
            "valid_from": DateInput(attrs={"type": "date"}),
            "valid_until": DateInput(attrs={"type": "date"}),
            "connection_type": RadioSelect,
        }
        form_helper_class = CollectionModelFormHelper

    def save(self, commit=True):
        """
        Save the collection, ensuring waste stream and predecessor handling.
        """
        instance = super().save(commit=False)
        data = self.cleaned_data
        instance.name = (
            f'{data["catchment"]} {data["waste_category"]} {data["collection_system"]}'
        )
        allowed_materials = Material.objects.filter(id__in=data["allowed_materials"])
        if not allowed_materials.exists():
            allowed_materials = Material.objects.none()
        forbidden_materials = Material.objects.filter(
            id__in=data["forbidden_materials"]
        )
        if not forbidden_materials.exists():
            forbidden_materials = Material.objects.none()
        waste_stream, created = WasteStream.objects.get_or_create(
            defaults={"owner": instance.owner},
            category=data["waste_category"],
            allowed_materials=allowed_materials,
            forbidden_materials=forbidden_materials,
        )
        if created:
            waste_stream.allowed_materials.add(*data["allowed_materials"])
            waste_stream.forbidden_materials.add(*data["forbidden_materials"])
        waste_stream.save()
        instance.waste_stream = waste_stream
        if commit:
            instance.save()
            for predecessor in instance.predecessors.all():
                valid_until = instance.valid_from - timedelta(days=1)
                predecessor.valid_until = valid_until
                predecessor.full_clean()
                predecessor.save()
            return super().save()
        else:
            return super().save(commit=False)


class CollectionAddWasteSampleForm(AutoCompleteModelForm):
    sample = ModelChoiceField(
        queryset=Sample.objects.all(), widget=BSModelSelect2(url="sample-autocomplete")
    )

    class Meta:
        model = Sample
        fields = ("sample",)


class CollectionRemoveWasteSampleForm(SimpleModelForm):
    sample = ModelChoiceField(queryset=Sample.objects.all())

    class Meta:
        model = Collection
        fields = ("sample",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sample"].queryset = Sample.objects.filter(
            collections=self.instance
        )


class CollectionAddPredecessorForm(AutoCompleteModelForm):
    """
    This form is used to add a predecessor to a Collection instance. A predecessor is a Collection instance that
    was replaced by the current Collection instance.

    Fields:
    predecessor: A ModelChoiceField that represents the predecessor to be added.
                 The queryset for this field is all Collection instances.
                 The widget used is ModelSelect2 with 'collection-autocomplete' as the url,
                 which provides autocomplete functionality.
    """

    predecessor = ModelChoiceField(
        queryset=Collection.objects.all(),
        widget=BSModelSelect2(url="collection-autocomplete"),
    )

    class Meta:
        model = Collection
        fields = ("predecessor",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["predecessor"].queryset = Collection.objects.exclude(
            id=self.instance.id
        )


class CollectionRemovePredecessorForm(SimpleModelForm):
    """
    This form is used to remove a predecessor from a Collection instance. A predecessor is a Collection instance that
    was replaced by the current Collection instance.

    Fields:
    predecessor: A ModelChoiceField that represents the predecessor collection to be removed.
    """

    predecessor = ModelChoiceField(queryset=Collection.objects.all())

    class Meta:
        model = Collection
        fields = ("predecessor",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["predecessor"].queryset = Collection.objects.filter(
            successors=self.instance
        )
