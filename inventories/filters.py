from django_filters import ModelChoiceFilter
from django_tomselect.app_settings import PluginClearButton, TomSelectConfig
from django_tomselect.forms import TomSelectModelChoiceField
from django_tomselect.widgets import TomSelectModelWidget

from maps.models import Catchment
from utils.filters import BaseCrispyFilterSet

from .models import Scenario


class ScenarioFilterSet(BaseCrispyFilterSet):
    name = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="scenario-name-autocomplete",
            placeholder="------",
            highlight=True,
            label_field="name",
            open_on_focus=True,
            plugin_clear_button=PluginClearButton(
                title="Clear Selection", class_name="clear-button"
            ),
        ),
        label="Scenario Name",
    )
    catchment = ModelChoiceFilter(
        queryset=Catchment.objects.all(),
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="catchment-autocomplete",
                placeholder="------",
                highlight=True,
                label_field="name",
                open_on_focus=True,
                plugin_clear_button=PluginClearButton(
                    title="Clear Selection", class_name="clear-button"
                ),
            ),
        ),
        method="catchment_filter",
    )

    class Meta:
        model = Scenario
        fields = ["name", "catchment"]

        # catchment_filter must always be applied first, because it grabs the initial queryset and does not filter any
        # existing queryset.
        order_by = ["catchment_filter"]

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
