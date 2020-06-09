from crispy_forms.helper import FormHelper
from django.forms import ModelForm
from leaflet.forms.widgets import LeafletWidget

from .models import Catchment, ScenarioInventoryConfiguration, Material, GeoDataset, InventoryAlgorithm, Scenario


class CatchmentForm(ModelForm):
    class Meta:
        model = Catchment
        fields = ['name', 'description', 'geom', ]
        widgets = {'geom': LeafletWidget()}

# class CatchmentSelectForm(ModelForm):

# title = ModelMultipleChoiceField(queryset=Catchment.objects.all(),
# required=True,
# widget=FilteredSelectedMultiple("Catchments", is_stacked=False)

# class Media:
# css = {'all': ('/static/admin/css/widgets.css',), }
# js = {'',)

# def __init__(self, parents=None, *args, **kwargs):
# super(CatchmentSelectForm, self).__init__(*args, **kwargs)

class ScenarioModelForm(ModelForm):
    class Meta:
        model = Scenario
        fields = ['name', 'description', 'region', 'catchment']


class ScenarioInventoryConfigurationForm(ModelForm):
    class Meta:
        model = ScenarioInventoryConfiguration
        fields = ['scenario', 'feedstock', 'geodataset', 'inventory_algorithm', ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['scenario'].queryset = Scenario.objects.all()
        self.fields['feedstock'].queryset = Material.objects.none()
        self.fields['geodataset'].queryset = GeoDataset.objects.none()
        self.fields['inventory_algorithm'].queryset = InventoryAlgorithm.objects.none()
        self.helper = FormHelper()
