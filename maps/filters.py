import json

from django.forms import HiddenInput
from django_filters import CharFilter, ModelChoiceFilter, NumberFilter
from django_tomselect.app_settings import TomSelectConfig
from django_tomselect.widgets import TomSelectModelWidget

from utils.filters import BaseCrispyFilterSet

from .models import Catchment, GeoDataset, NutsRegion, Region


class CatchmentFilterSet(BaseCrispyFilterSet):
    id = NumberFilter(widget=HiddenInput())
    name = CharFilter(lookup_expr="icontains")

    class Meta:
        model = Catchment
        fields = (
            "id",
            "name",
            "type",
        )


class RegionFilterSet(BaseCrispyFilterSet):
    name_icontains = CharFilter(
        field_name="name", lookup_expr="icontains", label="Name contains"
    )

    class Meta:
        model = Region
        fields = (
            "id",
            "name",
            "name_icontains",
            "country",
        )


class NutsRegionFilterSet(BaseCrispyFilterSet):
    level_0 = ModelChoiceFilter(
        queryset=NutsRegion.objects.filter(levl_code=0),
        field_name="region_ptr",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="nutsregion-autocomplete-level0",
                value_field="region_ptr",
                label_field="name_latn",
                placeholder="NUTS 0 (country)",
            )
        ),
        label="Level 0",
    )

    level_1 = ModelChoiceFilter(
        queryset=NutsRegion.objects.filter(levl_code=1),
        field_name="region_ptr",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="nutsregion-autocomplete-level1",
                value_field="region_ptr",
                label_field="name_latn",
                filter_by=("level_0", "parent_id"),
                placeholder="NUTS 1 region",
            ),
        ),
        label="Level 1",
    )

    level_2 = ModelChoiceFilter(
        queryset=NutsRegion.objects.filter(levl_code=2),
        field_name="levl_code",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="nutsregion-autocomplete-level2",
                value_field="id",
                label_field="name_latn",
                filter_by=("level_1", "parent_id"),
                placeholder="NUTS 2 region",
            ),
        ),
        label="Level 2",
    )

    level_3 = ModelChoiceFilter(
        queryset=NutsRegion.objects.filter(levl_code=3),
        field_name="levl_code",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="nutsregion-autocomplete-level3",
                value_field="id",
                label_field="name_latn",
                filter_by=("level_2", "parent_id"),
                placeholder="NUTS 3 region",
            ),
        ),
        label="Level 3",
    )

    class Meta:
        model = NutsRegion
        fields = ["level_0", "level_1", "level_2", "level_3"]


class GeoDataSetFilterSet(BaseCrispyFilterSet):
    class Meta:
        model = GeoDataset
        fields = ("id",)
