from datetime import timedelta

from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Column, Div, Field, Layout, Row
from django.core.exceptions import ValidationError
from django.db.models import Case, Value, When
from django.db.models import IntegerField as DBIntegerField
from django.forms import (
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
from utils.crispy_fields import ForeignkeyField
from utils.forms import (
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

from .models import (
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
    WasteStream,
)
from .tasks import cleanup_orphaned_waste_flyers


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


class CollectorModalModelForm(ModalModelFormMixin, CollectorModelForm):
    pass


class CollectionSystemModelForm(SimpleModelForm):
    class Meta:
        model = CollectionSystem
        fields = ("name", "description")


class CollectionSystemModalModelForm(ModalModelFormMixin, CollectionSystemModelForm):
    pass


class SortingMethodModelForm(SimpleModelForm):
    class Meta:
        model = SortingMethod
        fields = ("name", "description")


class SortingMethodModalModelForm(ModalModelFormMixin, SortingMethodModelForm):
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
                instance, _ = WasteFlyer.objects.get_or_create(
                    url=self.cleaned_data["url"], defaults=defaults
                )
                return instance
        else:
            return super().save(commit=False)


class WasteFlyerModalModelForm(ModalModelFormMixin, WasteFlyerModelForm):
    pass


class WasteFlyerFormSetHelper(DynamicTableInlineFormSetHelper):
    """
    Custom formset helper for waste flyer URLs with clear labeling.
    Distinguishes waste management document URLs from bibliographic references.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add a descriptive legend/title for the formset
        self.legend = (
            '<i class="fas fa-link me-1"></i> Waste Management Documents (URLs)'
        )
        self.help_text = "Quick links to waste management flyers, collection schedules, or municipal documents. URLs are automatically saved as references."
        self.form_show_labels = True  # Show URL label for each field


class WasteFlyerFormSet(M2MInlineFormSet):
    """
    Formset for managing WasteFlyer URLs.

    Handles proper cleanup by only deleting orphaned WasteFlyers that are not
    connected to any Collection (via flyers or sources) or PropertyValue (via sources).
    """

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
        # References section (widget renders its own card header with label)
        Div(
            Field("sources", template="bootstrap5/field_no_label.html"),
            css_class="mt-4",
        ),
    )


class CollectionPropertyValueModelForm(
    UserCreatedObjectFormMixin, SourcesFieldMixin, SimpleModelForm
):
    collection = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="collection-autocomplete",
            label_field="name",
        ),
        label="Collection",
    )
    # sources field and widget provided by SourcesFieldMixin

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
        # References section (widget renders its own card header with label)
        Div(
            Field("sources", template="bootstrap5/field_no_label.html"),
            css_class="mt-4",
        ),
    )


class AggregatedCollectionPropertyValueModelForm(
    UserCreatedObjectFormMixin, SourcesFieldMixin, SimpleModelForm
):
    collections = TomSelectModelMultipleChoiceField(
        config=TomSelectConfig(
            url="collection-autocomplete",
            label_field="name",
        ),
        label="Collections",
    )
    # sources field and widget provided by SourcesFieldMixin

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
    layout = Layout(
        # Collection identification and location
        Field("catchment"),
        ForeignkeyField("collector"),
        ForeignkeyField("collection_system"),
        Field("sorting_method"),
        # Waste stream configuration
        ForeignkeyField("waste_category"),
        Field("connection_type"),
        Field("allowed_materials"),
        Field("forbidden_materials"),
        # Collection parameters
        ForeignkeyField("fee_system"),
        Field("frequency"),
        Field("min_bin_size"),
        Field("required_bin_capacity"),
        Field("required_bin_capacity_reference"),
        # Validity period
        Field("established"),
        Field("valid_from"),
        Field("valid_until"),
        # Additional information
        Field("description"),
        # References section (widget renders its own card header with label)
        Div(
            Field("sources", template="bootstrap5/field_no_label.html"),
            css_class="mt-4",
        ),
    )


class CollectionModelForm(
    UserCreatedObjectFormMixin, SourcesFieldMixin, CreateInlineMixin, SimpleModelForm
):
    """
    Model form for Collection, including all collection parameters and waste stream fields.
    """

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

    @classmethod
    def _ordered_waste_component_qs(cls):
        """Return WasteComponents with explicit display order; unknown materials sort last by name."""
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
    # sources field provided by SourcesFieldMixin
    # Widget has its own header, so label won't be shown
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
        widget=NumberInput(attrs={"step": "0.1", "min": "0"}),
    )
    required_bin_capacity_reference = ChoiceField(
        choices=[("", "---------")] + REQUIRED_BIN_CAPACITY_REFERENCE_CHOICES,
        required=False,
        label="Reference unit for minimum required specific bin capacity",
        help_text="Defines the unit (person, household, property) for which the required bin capacity applies. Leave blank if not specified.",
    )

    # __init__ logic for sources field is provided by SourcesFieldMixin

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
            "sources",
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
            f"{data['catchment']} {data['waste_category']} {data['collection_system']}"
        )
        allowed_materials = data["allowed_materials"]
        forbidden_materials = data["forbidden_materials"]
        if (
            self.predecessor
            and self.predecessor.waste_stream_id
            and not {
                "waste_category",
                "allowed_materials",
                "forbidden_materials",
            }.intersection(self.changed_data)
        ):
            instance.waste_stream = self.predecessor.waste_stream
        else:
            waste_stream, created = WasteStream.objects.get_or_create(
                defaults={"owner": instance.owner},
                category=data["waste_category"],
                allowed_materials=allowed_materials,
                forbidden_materials=forbidden_materials,
            )
            instance.waste_stream = waste_stream
        if commit:
            instance.save()
            for predecessor in instance.predecessors.all():
                valid_until = instance.valid_from - timedelta(days=1)
                predecessor.valid_until = valid_until
                predecessor.save(update_fields=["valid_until", "lastmodified_at"])
            self.save_m2m()
            return instance
        else:
            return super().save(commit=False)


class CollectionAddWasteSampleForm(SimpleModelForm):
    sample = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="sample-autocomplete",
            label_field="name",
        ),
        label="Sample",
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


class CollectionAddPredecessorForm(SimpleModelForm):
    """
    This form is used to add a predecessor to a Collection instance. A predecessor is a Collection instance that
    was replaced by the current Collection instance.

    Fields:
    predecessor: A ModelChoiceField that represents the predecessor to be added.
                 The queryset for this field is all Collection instances.
    """

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
