from django.forms import HiddenInput
from django_filters import CharFilter, ChoiceFilter, ModelChoiceFilter, NumberFilter
from django_tomselect.app_settings import TomSelectConfig
from django_tomselect.widgets import TomSelectModelWidget

from bibliography.models import Source
from utils.filters import BaseCrispyFilterSet, UserCreatedObjectScopedFilterSet
from utils.object_management.permissions import (
    apply_scope_filter,
    filter_queryset_for_user,
)

from .models import (
    GIS_SOURCE_MODELS,
    Attribute,
    Catchment,
    GeoDataset,
    Location,
    NutsRegion,
    Region,
)


class CatchmentFilterSet(UserCreatedObjectScopedFilterSet):
    id = NumberFilter(widget=HiddenInput())
    name = CharFilter(lookup_expr="icontains")

    class Meta:
        model = Catchment
        fields = (
            "scope",
            "id",
            "name",
            "type",
        )


class RegionFilterSet(UserCreatedObjectScopedFilterSet):
    name_icontains = CharFilter(
        field_name="name", lookup_expr="icontains", label="Name contains"
    )
    composed_of = NumberFilter(
        field_name="composing_regions__id",
        label="Composed of region id",
    )

    class Meta:
        model = Region
        fields = (
            "scope",
            "id",
            "name",
            "name_icontains",
            "type",
            "country",
            "composed_of",
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


class GeoDataSetFilterSet(UserCreatedObjectScopedFilterSet):
    name = CharFilter(lookup_expr="icontains", label="Name contains")
    model_name = ChoiceFilter(choices=GIS_SOURCE_MODELS, label="Dataset type")
    region = ModelChoiceFilter(
        queryset=Region.objects.none(),
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="region-autocomplete",
                label_field="name",
                filter_by=("scope", "name"),
            )
        ),
        label="Region",
    )
    source = ModelChoiceFilter(
        queryset=Source.objects.none(),
        field_name="sources",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="source-autocomplete",
                label_field="text",
                filter_by=("scope", "name"),
            )
        ),
        label="Source",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = getattr(self, "request", None)

        region_queryset = Region.objects.all()
        source_queryset = Source.objects.all()
        if request and hasattr(request, "user"):
            region_queryset = filter_queryset_for_user(region_queryset, request.user)
            source_queryset = filter_queryset_for_user(source_queryset, request.user)

        scope_value = None
        try:
            if hasattr(self, "data") and self.data:
                scope_value = self.data.get("scope")
            if not scope_value and hasattr(self, "form"):
                scope_value = self.form.initial.get("scope")
        except Exception:
            scope_value = None

        if scope_value:
            region_queryset = apply_scope_filter(
                region_queryset, scope_value, user=getattr(request, "user", None)
            )
            source_queryset = apply_scope_filter(
                source_queryset, scope_value, user=getattr(request, "user", None)
            )

        self.filters["region"].queryset = region_queryset
        self.filters["source"].queryset = source_queryset

    class Meta:
        model = GeoDataset
        fields = ("scope", "name", "model_name", "region", "source")


class LocationListFilter(UserCreatedObjectScopedFilterSet):
    name = ModelChoiceFilter(
        queryset=Location.objects.none(),
        field_name="name",
        label="Location Name",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="location-autocomplete",
                filter_by=("scope", "name"),
            ),
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = getattr(self, "request", None)
        queryset = Location.objects.all()
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
        model = Location
        fields = ("scope", "name")


class AttributeListFilter(UserCreatedObjectScopedFilterSet):
    name = ModelChoiceFilter(
        queryset=Attribute.objects.none(),
        field_name="name",
        label="Attribute Name",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="attribute-autocomplete",
                filter_by=("scope", "name"),
            ),
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = getattr(self, "request", None)
        queryset = Attribute.objects.all()
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
        model = Attribute
        fields = ("scope", "name")
