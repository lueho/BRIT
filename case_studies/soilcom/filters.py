import math

from crispy_forms.bootstrap import Accordion
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Field, Layout, Row
from django.db.models import Avg, Count, Max, Q, Sum
from django.forms import CheckboxSelectMultiple, DateInput, HiddenInput, RadioSelect
from django_filters import (
    BooleanFilter,
    CharFilter,
    ChoiceFilter,
    DateFilter,
    ModelChoiceFilter,
    ModelMultipleChoiceFilter,
    OrderingFilter,
)
from django_tomselect.app_settings import TomSelectConfig
from django_tomselect.widgets import TomSelectModelWidget

from utils.crispy_fields import FilterAccordionGroup, RangeSliderField
from utils.filters import (
    BaseCrispyFilterSet,
    NullableRangeFilter,
    UserCreatedObjectScopedFilterSet,
)
from utils.widgets import NullableRangeSliderWidget

from .models import (
    CONNECTION_TYPE_CHOICES,
    REQUIRED_BIN_CAPACITY_REFERENCE_CHOICES,
    Collection,
    CollectionCatchment,
    CollectionCountOptions,
    CollectionFrequency,
    CollectionPropertyValue,
    Collector,
    FeeSystem,
    WasteCategory,
    WasteComponent,
    WasteFlyer,
)


class CollectorFilter(UserCreatedObjectScopedFilterSet):
    name = CharFilter(lookup_expr="icontains")
    catchment = CharFilter(
        lookup_expr="name__icontains", label="Catchment name contains"
    )

    class Meta:
        model = Collector
        fields = ("scope", "name", "catchment")


class CollectionCatchmentFilterSet(BaseCrispyFilterSet):
    name = CharFilter(lookup_expr="icontains")

    class Meta:
        model = CollectionCatchment
        fields = (
            "id",
            "name",
            "type",
        )


SEASONAL_FREQUENCY_CHOICES = (
    ("", "All"),
    (True, "Seasonal"),
    (False, "Not seasonal"),
)
OPTIONAL_FREQUENCY_CHOICES = (
    ("", "All"),
    (True, "Options"),
    (False, "No options"),
)


class CollectionFilterFormHelper(FormHelper):
    layout = Layout(
        Accordion(
            FilterAccordionGroup(
                "Filters",
                "catchment",
                "collector",
                "collection_system",
                "waste_category",
                "publication_status",
                "ordering",
            ),
            FilterAccordionGroup(
                "Advanced filters",
                "connection_type",
                "allowed_materials",
                "forbidden_materials",
                RangeSliderField("connection_rate"),
                Row(
                    Column(Field("seasonal_frequency"), css_class="col-md"),
                    Column(Field("optional_frequency"), css_class="col-md"),
                ),
                "fee_system",
                RangeSliderField("min_bin_size"),
                RangeSliderField("required_bin_capacity"),
                Field("required_bin_capacity_reference"),
                RangeSliderField("collections_per_year"),
                RangeSliderField("spec_waste_collected"),
                "valid_on",
                "scope",
            ),
        )
    )


class CollectionsPerYearFilter(NullableRangeFilter):
    def set_min_max(self):
        frequencies = CollectionFrequency.objects.annotate(
            collection_count=Sum("collectioncountoptions__standard")
        )
        if frequencies.exists():
            max_value = frequencies.aggregate(Max("collection_count"))[
                "collection_count__max"
            ]
        else:
            max_value = 1000
        self.extra["widget"] = NullableRangeSliderWidget(
            attrs={
                "data-range_min": 0,
                "data-range_max": max_value,
                "data-step": 1,
                "data-is_null": self.default_include_null,
                "data-unit": "",
            }
        )

    def apply_range(self, qs, value_slice: slice, include_nulls: bool):
        """Filter collections whose related frequency has *collection_count* in range."""
        freqs = CollectionFrequency.objects.annotate(
            collection_count=Sum("collectioncountoptions__standard")
        ).filter(
            collection_count__gte=value_slice.start,
            collection_count__lte=value_slice.stop,
        )
        filtered = qs.filter(frequency__in=freqs)
        if include_nulls:
            filtered = filtered | qs.filter(frequency__isnull=True)
        return filtered


class NullableCollectionPropertyValueRangeFilter(NullableRangeFilter):
    """Filter for CollectionPropertyValue model. It is used to filter by average value of property."""

    property_name = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.property_name = kwargs.get("property_name", self.property_name)

    def set_min_max(self):
        values = CollectionPropertyValue.objects.filter(
            property__name=self.property_name
        )
        if self.range_min is None:
            self.range_min = self.default_range_min
        if self.range_max is None:
            if values.exists():
                self.range_max = math.ceil(
                    values.aggregate(Max("average"))["average__max"]
                )
            else:
                self.range_max = self.default_range_max
        if self.range_step is None:
            self.range_step = self.default_range_step
        self.extra["widget"] = NullableRangeSliderWidget(
            attrs={
                "data-range_min": self.range_min,
                "data-range_max": self.range_max,
                "data-step": self.range_step,
                "data-is_null": self.default_include_null,
                "data-unit": self.unit,
            }
        )

    def apply_range(self, qs, value_slice: slice, include_nulls: bool):
        """Annotate average property value and apply range/null filtering."""
        qs = qs.annotate(
            **{
                "avg_value": Avg(
                    "collectionpropertyvalue__average",
                    filter=Q(
                        collectionpropertyvalue__property__name=self.property_name,
                        collectionpropertyvalue__average__gt=0.0,
                    ),
                )
            }
        )

        filtered = qs.filter(
            **{
                "avg_value__gte": value_slice.start,
                "avg_value__lte": value_slice.stop,
            }
        )
        if include_nulls:
            filtered = filtered | qs.filter(**{"avg_value__isnull": True})
        return filtered


class ConnectionRateFilter(NullableCollectionPropertyValueRangeFilter):
    property_name = "Connection rate"
    unit = "%"


class SpecWasteCollectedFilter(NullableCollectionPropertyValueRangeFilter):
    property_name = "specific waste collected"
    default_range_max = 1000


class RequiredBinCapacityRangeFilter(NullableRangeFilter):
    """
    Range filter for minimum bin capacity per unit (L).
    """

    default_range_min = 0
    default_range_max = 1000
    default_range_step = 1
    default_include_null = True
    unit = "L"

    def set_min_max(self):
        min_val = self.default_range_min
        values = Collection.objects.exclude(required_bin_capacity__isnull=True)
        if values.exists():
            max_val = values.aggregate(Max("required_bin_capacity"))[
                "required_bin_capacity__max"
            ]
            self.default_range_max = max_val
        else:
            max_val = self.default_range_max
        self.extra["widget"] = NullableRangeSliderWidget(
            attrs={
                "data-range_min": min_val,
                "data-range_max": max_val,
                "data-step": self.default_range_step,
                "data-is_null": self.default_include_null,
                "data-unit": self.unit,
            }
        )


class MinBinSizeRangeFilter(NullableRangeFilter):
    default_range_min = 0
    default_range_max = 2000
    default_range_step = 1
    default_include_null = True
    unit = "L"

    def set_min_max(self):
        min_val = self.default_range_min

        values = Collection.objects.exclude(min_bin_size__isnull=True)
        if values.exists():
            max_val = values.aggregate(Max("min_bin_size"))["min_bin_size__max"]
        else:
            max_val = self.default_range_max
        self.extra["widget"] = NullableRangeSliderWidget(
            attrs={
                "data-range_min": min_val,
                "data-range_max": max_val,
                "data-step": self.default_range_step,
                "data-is_null": self.default_include_null,
                "data-unit": self.unit,
            }
        )


class CollectionFilterSet(UserCreatedObjectScopedFilterSet):
    id = ModelMultipleChoiceFilter(
        queryset=Collection.objects.all(), to_field_name="id"
    )
    catchment = ModelChoiceFilter(
        queryset=CollectionCatchment.objects.all(),
        widget=TomSelectModelWidget(
            config=TomSelectConfig(url="catchment-autocomplete")
        ),
        method="catchment_filter",
    )
    collector = ModelChoiceFilter(
        queryset=Collector.objects.all(),
        widget=TomSelectModelWidget(
            config=TomSelectConfig(url="collector-autocomplete")
        ),
    )
    waste_category = ModelMultipleChoiceFilter(
        queryset=WasteCategory.objects.all(),
        field_name="waste_stream__category",
        label="Waste categories",
        widget=CheckboxSelectMultiple,
    )
    allowed_materials = ModelMultipleChoiceFilter(
        queryset=WasteComponent.objects.all(),
        field_name="waste_stream__allowed_materials",
        label="Allowed materials",
        widget=CheckboxSelectMultiple,
    )
    forbidden_materials = ModelMultipleChoiceFilter(
        queryset=WasteComponent.objects.all(),
        field_name="waste_stream__forbidden_materials",
        label="Forbidden materials",
        widget=CheckboxSelectMultiple,
    )
    connection_rate = ConnectionRateFilter(label="Connection rate")
    seasonal_frequency = BooleanFilter(
        widget=RadioSelect(choices=SEASONAL_FREQUENCY_CHOICES),
        label="Seasonal frequency",
        method="get_seasonal_frequency",
    )
    optional_frequency = BooleanFilter(
        widget=RadioSelect(choices=OPTIONAL_FREQUENCY_CHOICES),
        label="Optional frequency",
        method="get_optional_frequency",
    )
    collections_per_year = CollectionsPerYearFilter(label="Collections per year")
    spec_waste_collected = SpecWasteCollectedFilter(
        label="Specific waste collected [kg/(cap.*a)]",
    )
    fee_system = ModelChoiceFilter(
        queryset=FeeSystem.objects.all(),
    )
    valid_on = DateFilter(
        method="filter_valid_on",
        widget=DateInput(attrs={"type": "date"}),
        label="Valid on",
    )
    connection_type = ChoiceFilter(
        choices=CONNECTION_TYPE_CHOICES,
        label="Connection type",
    )
    min_bin_size = MinBinSizeRangeFilter(
        label="Smallest available bin size (L)",
    )
    required_bin_capacity = RequiredBinCapacityRangeFilter(
        label="Required bin capacity per unit (L)",
        help_text="Minimum total bin capacity that must be supplied per reference unit (see below).",
    )
    required_bin_capacity_reference = ChoiceFilter(
        choices=REQUIRED_BIN_CAPACITY_REFERENCE_CHOICES,
        label="Reference unit for required bin capacity",
        field_name="required_bin_capacity_reference",
        help_text="Defines the unit (person, household, property) for which the required bin capacity applies. Leave blank if not specified.",
    )
    ordering = OrderingFilter(
        label="Sort by",
        choices=(
            ("-lastmodified_at", "Last changed (newest)"),
            ("lastmodified_at", "Last changed (oldest)"),
            ("name", "Name (A–Z)"),
            ("-name", "Name (Z–A)"),
        ),
    )

    class Meta:
        model = Collection
        fields = (
            "id",
            "catchment",
            "collector",
            "collection_system",
            "waste_category",
            "connection_type",
            "allowed_materials",
            "forbidden_materials",
            "connection_rate",
            "seasonal_frequency",
            "optional_frequency",
            "min_bin_size",
            "required_bin_capacity",
            "required_bin_capacity_reference",
            "collections_per_year",
            "spec_waste_collected",
            "fee_system",
            "valid_on",
            "publication_status",
            "owner",
            "scope",
            "ordering",
        )
        # catchment_filter must always be applied first, because it grabs the initial queryset and does not filter any
        # existing queryset.
        order_by = ["catchment_filter"]
        form_helper = CollectionFilterFormHelper

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filters["connection_rate"].set_min_max()
        self.filters["collections_per_year"].set_min_max()
        self.filters["spec_waste_collected"].set_min_max()
        self.filters["required_bin_capacity"].set_min_max()
        self.filters["min_bin_size"].set_min_max()

        # Only show publication_status filter when scope is private ("My collections")
        try:
            scope_val = None
            # django_filters passes data in .data (QueryDict)
            if hasattr(self, "data") and self.data:
                scope_val = self.data.get("scope")
            # Fallback to initial on form if provided by view defaults
            if not scope_val and hasattr(self.form, "initial"):
                scope_val = self.form.initial.get("scope")
        except Exception:
            scope_val = None

        if scope_val != "private":
            # Hide the field visually; it will still be in the form to carry defaults if any
            try:
                self.filters["publication_status"].field.widget = HiddenInput()
                self.filters["publication_status"].field.label = ""
                self.filters["publication_status"].extra["help_text"] = ""
            except KeyError:
                pass

    @staticmethod
    def catchment_filter(queryset, _, value):
        if value.type == "custom":
            spatially_related_qs = value.inside_collections.order_by("name")
        else:
            spatially_related_qs = value.downstream_collections.order_by("name")
            if not spatially_related_qs.exists():
                spatially_related_qs = value.upstream_collections.order_by("name")

        collection_ids = list(spatially_related_qs.values_list("id", flat=True))

        return queryset.filter(id__in=collection_ids)

    @staticmethod
    def get_seasonal_frequency(queryset, _, value):
        if value is None:
            return queryset
        if "season_count" not in queryset.query.annotations:
            queryset = queryset.annotate(season_count=Count("frequency__seasons"))
        if value is True:
            return queryset.filter(season_count__gt=1)
        elif value is False:
            return queryset.filter(season_count__lte=1)

    @staticmethod
    def get_optional_frequency(queryset, _, value):
        if value is None:
            return queryset
        if value is True:
            opts = CollectionCountOptions.objects.filter(
                Q(option_1__isnull=False)
                | Q(option_2__isnull=False)
                | Q(option_3__isnull=False)
            )
            return queryset.filter(frequency__in=opts.values_list("frequency"))
        elif value is False:
            opts = CollectionCountOptions.objects.filter(
                Q(option_1__isnull=True)
                & Q(option_2__isnull=True)
                & Q(option_3__isnull=True)
            )
            return queryset.filter(frequency__in=opts.values_list("frequency"))

    @staticmethod
    def filter_valid_on(qs, _, value):
        return qs.filter(
            Q(valid_from__lte=value), Q(valid_until__gte=value) | Q(valid_until=None)
        )


class WasteFlyerFilter(UserCreatedObjectScopedFilterSet):
    url_valid = BooleanFilter(
        widget=RadioSelect(choices=((True, "True"), (False, "False")))
    )
    url_checked_before = DateFilter(
        field_name="url_checked",
        lookup_expr="lt",
        widget=DateInput(attrs={"type": "date"}),
        label="Url checked before",
    )
    url_checked_after = DateFilter(
        field_name="url_checked",
        lookup_expr="gt",
        widget=DateInput(attrs={"type": "date"}),
        label="Url checked after",
    )
    catchment = ModelChoiceFilter(
        queryset=CollectionCatchment.objects.all(),
        label="Catchment",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(url="catchment-autocomplete")
        ),
        method="get_catchment",
    )

    class Meta:
        model = WasteFlyer
        fields = (
            "scope",
            "url_valid",
            "url_checked_before",
            "url_checked_after",
            "catchment",
        )

    @staticmethod
    def get_catchment(qs, _, value):
        return qs.filter(collections__in=value.downstream_collections).distinct()
