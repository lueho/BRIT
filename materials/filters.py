from django_filters import (
    BooleanFilter,
    CharFilter,
    ChoiceFilter,
    DateFromToRangeFilter,
    ModelChoiceFilter,
)
from django_filters import rest_framework as rf_filters
from django_tomselect.app_settings import TomSelectConfig
from django_tomselect.widgets import TomSelectModelWidget

from utils.filters import UserCreatedObjectScopedFilterSet
from utils.object_management.permissions import (
    apply_scope_filter,
    filter_queryset_for_user,
)

from .models import (
    AnalyticalMethod,
    Composition,
    Material,
    MaterialCategory,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialComponentKind,
    MaterialProperty,
    MaterialPropertyAggregationKind,
    Sample,
    SampleSeries,
)


class MaterialFilterSet(rf_filters.FilterSet):
    class Meta:
        model = Material
        fields = {"name": ["iexact", "icontains"], "categories": ["iexact"]}


class MaterialListFilter(UserCreatedObjectScopedFilterSet):
    name = ModelChoiceFilter(
        queryset=Material.objects.none(),
        field_name="name",
        label="Material Name",
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
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="materialcategory-autocomplete",
            ),
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = getattr(self, "request", None)
        queryset = Material.objects.filter(type="material")
        if request and hasattr(request, "user"):
            queryset = filter_queryset_for_user(queryset, request.user)

        scope_value = None
        try:
            if hasattr(self, "data") and self.data:
                scope_value = self.data.get("scope")
            if not scope_value and hasattr(self, "form"):
                scope_value = self.form.initial.get("scope")
        except Exception:
            scope_value = None

        if scope_value:
            queryset = apply_scope_filter(
                queryset, scope_value, user=getattr(request, "user", None)
            )

        self.filters["name"].queryset = queryset

    class Meta:
        model = Material
        fields = (
            "scope",
            "name",
            "category",
        )


class MaterialCategoryListFilter(UserCreatedObjectScopedFilterSet):
    name = ModelChoiceFilter(
        queryset=MaterialCategory.objects.none(),
        field_name="name",
        label="Category Name",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="materialcategory-autocomplete",
                filter_by=("scope", "name"),
            ),
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = getattr(self, "request", None)
        queryset = MaterialCategory.objects.all()
        if request and hasattr(request, "user"):
            queryset = filter_queryset_for_user(queryset, request.user)

        scope_value = None
        try:
            if hasattr(self, "data") and self.data:
                scope_value = self.data.get("scope")
            if not scope_value and hasattr(self, "form"):
                scope_value = self.form.initial.get("scope")
        except Exception:
            scope_value = None

        if scope_value:
            queryset = apply_scope_filter(
                queryset, scope_value, user=getattr(request, "user", None)
            )

        self.filters["name"].queryset = queryset

    class Meta:
        model = MaterialCategory
        fields = ("scope", "name")


class MaterialComponentListFilter(UserCreatedObjectScopedFilterSet):
    name = ModelChoiceFilter(
        queryset=MaterialComponent.objects.none(),
        field_name="name",
        label="Component Name",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="materialcomponent-autocomplete",
                filter_by=("scope", "name"),
            ),
        ),
    )
    component_kind = ChoiceFilter(
        field_name="component_kind",
        label="Kind",
        choices=MaterialComponentKind.choices,
        empty_label="All",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = getattr(self, "request", None)
        queryset = MaterialComponent.objects.all()
        if request and hasattr(request, "user"):
            queryset = filter_queryset_for_user(queryset, request.user)

        scope_value = None
        try:
            if hasattr(self, "data") and self.data:
                scope_value = self.data.get("scope")
            if not scope_value and hasattr(self, "form"):
                scope_value = self.form.initial.get("scope")
        except Exception:
            scope_value = None

        if scope_value:
            queryset = apply_scope_filter(
                queryset, scope_value, user=getattr(request, "user", None)
            )

        self.filters["name"].queryset = queryset

    class Meta:
        model = MaterialComponent
        fields = (
            "scope",
            "name",
            "component_kind",
        )


class MaterialComponentGroupListFilter(UserCreatedObjectScopedFilterSet):
    name = ModelChoiceFilter(
        queryset=MaterialComponentGroup.objects.none(),
        field_name="name",
        label="Group Name",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="materialcomponentgroup-autocomplete",
                filter_by=("scope", "name"),
            ),
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = getattr(self, "request", None)
        queryset = MaterialComponentGroup.objects.all()
        if request and hasattr(request, "user"):
            queryset = filter_queryset_for_user(queryset, request.user)

        scope_value = None
        try:
            if hasattr(self, "data") and self.data:
                scope_value = self.data.get("scope")
            if not scope_value and hasattr(self, "form"):
                scope_value = self.form.initial.get("scope")
        except Exception:
            scope_value = None

        if scope_value:
            queryset = apply_scope_filter(
                queryset, scope_value, user=getattr(request, "user", None)
            )

        self.filters["name"].queryset = queryset

    class Meta:
        model = MaterialComponentGroup
        fields = ("scope", "name")


class MaterialPropertyListFilter(UserCreatedObjectScopedFilterSet):
    name = ModelChoiceFilter(
        queryset=MaterialProperty.objects.none(),
        field_name="name",
        label="Property Name",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="materialproperty-autocomplete",
                filter_by=("scope", "name"),
            ),
        ),
    )
    aggregation_kind = ChoiceFilter(
        field_name="aggregation_kind",
        label="Aggregation",
        choices=MaterialPropertyAggregationKind.choices,
        empty_label="All",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = getattr(self, "request", None)
        queryset = MaterialProperty.objects.all()
        if request and hasattr(request, "user"):
            queryset = filter_queryset_for_user(queryset, request.user)

        scope_value = None
        try:
            if hasattr(self, "data") and self.data:
                scope_value = self.data.get("scope")
            if not scope_value and hasattr(self, "form"):
                scope_value = self.form.initial.get("scope")
        except Exception:
            scope_value = None

        if scope_value:
            queryset = apply_scope_filter(
                queryset, scope_value, user=getattr(request, "user", None)
            )

        self.filters["name"].queryset = queryset

    class Meta:
        model = MaterialProperty
        fields = (
            "scope",
            "name",
            "aggregation_kind",
        )


class AnalyticalMethodListFilter(UserCreatedObjectScopedFilterSet):
    name = ModelChoiceFilter(
        queryset=AnalyticalMethod.objects.none(),
        field_name="name",
        label="Method Name",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="analyticalmethod-autocomplete",
                filter_by=("scope", "name"),
            ),
        ),
    )
    technique = CharFilter(
        field_name="technique",
        lookup_expr="icontains",
        label="Technique",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = getattr(self, "request", None)
        queryset = AnalyticalMethod.objects.all()
        if request and hasattr(request, "user"):
            queryset = filter_queryset_for_user(queryset, request.user)

        scope_value = None
        try:
            if hasattr(self, "data") and self.data:
                scope_value = self.data.get("scope")
            if not scope_value and hasattr(self, "form"):
                scope_value = self.form.initial.get("scope")
        except Exception:
            scope_value = None

        if scope_value:
            queryset = apply_scope_filter(
                queryset, scope_value, user=getattr(request, "user", None)
            )

        self.filters["name"].queryset = queryset

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


class SampleFilter(UserCreatedObjectScopedFilterSet):
    name = ModelChoiceFilter(
        queryset=Sample.objects.none(),
        field_name="name",
        label="Sample Name",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="sample-autocomplete",
                filter_by=("scope", "name"),
            ),
        ),
    )
    material = ModelChoiceFilter(
        queryset=Material.objects.filter(type="material"),
        field_name="material__name",
        label="Material",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="material-autocomplete",
            )
        ),
    )
    standalone = BooleanFilter(field_name="standalone", label="Standalone")
    created_at = DateFromToRangeFilter(field_name="created_at", label="Created")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = getattr(self, "request", None)
        queryset = Sample.objects.all()
        if request and hasattr(request, "user"):
            queryset = filter_queryset_for_user(queryset, request.user)

        scope_value = None
        try:
            if hasattr(self, "data") and self.data:
                scope_value = self.data.get("scope")
            if not scope_value and hasattr(self, "form"):
                scope_value = self.form.initial.get("scope")
        except Exception:
            scope_value = None

        if scope_value:
            queryset = apply_scope_filter(
                queryset, scope_value, user=getattr(request, "user", None)
            )

        self.filters["name"].queryset = queryset

    class Meta:
        model = Sample
        fields = (
            "scope",
            "name",
            "material",
            "standalone",
            "created_at",
        )


class PublishedSampleFilter(SampleFilter):
    name = ModelChoiceFilter(
        queryset=Sample.objects.filter(publication_status="published"),
        field_name="name",
        label="Sample Name",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="sample-autocomplete-published",
            )
        ),
    )


class UserOwnedSampleFilter(SampleFilter):
    name = ModelChoiceFilter(
        queryset=Sample.objects.all(),
        field_name="name",
        label="Sample Name",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="sample-autocomplete-owned",
            )
        ),
    )


class SampleSeriesFilter(UserCreatedObjectScopedFilterSet):
    material = ModelChoiceFilter(
        queryset=Material.objects.filter(type="material"),
        field_name="material__name",
        label="Material",
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
            "properties",
        )


class SampleSeriesFilterSet(rf_filters.FilterSet):
    class Meta:
        model = SampleSeries
        fields = ("material",)
