from django.forms import HiddenInput
from django_tomselect.app_settings import PluginClearButton
from django_tomselect.forms import TomSelectConfig, TomSelectModelChoiceField

from distributions.models import TemporalDistribution
from maps.models import GeoDataset
from utils.forms import ModalModelFormMixin, SimpleModelForm

from .models import InventoryAlgorithm, Scenario, ScenarioInventoryConfiguration


class SeasonalDistributionModelForm(SimpleModelForm):
    class Meta:
        model = TemporalDistribution
        fields = ()


class ScenarioModelForm(SimpleModelForm):
    region = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="region-autocomplete",
            placeholder="------",
            highlight=True,
            label_field="name",
            open_on_focus=True,
            plugin_clear_button=PluginClearButton(
                title="Clear Selection", class_name="clear-button"
            ),
        ),
        label="Region",
    )
    catchment = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="catchment-autocomplete",
            placeholder="------",
            filter_by=("region", "region_id"),
            highlight=True,
            label_field="name",
            open_on_focus=True,
            plugin_clear_button=PluginClearButton(
                title="Clear Selection", class_name="clear-button"
            ),
        ),
        label="Catchment",
        required=False,
    )

    class Meta:
        model = Scenario
        fields = ["name", "description", "region", "catchment"]


class ScenarioModalModelForm(ModalModelFormMixin, ScenarioModelForm):
    pass


class ScenarioInventoryConfigurationForm(SimpleModelForm):
    class Meta:
        model = ScenarioInventoryConfiguration
        fields = (
            "scenario",
            "feedstock",
            "geodataset",
            "inventory_algorithm",
            "inventory_parameter",
            "inventory_value",
        )


class ScenarioInventoryConfigurationAddForm(ScenarioInventoryConfigurationForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        del self.fields["inventory_parameter"]
        del self.fields["inventory_value"]
        initial = kwargs.get("initial")
        self.fields["scenario"].queryset = Scenario.objects.all()
        self.fields["scenario"].initial = initial.get("scenario")
        self.fields["scenario"].widget = HiddenInput()
        self.fields["feedstock"].queryset = initial.get("feedstocks")
        self.fields["geodataset"].queryset = GeoDataset.objects.none()
        self.fields["inventory_algorithm"].queryset = InventoryAlgorithm.objects.none()


class ScenarioInventoryConfigurationUpdateForm(ScenarioInventoryConfigurationForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        del self.fields["inventory_parameter"]
        del self.fields["inventory_value"]
        initial = kwargs.get("initial")
        scenario = initial.get("scenario")
        feedstock = initial.get("feedstock")
        geodataset = initial.get("geodataset")
        algorithm = initial.get("inventory_algorithm")
        self.fields["scenario"].queryset = Scenario.objects.all()
        self.fields["scenario"].initial = scenario
        self.fields["scenario"].widget = HiddenInput()
        self.fields["feedstock"].queryset = scenario.available_feedstocks()
        self.fields["feedstock"].initial = feedstock
        self.fields["geodataset"].queryset = scenario.available_geodatasets(
            feedstock=feedstock
        )
        self.fields["geodataset"].initial = geodataset
        self.fields["inventory_algorithm"].queryset = (
            scenario.available_inventory_algorithms(
                feedstock=feedstock, geodataset=geodataset
            )
        )
        self.fields["inventory_algorithm"].initial = algorithm
