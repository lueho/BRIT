from django.forms import HiddenInput
from django_filters import CharFilter, NumberFilter
from django_tomselect.app_settings import TomSelectConfig
from django_tomselect.forms import TomSelectModelChoiceField

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
    nuts0 = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="nutsregion-autocomplete",
            value_field="id",
            label_field="name",
            placeholder="NUTS 0 (country)",
        ),
        required=True,
    )

    nuts1 = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="nutsregion-autocomplete",
            value_field="id",
            label_field="name",
            filter_by=("nuts0", "parent_id"),
            placeholder="NUTS 1 region",
        ),
        required=False,
    )

    nuts2 = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="nutsregion-autocomplete",
            value_field="id",
            label_field="name",
            filter_by=("nuts1", "parent_id"),
            placeholder="NUTS 2 region",
        ),
        required=False,
    )

    nuts3 = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="nutsregion-autocomplete",
            value_field="id",
            label_field="name",
            filter_by=("nuts2", "parent_id"),
            placeholder="NUTS 3 region",
        ),
        required=False,
    )


class GeoDataSetFilterSet(BaseCrispyFilterSet):
    class Meta:
        model = GeoDataset
        fields = ("id",)
