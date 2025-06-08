from django.forms import HiddenInput
from django_filters import ChoiceFilter, ModelChoiceFilter
from django_filters import rest_framework as rf_filters
from django_tomselect.app_settings import TomSelectConfig
from django_tomselect.widgets import TomSelectModelWidget

from utils.filters import BaseCrispyFilterSet

from .models import Composition, Material, Sample, SampleSeries


class MaterialFilterSet(rf_filters.FilterSet):
    class Meta:
        model = Material
        fields = {"name": ["iexact", "icontains"], "categories": ["iexact"]}


class CompositionFilterSet(rf_filters.FilterSet):
    class Meta:
        model = Composition
        fields = (
            "group",
            "fractions_of",
        )


class SampleFilter(BaseCrispyFilterSet):
    scope = ChoiceFilter(
        choices=(("published", "Published"), ("private", "Private")),
        widget=HiddenInput(),
        method="filter_scope",
        label="",
    )
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

    class Meta:
        model = Sample
        fields = (
            "scope",
            "name",
            "material",
        )

    def filter_scope(self, queryset, name, value):
        """Filter queryset by published vs private depending on scope param."""
        if value == "private":
            if not self.request.user.is_authenticated:
                return queryset.none()
            return queryset.filter(owner=self.request.user)
        return queryset.filter(publication_status="published")


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
