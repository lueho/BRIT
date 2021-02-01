from crispy_forms.bootstrap import StrictButton, FieldWithButtons
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Field
from django import forms
from django.forms import (Form,
                          modelformset_factory,
                          ModelChoiceField,
                          ModelForm,
                          MultipleChoiceField,
                          HiddenInput)
from django.forms.widgets import CheckboxSelectMultiple
from leaflet.forms.widgets import LeafletWidget

from .models import (
    Catchment,
    GeoDataset,
    InventoryAlgorithm,
    Material,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialComponentGroupSettings,
    MaterialComponentShare,
    Region,
    Scenario,
    ScenarioInventoryConfiguration,
    SeasonalDistribution,
)


# class Row(Div):
#     css_class = "form-row"


# ----------- Catchments -----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CatchmentCreateForm(ModelForm):
    class Meta:
        model = Catchment
        fields = ['region', 'name', 'description', 'geom', ]
        widgets = {'geom': LeafletWidget()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['geom'].label = ''


class CatchmentForm(ModelForm):
    class Meta:
        model = Catchment
        fields = ('region', 'name', 'description', 'geom',)
        widgets = {'geom': LeafletWidget()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['geom'].label = ''

    def clean(self):
        catchment = super().clean()
        region = catchment.get('region')
        if region and catchment:
            if not region.geom.contains(catchment.get('geom')):
                self.add_error('geom', 'The catchment must be inside the region.')


class CatchmentQueryForm(Form):
    region = ModelChoiceField(queryset=Region.objects.all())
    category = MultipleChoiceField(
        choices=(('standard', 'Standard'), ('custom', 'Custom'),),
        widget=CheckboxSelectMultiple
    )
    catchment = ModelChoiceField(queryset=Catchment.objects.all())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


# ----------- Materials/Feedstocks -------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MaterialModelForm(ModelForm):
    class Meta:
        model = Material
        fields = ('name', 'description', 'is_feedstock', 'stan_flow_id',)


class MaterialComponentModelForm(ModelForm):
    class Meta:
        model = MaterialComponent
        fields = ('name', 'description',)


class MaterialComponentGroupModelForm(ModelForm):
    class Meta:
        model = MaterialComponentGroup
        fields = ('name', 'description',)


class MaterialAddComponentGroupForm(ModelForm):
    initial = {}

    class Meta:
        model = MaterialComponentGroupSettings
        fields = ('scenario', 'material', 'group', 'fractions_of',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial = kwargs.get('initial')
        self.fields['scenario'].queryset = Scenario.objects.all()
        self.fields['scenario'].initial = self.initial.get('scenario')
        self.fields['material'].queryset = Material.objects.all()
        self.fields['material'].initial = self.initial.get('material')

    @property
    def helper(self):
        helper = FormHelper()
        helper.form_method = 'POST'
        helper.layout = Layout(
            Field('scenario', type='hidden'),
            Field('material', type='hidden'),
            Row(
                Field('group', type='select'),
                FieldWithButtons('fractions_of',
                                 StrictButton("Add", type="submit", name="add_group", css_class="btn-primary")),
            )
        )
        return helper


class MaterialComponentShareModelForm(ModelForm):
    class Meta:
        model = MaterialComponentShare
        fields = '__all__'


#
# class MaterialComponentShareBaseFormSet(BaseFormSet):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)

class MaterialComponentShareForm(Form):
    name = forms.CharField()


MaterialComponentShareFormSet = modelformset_factory(
    MaterialComponentShare,
    exclude=('scenario', 'distribution', 'group_settings',),
    extra=2
)


class MaterialComponentGroupAddComponentForm(MaterialComponentShareModelForm):
    initial = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial = kwargs.get('initial')
        self.fields['group_settings'].queryset = MaterialComponentGroupSettings.objects.all()
        self.fields['group_settings'].initial = self.initial.get('group_settings')
        self.fields['group_settings'].widget = HiddenInput()
        self.fields['component'].label = 'Add component'

    @property
    def helper(self):
        helper = FormHelper()
        helper.form_method = 'POST'
        # self.helper.form_action = reverse('material_component_group_composition',
        #                                   kwargs={'scenario_pk': self.instance.scenario,
        #                                           'material_pk': self.instance.material,
        #                                           'group_pk': self.instance.group}
        #                                   )
        helper.layout = Layout(
            Field('group_settings', type='hidden'),
            Row(
                FieldWithButtons('component',
                                 StrictButton("Add", type="submit", name="add_component", css_class="btn-primary")),
            )
        )
        return helper

    class Meta:
        model = MaterialComponentShare
        fields = ('group_settings', 'component',)


class SeasonalDistributionModelForm(ModelForm):
    class Meta:
        model = SeasonalDistribution
        fields = ('values',)


# ----------- Inventories -------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class ScenarioModelForm(ModelForm):
    class Meta:
        model = Scenario
        fields = ['name', 'description', 'region', 'catchment']


class ScenarioInventoryConfigurationForm(ModelForm):
    class Meta:
        model = ScenarioInventoryConfiguration
        fields = '__all__'


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
        self.helper = FormHelper()


class ScenarioInventoryConfigurationUpdateForm(ScenarioInventoryConfigurationForm):

    # current_algorithm = ModelChoiceField(InventoryAlgorithm.objects.all())
    #
    # class Meta(ScenarioInventoryConfigurationForm.Meta):
    #     fields = ScenarioInventoryConfigurationForm.Meta.fields + ('current_algorithm')

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
        # self.fields['current_algorithm'].queryset = InventoryAlgorithm.objects.all()
        # self.fields['current_algorithm'].initial = algorithm
        # self.fields['current_algorithm'].widget = HiddenInput()
        self.helper = FormHelper()
