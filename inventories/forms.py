from dal.autocomplete import ModelSelect2
from django.forms import HiddenInput, ModelChoiceField

from distributions.models import TemporalDistribution
from maps.models import Catchment, GeoDataset, Region
from utils.forms import AutoCompleteModelForm, ModalModelFormMixin, SimpleModelForm
from .models import InventoryAlgorithm, Scenario, ScenarioInventoryConfiguration


class SeasonalDistributionModelForm(SimpleModelForm):
    class Meta:
        model = TemporalDistribution
        fields = ()


class ScenarioModelForm(AutoCompleteModelForm):
    region = ModelChoiceField(
        queryset=Region.objects.all(),
        widget=ModelSelect2(url='region-autocomplete'),
        required=False
    )
    catchment = ModelChoiceField(
        queryset=Catchment.objects.all(),
        widget=ModelSelect2(url='catchment-autocomplete'),
        required=False
    )

    def __init__(self, *args, **kwargs):
        region_id = kwargs.pop('region_id', None)
        super().__init__(*args, **kwargs)
        if region_id is not None:
            self.fields['region'].queryset = Region.objects.filter(id=region_id)
            self.fields['catchment'].queryset = Catchment.objects.filter(parent_region_id=region_id)

    class Meta:
        model = Scenario
        fields = ['name', 'description', 'region', 'catchment']

class ScenarioModalModelForm(ModalModelFormMixin, ScenarioModelForm):
    pass


class ScenarioInventoryConfigurationForm(SimpleModelForm):
    class Meta:
        model = ScenarioInventoryConfiguration
        fields = ('scenario', 'feedstock', 'geodataset', 'inventory_algorithm', 'inventory_parameter',
                  'inventory_value')


class ScenarioInventoryConfigurationAddForm(ScenarioInventoryConfigurationForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        del self.fields['inventory_parameter']
        del self.fields['inventory_value']
        initial = kwargs.get('initial')
        self.fields['scenario'].queryset = Scenario.objects.all()
        self.fields['scenario'].initial = initial.get('scenario')
        self.fields['scenario'].widget = HiddenInput()
        self.fields['feedstock'].queryset = initial.get('feedstocks')
        self.fields['geodataset'].queryset = GeoDataset.objects.none()
        self.fields['inventory_algorithm'].queryset = InventoryAlgorithm.objects.none()


class ScenarioInventoryConfigurationUpdateForm(ScenarioInventoryConfigurationForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        del self.fields['inventory_parameter']
        del self.fields['inventory_value']
        initial = kwargs.get('initial')
        scenario = initial.get('scenario')
        feedstock = initial.get('feedstock')
        geodataset = initial.get('geodataset')
        algorithm = initial.get('inventory_algorithm')
        self.fields['scenario'].queryset = Scenario.objects.all()
        self.fields['scenario'].initial = scenario
        self.fields['scenario'].widget = HiddenInput()
        self.fields['feedstock'].queryset = scenario.available_feedstocks()
        self.fields['feedstock'].initial = feedstock
        self.fields['geodataset'].queryset = scenario.available_geodatasets(feedstock=feedstock)
        self.fields['geodataset'].initial = geodataset
        self.fields['inventory_algorithm'].queryset = scenario.available_inventory_algorithms(feedstock=feedstock,
                                                                                              geodataset=geodataset)
        self.fields['inventory_algorithm'].initial = algorithm
