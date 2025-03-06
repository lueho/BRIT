from django_filters import CharFilter, ModelChoiceFilter

from maps.models import Catchment
from utils.filters import CrispyAutocompleteFilterSet
from utils.widgets import BSListSelect2, BSModelSelect2
from .models import Scenario


class ScenarioFilterSet(CrispyAutocompleteFilterSet):
    name = CharFilter(
        field_name='name',
        lookup_expr='icontains',
        widget=BSListSelect2(url='scenario-name-autocomplete'),
        label='Scenario Name'
    )
    catchment = ModelChoiceFilter(
        queryset=Catchment.objects.all(),
        widget=BSModelSelect2(url='catchment-autocomplete'),
        label='Catchment'
    )

    class Meta:
        model = Scenario
        fields = ['name', 'catchment']
