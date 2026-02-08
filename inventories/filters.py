from django_filters import ModelChoiceFilter
from django_tomselect.forms import TomSelectConfig
from django_tomselect.widgets import TomSelectModelWidget

from maps.models import Catchment
from utils.filters import UserCreatedObjectScopedFilterSet
from utils.object_management.permissions import (
    apply_scope_filter,
    filter_queryset_for_user,
)

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
                filter_by=("scope", "name"),
            ),
        ),
    )
    catchment = ModelChoiceFilter(
        queryset=Catchment.objects.none(),
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="catchment-autocomplete",
                label_field="name",
                filter_by=("scope", "name"),
            ),
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = getattr(self, "request", None)

        for field_name, model_cls in (("name", Scenario), ("catchment", Catchment)):
            queryset = model_cls.objects.all()
            if request and hasattr(request, "user"):
                queryset = filter_queryset_for_user(queryset, request.user)

            scope_value = None
            try:
                if hasattr(self, "data") and self.data:
                    scope_value = self.data.get("scope")
                if not scope_value and hasattr(self, "form"):
                    scope_value = self.form.initial.get("scope")
            except Exception:
                scope_value = None

            if scope_value:
                queryset = apply_scope_filter(
                    queryset, scope_value, user=getattr(request, "user", None)
                )

            self.filters[field_name].queryset = queryset

    class Meta:
        model = Scenario
        fields = ["scope", "name", "catchment"]
