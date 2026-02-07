from django_filters import BooleanFilter, DateFromToRangeFilter, ModelChoiceFilter
from django_filters import rest_framework as rf_filters
from django_tomselect.app_settings import TomSelectConfig
from django_tomselect.widgets import TomSelectModelWidget

from utils.filters import BaseCrispyFilterSet, UserCreatedObjectScopedFilterSet
from utils.object_management.permissions import (
    apply_scope_filter,
    filter_queryset_for_user,
)

from .models import Composition, Material, MaterialCategory, Sample, SampleSeries


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


class SampleSeriesFilter(BaseCrispyFilterSet):
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
        fields = ("material",)


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
