from dal import autocomplete
from django_filters import CharFilter, ModelChoiceFilter

from maps.models import Catchment
from utils.filters import CrispyAutocompleteFilterSet
from .models import Scenario


class ScenarioFilterSet(CrispyAutocompleteFilterSet):
    name = CharFilter(
        field_name='name',
        lookup_expr='icontains',
        widget=autocomplete.ListSelect2(url='scenario-name-autocomplete'),
        label='Scenario Name'
    )
    catchment = ModelChoiceFilter(
        queryset=Catchment.objects.all(),
        widget=autocomplete.ModelSelect2(url='catchment-autocomplete'),
        label='Catchment'
    )

    class Meta:
        model = Scenario
        fields = ['name', 'catchment']
