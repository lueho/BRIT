from django.forms import HiddenInput
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
            label_field="name",
        ),
        label="Region",
    )
    catchment = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="catchment-autocomplete",
            filter_by=("region", "region_id"),
            label_field="name",
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
    feedstock = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="sampleseries-autocomplete",
            label_field="name",
        ),
        label="Feedstock",
    )
    geodataset = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="scenario-geodataset-autocomplete",
            label_field="name",
            filter_by=(
                "feedstock",
                "feedstock_id",
            ),
            exclude_by=(
                "scenario",
                "scenario_id",
            ),
        ),
        label="Geodataset",
    )
    inventory_algorithm = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="inventoryalgorithm-autocomplete",
            label_field="name",
        ),
        label="Inventory algorithm",
    )

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
