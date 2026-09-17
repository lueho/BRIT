from django.db.models import Q
from django_filters import (
    CharFilter,
    ChoiceFilter,
    DateFromToRangeFilter,
    ModelChoiceFilter,
)
from django_filters import rest_framework as rf_filters
from django_filters.widgets import DateRangeWidget
from django_tomselect.app_settings import TomSelectConfig
from django_tomselect.widgets import TomSelectModelWidget

from utils.filters import (
    FreeTextSearchFilterMixin,
    UserCreatedObjectScopedFilterSet,
)

from .models import (
    AnalyticalMethod,
    Composition,
    Material,
    MaterialCategory,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialProperty,
    MaterialPropertyAggregationKind,
    Sample,
    SampleSeries,
    get_or_create_sample_substrate_category,
)


def sampled_substrate_material_q(substrate_category):
    return Q(categories=substrate_category) | Q(samples__isnull=False)


class MaterialFilterSet(rf_filters.FilterSet):
    class Meta:
        model = Material
        fields = {"name": ["iexact", "icontains"], "categories": ["iexact"]}


class MaterialListFilter(FreeTextSearchFilterMixin, UserCreatedObjectScopedFilterSet):
    sortable_fields = {"name": "name"}
    search_fields = ("name", "abbreviation", "description")

    name = ModelChoiceFilter(
        queryset=Material.objects.none(),
        field_name="name",
        label="Material Name",
        empty_label="All",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="material-autocomplete",
                filter_by=("scope", "name"),
            ),
        ),
    )
    category = ModelChoiceFilter(
        queryset=MaterialCategory.objects.all(),
        field_name="categories",
        label="Category",
        empty_label="All",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filters["name"].queryset = self.scoped_choice_queryset(
            Material.objects.all()
        )

    class Meta:
        model = Material
        fields = (
            "q",
            "scope",
            "name",
            "category",
        )


class MaterialCategoryListFilter(UserCreatedObjectScopedFilterSet):
    sortable_fields = {"name": "name"}
    name = CharFilter(
        field_name="name",
        lookup_expr="icontains",
        label="Name",
    )

    class Meta:
        model = MaterialCategory
        fields = ("scope", "name")


class MaterialComponentListFilter(UserCreatedObjectScopedFilterSet):
    sortable_fields = {"name": "name"}
    name = ModelChoiceFilter(
        queryset=MaterialComponent.objects.none(),
        field_name="name",
        label="Component Name",
        empty_label="All",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="materialcomponent-autocomplete",
                filter_by=("scope", "name"),
            ),
        ),
    )
    category = ModelChoiceFilter(
        queryset=MaterialCategory.objects.all(),
        field_name="categories",
        label="Category",
        empty_label="All",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(url="materialcategory-autocomplete")
        ),
    )
    basis_component = ModelChoiceFilter(
        queryset=MaterialComponent.objects.all(),
        field_name="basis_component",
        label="Basis component",
        empty_label="All",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(url="materialcomponent-autocomplete")
        ),
    )
    comparable_component = ModelChoiceFilter(
        queryset=MaterialComponent.objects.all(),
        field_name="comparable_component",
        label="Comparable component",
        empty_label="All",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(url="materialcomponent-autocomplete")
        ),
    )
    component_group = ModelChoiceFilter(
        queryset=MaterialComponentGroup.objects.all(),
        method="filter_component_group",
        label="Component group",
        empty_label="All",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(url="materialcomponentgroup-autocomplete")
        ),
    )

    class Meta:
        model = MaterialComponent
        fields = (
            "scope",
            "name",
            "category",
            "basis_component",
            "comparable_component",
            "component_group",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filters["name"].queryset = self.scoped_choice_queryset(
            MaterialComponent.objects.all()
        )

    def filter_component_group(self, queryset, name, value):
        return queryset.filter(component_measurements__group=value).distinct()


class MaterialComponentGroupListFilter(UserCreatedObjectScopedFilterSet):
    sortable_fields = {"name": "name"}
    name = CharFilter(
        field_name="name",
        lookup_expr="icontains",
        label="Name",
    )
    component = ModelChoiceFilter(
        queryset=MaterialComponent.objects.all(),
        method="filter_component",
        label="Component",
        empty_label="All",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(url="materialcomponent-autocomplete")
        ),
    )

    class Meta:
        model = MaterialComponentGroup
        fields = ("scope", "name", "component")

    def filter_component(self, queryset, name, value):
        return queryset.filter(component_measurements__component=value).distinct()


class MaterialPropertyListFilter(UserCreatedObjectScopedFilterSet):
    sortable_fields = {"name": "name"}
    name = CharFilter(
        field_name="name",
        lookup_expr="icontains",
        label="Name",
    )
    aggregation_kind = ChoiceFilter(
        field_name="aggregation_kind",
        label="Aggregation",
        choices=MaterialPropertyAggregationKind.choices,
        empty_label="All",
    )
    comparable_property = ModelChoiceFilter(
        queryset=MaterialProperty.objects.all(),
        field_name="comparable_property",
        label="Comparable property",
        empty_label="All",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(url="materialproperty-autocomplete")
        ),
    )

    class Meta:
        model = MaterialProperty
        fields = (
            "scope",
            "name",
            "aggregation_kind",
            "comparable_property",
        )


class AnalyticalMethodListFilter(UserCreatedObjectScopedFilterSet):
    sortable_fields = {"name": "name", "technique": "technique"}
    name = CharFilter(
        field_name="name",
        lookup_expr="icontains",
        label="Name",
    )
    technique = CharFilter(
        field_name="technique",
        lookup_expr="icontains",
        label="Technique",
    )

    class Meta:
        model = AnalyticalMethod
        fields = (
            "scope",
            "name",
            "technique",
        )


class CompositionFilterSet(rf_filters.FilterSet):
    class Meta:
        model = Composition
        fields = (
            "group",
            "fractions_of",
        )


class SampleFilter(FreeTextSearchFilterMixin, UserCreatedObjectScopedFilterSet):
    sortable_fields = {"name": "name", "datetime": "datetime"}
    search_fields = ("name", "description", "material__name", "location")

    q = CharFilter(
        method="filter_q",
        label="Search",
        help_text="Search sample names, descriptions, substrate materials, or locations.",
    )

    name = ModelChoiceFilter(
        queryset=Sample.objects.none(),
        field_name="name",
        label="Sample Name",
        help_text="Select a specific sample by name.",
        empty_label="All",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="sample-autocomplete",
                filter_by=("scope", "name"),
            ),
        ),
    )
    substrate_material = ModelChoiceFilter(
        queryset=Material.objects.none(),
        field_name="material",
        label="Substrate material",
        help_text="Show samples made from this substrate material.",
        empty_label="All",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="sample-filter-substrate-material-autocomplete",
                value_field="id",
            )
        ),
    )
    parameter = ModelChoiceFilter(
        queryset=MaterialProperty.objects.none(),
        method="filter_parameter",
        label="Material property",
        help_text="Filter by non-mass characteristics, such as pH or calorific value.",
        empty_label="All",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="materialproperty-autocomplete",
                value_field="id",
            )
        ),
    )
    raw_parameter = ModelChoiceFilter(
        queryset=MaterialComponent.objects.none(),
        method="filter_raw_parameter",
        label="Composition component",
        help_text=(
            "Filter by a component mass fraction used in material-flow analysis, "
            "such as nitrogen."
        ),
        empty_label="All",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="materialcomponent-autocomplete",
                value_field="id",
            )
        ),
    )
    component_group = ModelChoiceFilter(
        queryset=MaterialComponentGroup.objects.none(),
        method="filter_component_group",
        label="Component group",
        help_text=(
            "Show samples with measurements or compositions in this component group."
        ),
        empty_label="All",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="materialcomponentgroup-autocomplete",
                value_field="id",
            )
        ),
    )
    analytical_method = ModelChoiceFilter(
        queryset=AnalyticalMethod.objects.all(),
        method="filter_analytical_method",
        label="Analytical method",
        empty_label="All",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(url="analyticalmethod-autocomplete")
        ),
    )
    series = ModelChoiceFilter(
        queryset=SampleSeries.objects.all(),
        field_name="series",
        label="Sample series",
        empty_label="All",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(url="sampleseries-autocomplete")
        ),
    )
    sample_date = DateFromToRangeFilter(
        field_name="datetime",
        label="Sample date",
        help_text="Show samples taken within this date range.",
        widget=DateRangeWidget(attrs={"type": "date"}),
    )

    def filter_parameter(self, queryset, name, value):
        canonical_property = value.canonical_property
        comparable_ids = MaterialProperty.objects.filter(
            Q(pk=canonical_property.pk) | Q(comparable_property=canonical_property)
        ).values_list("pk", flat=True)
        return queryset.filter(
            property_values__property_id__in=comparable_ids
        ).distinct()

    def filter_raw_parameter(self, queryset, name, value):
        canonical_component = value.canonical_component
        comparable_ids = MaterialComponent.objects.filter(
            Q(pk=canonical_component.pk) | Q(comparable_component=canonical_component)
        ).values_list("pk", flat=True)
        return queryset.filter(
            component_measurements__component_id__in=comparable_ids
        ).distinct()

    def filter_component_group(self, queryset, name, value):
        return queryset.filter(
            Q(component_measurements__group=value) | Q(compositions__group=value)
        ).distinct()

    def filter_analytical_method(self, queryset, name, value):
        return queryset.filter(
            Q(property_values__analytical_method=value)
            | Q(component_measurements__analytical_method=value)
        ).distinct()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        substrate_category, _ = get_or_create_sample_substrate_category()
        self.filters["name"].queryset = self.scoped_choice_queryset(
            Sample.objects.all()
        )
        self.filters["substrate_material"].queryset = Material.objects.filter(
            sampled_substrate_material_q(substrate_category)
        ).distinct()
        self.filters["parameter"].queryset = self.scoped_choice_queryset(
            MaterialProperty.objects.all()
        )
        self.filters["raw_parameter"].queryset = self.scoped_choice_queryset(
            MaterialComponent.objects.all()
        )
        self.filters["component_group"].queryset = self.scoped_choice_queryset(
            MaterialComponentGroup.objects.all()
        )

    class Meta:
        model = Sample
        fields = (
            "q",
            "scope",
            "name",
            "substrate_material",
            "parameter",
            "raw_parameter",
            "component_group",
            "analytical_method",
            "series",
            "sample_date",
        )


class PublishedSampleFilter(SampleFilter):
    name = ModelChoiceFilter(
        queryset=Sample.objects.filter(publication_status="published"),
        field_name="name",
        label="Sample Name",
        empty_label="All",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="sample-autocomplete-public",
            )
        ),
    )


class UserOwnedSampleFilter(SampleFilter):
    name = ModelChoiceFilter(
        queryset=Sample.objects.all(),
        field_name="name",
        label="Sample Name",
        empty_label="All",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="sample-autocomplete-user",
            )
        ),
    )


class SampleSeriesFilter(UserCreatedObjectScopedFilterSet):
    sortable_fields = {"name": "name"}
    material = ModelChoiceFilter(
        queryset=Material.objects.all(),
        field_name="material",
        label="Material",
        empty_label="All",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="material-autocomplete",
            )
        ),
    )

    class Meta:
        model = SampleSeries
        fields = ("scope", "material")


class SampleFilterSet(rf_filters.FilterSet):
    class Meta:
        model = Sample
        fields = (
            "timestep",
            "property_values",
        )


class SampleSeriesFilterSet(rf_filters.FilterSet):
    class Meta:
        model = SampleSeries
        fields = ("material",)
