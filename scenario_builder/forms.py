from crispy_forms.bootstrap import StrictButton, FieldWithButtons
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Field
from django.contrib.auth.models import User
from django.forms import (Form,
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
    MaterialComponentGroupShare,
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
        fields = ('name', 'description', 'is_feedstock')


class MaterialComponentModelForm(ModelForm):
    class Meta:
        model = MaterialComponent
        fields = ('name', 'description',)


class MaterialComponentGroupModelForm(ModelForm):
    class Meta:
        model = MaterialComponentGroup
        fields = ('name', 'description', 'fractions_of',)


class MaterialComponentGroupShareModelForm(ModelForm):
    class Meta:
        model = MaterialComponentGroupShare
        fields = '__all__'


class MaterialComponentGroupAddComponentForm(MaterialComponentGroupShareModelForm):
    initial = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial = kwargs.get('initial')
        self.fields['owner'].queryset = User.objects.all()
        self.fields['owner'].initial = self.initial.get('owner')
        self.fields['owner'].widget = HiddenInput()
        self.fields['scenario'].queryset = Scenario.objects.all()
        self.fields['scenario'].initial = self.initial.get('scenario')
        self.fields['scenario'].widget = HiddenInput()
        self.fields['material'].queryset = Material.objects.filter(is_feedstock=True)
        self.fields['material'].initial = self.initial.get('material')
        self.fields['material'].widget = HiddenInput()
        self.fields['group'].queryset = MaterialComponentGroup.objects.all()
        self.fields['group'].initial = self.initial.get('group')
        self.fields['group'].widget = HiddenInput()
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
            Field('owner', type='hidden'),
            Field('scenario', type='hidden'),
            Field('material', type='hidden'),
            Field('group', type='hidden'),
            Row(
                FieldWithButtons('component',
                                 StrictButton("Add", type="submit", name="add_component", css_class="btn-primary")),
            )
        )
        return helper

    class Meta:
        model = MaterialComponentGroupShare
        fields = ('owner', 'scenario', 'material', 'group', 'component',)


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
