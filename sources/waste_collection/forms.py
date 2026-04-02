from datetime import timedelta

from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Column, Div, Field, Layout, Row
from django.core.exceptions import ValidationError
from django.db.models import Case, Value, When
from django.db.models import IntegerField as DBIntegerField
from django.forms import (
    BooleanField,
    CheckboxSelectMultiple,
    ChoiceField,
    DateInput,
    DecimalField,
    HiddenInput,
    IntegerField,
    ModelChoiceField,
    ModelMultipleChoiceField,
    NumberInput,
    RadioSelect,
)
from django.utils.translation import gettext as _
from django_tomselect.forms import (
    TomSelectConfig,
    TomSelectModelChoiceField,
    TomSelectModelMultipleChoiceField,
)

from distributions.models import TemporalDistribution, Timestep
from materials.models import Sample
from sources.waste_collection.description_formatting import (
    normalize_collection_description,
)
from sources.waste_collection.frequency_service import (
    CADENCE_CHOICES,
    CADENCE_CUSTOM,
    CollectionFrequencyScheduleService,
)
from sources.waste_collection.models import (
    CONNECTION_TYPE_CHOICES,
    REQUIRED_BIN_CAPACITY_REFERENCE_CHOICES,
    AggregatedCollectionPropertyValue,
    Collection,
    CollectionCountOptions,
    CollectionFrequency,
    CollectionPropertyValue,
    CollectionSeason,
    CollectionSystem,
    Collector,
    FeeSystem,
    SortingMethod,
    WasteCategory,
    WasteComponent,
    WasteFlyer,
)
from sources.waste_collection.tasks import cleanup_orphaned_waste_flyers
from utils.crispy_fields import ForeignkeyField
from utils.forms import (
    MARKDOWN_HELP_TEXT,
    CreateInlineMixin,
    DynamicTableInlineFormSetHelper,
    M2MInlineFormSet,
    ModalModelFormMixin,
    SimpleForm,
    SimpleModelForm,
    SourcesFieldMixin,
    UserCreatedObjectFormMixin,
)
from utils.object_management.models import get_default_owner
from utils.properties.forms import NumericMeasurementFieldsFormMixin


class CollectorModelForm(SimpleModelForm):
    catchment = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="catchment-autocomplete",
            label_field="name",
        ),
        label="Catchment",
        required=False,
    )

    class Meta:
        model = Collector
        fields = ("name", "website", "catchment", "description")
        help_texts = {"description": MARKDOWN_HELP_TEXT}


class CollectorModalModelForm(ModalModelFormMixin, CollectorModelForm):
    pass


class CollectionSystemModelForm(SimpleModelForm):
    class Meta:
        model = CollectionSystem
        fields = ("name", "description")
        help_texts = {"description": MARKDOWN_HELP_TEXT}


class CollectionSystemModalModelForm(ModalModelFormMixin, CollectionSystemModelForm):
    pass


class SortingMethodModelForm(SimpleModelForm):
    class Meta:
        model = SortingMethod
        fields = ("name", "description")
        help_texts = {"description": MARKDOWN_HELP_TEXT}


class SortingMethodModalModelForm(ModalModelFormMixin, SortingMethodModelForm):
    pass


class WasteCategoryModelForm(SimpleModelForm):
    class Meta:
        model = WasteCategory
        fields = ("name", "description")
        help_texts = {"description": MARKDOWN_HELP_TEXT}


class WasteCategoryModalModelForm(ModalModelFormMixin, WasteCategoryModelForm):
    pass


class WasteComponentModelForm(SimpleModelForm):
    class Meta:
        model = WasteComponent
        fields = ("name", "description")
        help_texts = {"description": MARKDOWN_HELP_TEXT}


class WasteComponentModalModelForm(ModalModelFormMixin, WasteComponentModelForm):
    pass


class FeeSystemModelForm(SimpleModelForm):
    class Meta:
        model = FeeSystem
        fields = ("name", "description")
        help_texts = {"description": MARKDOWN_HELP_TEXT}


class FeeSystemModalModelForm(ModalModelFormMixin, FeeSystemModelForm):
    pass


class CollectionFrequencyModelForm(SimpleModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].required = False
        self.fields["description"].widget.attrs["rows"] = 4

    class Meta:
        model = CollectionFrequency
        fields = ("name", "type", "description")
        labels = {"name": "Label"}
        help_texts = {
            "name": "Optional. Leave blank to generate a canonical label from the schedule.",
            "description": MARKDOWN_HELP_TEXT,
        }
        widgets = {"type": HiddenInput()}


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
                HTML(
                    "<p>Choose a cadence or enter a custom annual total for this period.</p>"
                ),
                Row(
                    Column(Field("standard_cadence")),
                    Column(Field("standard")),
                    css_class="formset-form",
                ),
                HTML("<p>Optional service levels</p>"),
                Row(
                    Column(Field("option_1_cadence")),
                    Column(Field("option_1")),
                    Column(Field("option_2_cadence")),
                    Column(Field("option_2")),
                    Column(Field("option_3_cadence")),
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
    standard_cadence = ChoiceField(
        choices=CADENCE_CHOICES,
        required=False,
        label="Standard cadence",
    )
    standard = IntegerField(required=False, min_value=0, label="Standard annual total")
    option_1_cadence = ChoiceField(
        choices=CADENCE_CHOICES,
        required=False,
        label="Optional cadence 1",
    )
    option_1 = IntegerField(
        required=False, min_value=0, label="Optional annual total 1"
    )
    option_2_cadence = ChoiceField(
        choices=CADENCE_CHOICES,
        required=False,
        label="Optional cadence 2",
    )
    option_2 = IntegerField(
        required=False, min_value=0, label="Optional annual total 2"
    )
    option_3_cadence = ChoiceField(
        choices=CADENCE_CHOICES,
        required=False,
        label="Optional cadence 3",
    )
    option_3 = IntegerField(
        required=False, min_value=0, label="Optional annual total 3"
    )

    class Meta:
        fields = (
            "distribution",
            "first_timestep",
            "last_timestep",
            "standard_cadence",
            "standard",
            "option_1_cadence",
            "option_1",
            "option_2_cadence",
            "option_2",
            "option_3_cadence",
            "option_3",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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

        first_timestep = self.initial.get("first_timestep")
        last_timestep = self.initial.get("last_timestep")
        if first_timestep and last_timestep:
            for field_name in ("standard", "option_1", "option_2", "option_3"):
                cadence_field = f"{field_name}_cadence"
                if self.initial.get(cadence_field) in (None, ""):
                    self.initial[cadence_field] = (
                        CollectionFrequencyScheduleService.infer_cadence(
                            self.initial.get(field_name),
                            first_timestep,
                            last_timestep,
                        )
                    )

        for field_name in ("standard", "option_1", "option_2", "option_3"):
            self.fields[field_name].help_text = ""
            self.fields[field_name].widget.attrs["placeholder"] = "Only for custom"

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data = CollectionFrequencyScheduleService.populate_counts_from_cadences(
            cleaned_data
        )
        for field_name in ("standard", "option_1", "option_2", "option_3"):
            cadence_field = f"{field_name}_cadence"
            if cleaned_data.get(cadence_field) == CADENCE_CUSTOM and cleaned_data.get(
                field_name
            ) in (None, ""):
                self.add_error(
                    field_name,
                    "Enter a custom annual total or choose a cadence preset.",
                )
        return cleaned_data

    def save(self):
        self.instance, _ = CollectionSeason.objects.get_or_create(
            distribution=self.cleaned_data["distribution"],
            first_timestep=self.cleaned_data["first_timestep"],
            last_timestep=self.cleaned_data["last_timestep"],
        )
        return self.instance


class CollectionSeasonFormSet(M2MInlineFormSet):
    def clean(self):
        for i, _form in enumerate(self.forms):
            if (
                i > 0
                and self.forms[i - 1].cleaned_data.get("last_timestep")
                and self.forms[i].cleaned_data.get("first_timestep")
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
        labels = {"url": "URL"}

    def save(self, commit=True):
        if commit:
            defaults = {
                "owner": self.instance.owner,
                "title": "Waste flyer",
                "abbreviation": "WasteFlyer",
            }
            url = self.cleaned_data.get("url")
            if url:
                instance, _ = WasteFlyer.objects.get_or_create_by_url(
                    url=self.cleaned_data["url"], defaults=defaults
                )
                return instance
        else:
            return super().save(commit=False)


class WasteFlyerModalModelForm(ModalModelFormMixin, WasteFlyerModelForm):
    pass


class WasteFlyerFormSetHelper(DynamicTableInlineFormSetHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.legend = (
            '<i class="fas fa-link me-1"></i> Waste Management Documents (URLs)'
        )
        self.help_text = "Quick links to waste management flyers, collection schedules, or municipal documents. URLs are automatically saved as references."
        self.form_show_labels = True


class WasteFlyerFormSet(M2MInlineFormSet):
    def __init__(self, *args, **kwargs):
        self.owner = kwargs.pop("owner", get_default_owner())
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        parent_object = getattr(self, "parent_object", None)
        relation_field_name = getattr(self, "relation_field_name", None)
        existing_ids: set[int] = set()
        if parent_object and relation_field_name:
            existing_ids = set(
                getattr(parent_object, relation_field_name).values_list("id", flat=True)
            )

        for form in self.forms:
            if not getattr(form.instance, "owner", None):
                form.instance.owner = self.owner

        child_objects = super().save(commit=commit)
        new_ids = {obj.id for obj in child_objects if obj and obj.id}
        flyers_changed = existing_ids != new_ids
        if commit and flyers_changed:
            cleanup_orphaned_waste_flyers.delay()

        return child_objects


class CollectionPropertyValueModelFormHelper(FormHelper):
    form_tag = False
    layout = Layout(
        Field("collection"),
        Field("property"),
        Field("unit"),
        Field("year"),
        Field("average"),
        Field("standard_deviation"),
        Div(
            Field("sources", template="bootstrap5/field_no_label.html"),
            css_class="mt-4",
        ),
    )


class CollectionPropertyValueModelForm(
    NumericMeasurementFieldsFormMixin,
    UserCreatedObjectFormMixin,
    SourcesFieldMixin,
    SimpleModelForm,
):
    collection = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="collection-autocomplete",
            label_field="name",
        ),
        label="Collection",
    )

    class Meta:
        model = CollectionPropertyValue
        fields = (
            "collection",
            "property",
            "unit",
            "year",
            "average",
            "standard_deviation",
            "sources",
        )
        form_helper_class = CollectionPropertyValueModelFormHelper


class AggregatedCollectionPropertyValueModelFormHelper(FormHelper):
    form_tag = False
    layout = Layout(
        Field("collections"),
        Field("property"),
        Field("unit"),
        Field("year"),
        Field("average"),
        Field("standard_deviation"),
        Div(
            Field("sources", template="bootstrap5/field_no_label.html"),
            css_class="mt-4",
        ),
    )


class AggregatedCollectionPropertyValueModelForm(
    NumericMeasurementFieldsFormMixin,
    UserCreatedObjectFormMixin,
    SourcesFieldMixin,
    SimpleModelForm,
):
    collections = TomSelectModelMultipleChoiceField(
        config=TomSelectConfig(
            url="collection-autocomplete",
            label_field="name",
        ),
        label="Collections",
    )

    class Meta:
        model = AggregatedCollectionPropertyValue
        fields = (
            "collections",
            "property",
            "unit",
            "year",
            "average",
            "standard_deviation",
            "sources",
        )
        form_helper_class = AggregatedCollectionPropertyValueModelFormHelper


class CollectionModelFormHelper(FormHelper):
    form_tag = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout_fields = [
            Field("catchment"),
            ForeignkeyField("collector"),
            ForeignkeyField("collection_system"),
            Field("sorting_method"),
            ForeignkeyField("waste_category"),
            Field("connection_type"),
            Field("allowed_materials"),
            Field("forbidden_materials"),
            Field("samples"),
            ForeignkeyField("fee_system"),
            Field("frequency"),
            Field("min_bin_size"),
            Field("required_bin_capacity"),
            Field("required_bin_capacity_reference"),
            Field("established"),
            Field("valid_from"),
            Field("valid_until"),
            Field("description"),
        ]
        form = getattr(self, "form", None)
        if form is not None and "reviewed_predecessor_evidence" in form.fields:
            layout_fields.append(Field("reviewed_predecessor_evidence"))
        layout_fields.append(
            Div(
                Field("sources", template="bootstrap5/field_no_label.html"),
                css_class="mt-4",
            )
        )
        self.layout = Layout(*layout_fields)


class CollectionModelForm(
    UserCreatedObjectFormMixin, SourcesFieldMixin, CreateInlineMixin, SimpleModelForm
):
    _WASTE_COMPONENT_ORDER = {
        "Food waste: Non-processed animal-based": 10,
        "Food waste: Non-processed plant-based": 20,
        "Food waste: Processed animal-based": 30,
        "Food waste: Processed plant-based": 40,
        "Garden waste: Hard materials": 50,
        "Garden waste: Soft materials": 60,
        "Collection Support Item: Biodegradable plastic bags": 70,
        "Collection Support Item: Paper bags": 80,
        "Collection Support Item: Newspaper": 90,
        "Collection Support Item: Plastic bags": 100,
        "Other: Paper tissue": 110,
        "Other: Soil": 120,
    }

    def __init__(self, *args, predecessor=None, **kwargs):
        self.predecessor = predecessor
        super().__init__(*args, **kwargs)
        qs = self._ordered_waste_component_qs()
        self.fields["allowed_materials"].queryset = qs
        self.fields["forbidden_materials"].queryset = qs
        if self.predecessor is not None:
            carry_over_fields = self.predecessor.carried_over_version_review_fields()
            self.fields["reviewed_predecessor_evidence"] = BooleanField(
                required=bool(carry_over_fields),
                label=_("I reviewed the carried-over evidence for this new version"),
                help_text=(
                    "Review the predecessor evidence before saving this version. "
                    f"Fields with carried-over evidence: {', '.join(carry_over_fields)}."
                    if carry_over_fields
                    else "No evidence-backed predecessor fields need confirmation."
                ),
            )
        if not self.is_bound:
            description = self.initial.get("description")
            if description is None and getattr(self.instance, "description", None):
                description = self.instance.description
            if description:
                normalized_description = normalize_collection_description(description)
                self.initial["description"] = normalized_description
                self.fields["description"].initial = normalized_description
        self.helper = self.Meta.form_helper_class(self)

    def clean_description(self):
        return normalize_collection_description(self.cleaned_data.get("description"))

    def clean(self):
        cleaned_data = super().clean()
        if self.predecessor is None:
            return cleaned_data

        carry_over_fields = self.predecessor.carried_over_version_review_fields()
        if carry_over_fields and not cleaned_data.get("reviewed_predecessor_evidence"):
            self.add_error(
                "reviewed_predecessor_evidence",
                _(
                    "Confirm that you reviewed all carried-over predecessor evidence before creating a new version."
                ),
            )
        return cleaned_data

    @classmethod
    def _ordered_waste_component_qs(cls):
        whens = [
            When(name=name, then=Value(pos))
            for name, pos in cls._WASTE_COMPONENT_ORDER.items()
        ]
        return WasteComponent.objects.annotate(
            _display_order=Case(
                *whens,
                default=Value(999),
                output_field=DBIntegerField(),
            )
        ).order_by("_display_order", "name")

    catchment = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="collectioncatchment-autocomplete",
            label_field="name",
        ),
        label="Catchment",
        required=True,
    )
    collector = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="collector-autocomplete",
            label_field="name",
        ),
        label="Collector",
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
    samples = TomSelectModelMultipleChoiceField(
        config=TomSelectConfig(
            url="sample-autocomplete",
            label_field="name",
        ),
        required=False,
        label="Samples",
    )
    frequency = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="collectionfrequency-autocomplete",
            label_field="name",
        ),
        required=False,
    )
    fee_system = ModelChoiceField(queryset=FeeSystem.objects.all(), required=False)
    connection_type = ChoiceField(
        choices=[("", "---------")] + list(CONNECTION_TYPE_CHOICES),
        required=False,
        label="Connection type",
        help_text="Indicates whether connection to the collection system is mandatory, voluntary, or not specified. Leave blank for never set; select 'not specified' for explicit user choice.",
    )
    min_bin_size = DecimalField(
        required=False,
        min_value=0,
        max_digits=8,
        decimal_places=1,
        widget=NumberInput(attrs={"step": "0.1", "min": "0"}),
    )
    required_bin_capacity = DecimalField(
        required=False,
        min_value=0,
        max_digits=8,
        decimal_places=1,
        label="Minimum required specific bin capacity (L/reference unit)",
        widget=NumberInput(attrs={"step": "0.1", "min": "0"}),
    )
    required_bin_capacity_reference = ChoiceField(
        choices=[("", "---------")] + REQUIRED_BIN_CAPACITY_REFERENCE_CHOICES,
        required=False,
        label="Reference unit for minimum required specific bin capacity",
        help_text="Defines the unit (person, household, property) for which the required bin capacity applies. Leave blank if not specified.",
    )
    sorting_method = ModelChoiceField(
        queryset=SortingMethod.objects.all(), required=False, label="Sorting method"
    )
    established = IntegerField(
        required=False,
        min_value=1800,
        max_value=2100,
        label="Year established",
        help_text="Year when this collection scheme was first introduced.",
    )

    class Meta:
        model = Collection
        fields = (
            "catchment",
            "collector",
            "collection_system",
            "sorting_method",
            "waste_category",
            "connection_type",
            "allowed_materials",
            "forbidden_materials",
            "frequency",
            "fee_system",
            "established",
            "valid_from",
            "valid_until",
            "description",
            "min_bin_size",
            "required_bin_capacity",
            "required_bin_capacity_reference",
            "samples",
            "sources",
        )
        labels = {
            "description": "Comments",
            "connection_type": "Connection type",
        }
        help_texts = {"description": MARKDOWN_HELP_TEXT}
        widgets = {
            "valid_from": DateInput(attrs={"type": "date"}),
            "valid_until": DateInput(attrs={"type": "date"}),
            "connection_type": RadioSelect,
        }
        form_helper_class = CollectionModelFormHelper

    def save(self, commit=True):
        instance = super().save(commit=False)
        data = self.cleaned_data
        instance.name = (
            f"{data['catchment']} {data['waste_category']} {data['collection_system']}"
        )
        instance.waste_category = data["waste_category"]
        if commit:
            instance.save()
            for predecessor in instance.predecessors.all():
                valid_until = instance.valid_from - timedelta(days=1)
                predecessor.valid_until = valid_until
                predecessor.save(update_fields=["valid_until", "lastmodified_at"])
            self.save_m2m()
            return instance
        else:
            return instance


class CollectionAddWasteSampleForm(SimpleModelForm):
    sample = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="sample-autocomplete",
            label_field="name",
        ),
        label="Sample",
        help_text="Add a sample directly to this collection.",
    )

    class Meta:
        model = Sample
        fields = ("sample",)

    def __init__(self, *args, **kwargs):
        collection = kwargs.get("instance")
        super().__init__(*args, **kwargs)

        queryset = Sample.objects.order_by("name")
        if isinstance(collection, Collection) and collection.pk:
            queryset = queryset.exclude(collections=collection)
        self.fields["sample"].queryset = queryset


class CollectionRemoveWasteSampleForm(SimpleModelForm):
    sample = ModelChoiceField(
        queryset=Sample.objects.all(),
        label="Sample",
        help_text="Remove a sample currently linked to this collection.",
    )

    class Meta:
        model = Collection
        fields = ("sample",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sample"].queryset = Sample.objects.filter(
            collections=self.instance
        ).order_by("name")


class CollectionAddPredecessorForm(SimpleModelForm):
    predecessor = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="collection-autocomplete",
            label_field="name",
        ),
        label="Predecessor",
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
    predecessor = ModelChoiceField(queryset=Collection.objects.all())

    class Meta:
        model = Collection
        fields = ("predecessor",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["predecessor"].queryset = Collection.objects.filter(
            successors=self.instance
        )


__all__ = [
    "AggregatedCollectionPropertyValueModelForm",
    "AggregatedCollectionPropertyValueModelFormHelper",
    "cleanup_orphaned_waste_flyers",
    "CollectionAddPredecessorForm",
    "CollectionAddWasteSampleForm",
    "CollectionFrequencyModalModelForm",
    "CollectionFrequencyModelForm",
    "CollectionModelForm",
    "CollectionModelFormHelper",
    "CollectionPropertyValueModelForm",
    "CollectionPropertyValueModelFormHelper",
    "CollectionRemovePredecessorForm",
    "CollectionRemoveWasteSampleForm",
    "CollectionSeasonForm",
    "CollectionSeasonFormHelper",
    "CollectionSeasonFormSet",
    "CollectionSystemModalModelForm",
    "CollectionSystemModelForm",
    "CollectorModalModelForm",
    "CollectorModelForm",
    "CONNECTION_TYPE_CHOICES",
    "FeeSystemModalModelForm",
    "FeeSystemModelForm",
    "REQUIRED_BIN_CAPACITY_REFERENCE_CHOICES",
    "SortingMethodModalModelForm",
    "SortingMethodModelForm",
    "WasteCategoryModalModelForm",
    "WasteCategoryModelForm",
    "WasteComponentModalModelForm",
    "WasteComponentModelForm",
    "WasteFlyerFormSet",
    "WasteFlyerFormSetHelper",
    "WasteFlyerModalModelForm",
    "WasteFlyerModelForm",
]
