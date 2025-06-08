from django_tomselect.app_settings import PluginClearButton, TomSelectConfig
from django_tomselect.forms import TomSelectModelChoiceField

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
    catchment = TomSelectModelChoiceField(
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
        label="Catchment",
    )

    class Meta:
        model = Scenario
        fields = ["name", "catchment"]
