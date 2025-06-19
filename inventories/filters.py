from django.forms import HiddenInput
from django_filters import ChoiceFilter, ModelChoiceFilter
from django_tomselect.forms import TomSelectConfig
from django_tomselect.widgets import TomSelectModelWidget

from maps.models import Catchment
from utils.filters import BaseCrispyFilterSet

from .models import Scenario


class ScenarioFilterSet(BaseCrispyFilterSet):
    scope = ChoiceFilter(
        choices=(("published", "Published"), ("private", "Private")),
        widget=HiddenInput(),
        method="filter_scope",
        label="",
    )
    name = ModelChoiceFilter(
        queryset=Scenario.objects.none(),
        field_name="name",
        label="Name",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="scenario-autocomplete",
                label_field="name",
                filter_by=("scope", "name"),
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

    def filter_scope(self, queryset, name, value):
        """Filter queryset by published vs private depending on scope param."""
        if value == "private":
            if not self.request.user.is_authenticated:
                return queryset.none()
            return queryset.filter(owner=self.request.user)
        return queryset.filter(publication_status="published")
