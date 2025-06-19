from django_filters import ModelChoiceFilter
from django_tomselect.forms import TomSelectConfig
from django_tomselect.widgets import TomSelectModelWidget

from maps.models import Catchment
from utils.filters import UserCreatedObjectScopedFilterSet

from .models import Scenario


class ScenarioFilterSet(UserCreatedObjectScopedFilterSet):
    name = ModelChoiceFilter(
        queryset=Scenario.objects.none(),
        field_name="name",
        label="Name",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="scenario-autocomplete",
                label_field="name",
            ),
        ),
    )
    catchment = ModelChoiceFilter(
        queryset=Catchment.objects.all(),
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="catchment-autocomplete",
                label_field="name",
            ),
        ),
    )

    class Meta:
        model = Scenario
        fields = ["scope", "name", "catchment"]
