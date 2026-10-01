from django.forms import HiddenInput
from django.utils.html import escape
from django_tomselect.forms import TomSelectConfig, TomSelectModelChoiceField
from django_tomselect.widgets import TomSelectModelWidget

from distributions.models import TemporalDistribution
from maps.models import GeoDataset
from maps.views import CatchmentAutocompleteView
from utils.forms import ModalModelFormMixin, SimpleModelForm

from .models import Scenario, ScenarioInventoryConfiguration


class SeasonalDistributionModelForm(SimpleModelForm):
    class Meta:
        model = TemporalDistribution
        fields = ()


class ScenarioModelForm(SimpleModelForm):
    region = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="region-autocomplete",
            label_field="display_name",
        ),
        label="Region",
    )
    catchment = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="catchment-autocomplete",
            filter_by=("region", CatchmentAutocompleteView.IN_REGION_LOOKUP),
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


class InitialInstanceTomSelectModelWidget(TomSelectModelWidget):
    """Keeps a known initial instance selected when the dependent autocomplete
    source cannot resolve it without the client-side filter values."""

    initial_instance = None

    def get_context(self, name, value, attrs=None):
        context = super().get_context(name, value, attrs)
        instance = self.initial_instance
        if (
            instance is not None
            and not context["widget"]["selected_options"]
            and str(value) == str(instance.pk)
        ):
            label = getattr(instance, self.label_field or "name", str(instance))
            context["widget"]["selected_options"] = [
                {"value": str(instance.pk), "label": escape(str(label))}
            ]
        return context


class InitialInstanceTomSelectModelChoiceField(TomSelectModelChoiceField):
    widget_class = InitialInstanceTomSelectModelWidget


class ScenarioInventoryConfigurationForm(SimpleModelForm):
    feedstock = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="sampleseries-autocomplete",
            label_field="name",
        ),
        label="Feedstock",
    )
    geodataset = InitialInstanceTomSelectModelChoiceField(
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
            minimum_query_length=0,
            preload="focus",
        ),
        label="Geodataset",
    )
    inventory_algorithm = InitialInstanceTomSelectModelChoiceField(
        config=TomSelectConfig(
            url="scenario-inventoryalgorithm-autocomplete",
            label_field="name",
            filter_by=(
                "geodataset",
                "geodataset_id",
            ),
            exclude_by=(
                "feedstock",
                "feedstock_id",
            ),
            minimum_query_length=0,
            preload="focus",
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
        # The add form offers generic functions (geometry-driven) plus
        # registered algorithms via a JS-rendered `algorithm_choice` select,
        # not a model-bound TomSelect.
        del self.fields["inventory_algorithm"]
        initial = kwargs.get("initial")
        self.fields["scenario"].queryset = Scenario.objects.all()
        self.fields["scenario"].initial = initial.get("scenario")
        self.fields["scenario"].widget = HiddenInput()
        self.fields["feedstock"].queryset = initial.get("feedstocks")
        self.fields["geodataset"].queryset = GeoDataset.objects.none()
        # Dataset-first flow: geodataset drives the function options.
        self.fields["feedstock"] = self.fields.pop("feedstock")


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
        self.fields["geodataset"].widget.initial_instance = geodataset
        self.fields[
            "inventory_algorithm"
        ].queryset = scenario.available_inventory_algorithms(
            feedstock=feedstock, geodataset=geodataset
        )
        self.fields["inventory_algorithm"].initial = algorithm
        self.fields["inventory_algorithm"].widget.initial_instance = algorithm
