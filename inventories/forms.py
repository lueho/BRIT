from crispy_forms.helper import FormHelper
from dal import forward
from dal.autocomplete import ModelSelect2
from django.forms import ModelChoiceField
from extra_views import InlineFormSetFactory

from distributions.models import TemporalDistribution
from maps.models import Catchment, GeoDataset, Region
from materials.models import SampleSeries
from utils.forms import AutoCompleteModelForm, ModalModelFormMixin, SimpleModelForm
from .models import Algorithm, Scenario, ScenarioConfiguration, ParameterValue, ScenarioParameterSetting


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


# ----------- Scenario configuration -----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class ScenarioConfigurationModelForm(AutoCompleteModelForm):
    scenario = ModelChoiceField(
        queryset=Scenario.objects.all(),
        widget=ModelSelect2(url='scenario-name-autocomplete'),  # TODO: This should not be editable
    )
    feedstock = ModelChoiceField(
        queryset=SampleSeries.objects.all(),
        widget=ModelSelect2(url='sampleseries-autocomplete'),
        # TODO: Limit choices with respect to geodataset and algorithm
    )
    geodataset = ModelChoiceField(
        queryset=GeoDataset.objects.all(),
        widget=ModelSelect2(url='geodataset-name-autocomplete', forward=['algorithm', ]),
        # TODO: Limit choices with respect to feedstock
    )
    algorithm = ModelChoiceField(
        queryset=Algorithm.objects.all(),
        widget=ModelSelect2(url='algorithm-name-autocomplete', forward=['geodataset', ]),
        # TODO: Limit choices with respect to feedstock
    )

    class Meta:
        model = ScenarioConfiguration
        fields = ('scenario', 'feedstock', 'geodataset', 'algorithm')


# ----------- Scenario Parameter Settings ------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class NoFormTagFormSetHelper(FormHelper):  # TODO: Where to put this for reuse?

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_tag = False


class ScenarioParameterSettingForm(AutoCompleteModelForm):
    parameter_value = ModelChoiceField(
        queryset=ParameterValue.objects.all(),
        widget=ModelSelect2(url='parametervalue-name-autocomplete'),
    )

    class Meta:
        model = ScenarioParameterSetting
        fields = ['parameter_value']

    def __init__(self, *args, **kwargs):
        super(ScenarioParameterSettingForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.parameter_value:
            self.fields['parameter_value'].label = self.instance.parameter_value.parameter.descriptive_name
            self.fields['parameter_value'].queryset = ParameterValue.objects.filter(parameter=self.instance.parameter_value.parameter)
            self.fields['parameter_value'].widget.forward=(forward.Const(self.instance.parameter_value.parameter.id, 'parameter'), )


class ScenarioParameterSettingInline(InlineFormSetFactory):
    model = ScenarioParameterSetting
    form_class = ScenarioParameterSettingForm
    fields = ['parameter_value']
    factory_kwargs = {'extra': 0, 'max_num': 10, 'can_delete': False}

    def get_initial(self):
        return [
            {'parameter_value': ParameterValue.objects.get(parameter=parameter, value=parameter.default_value.value)}
            for parameter in
            self.object.algorithm.parameters.all()]
