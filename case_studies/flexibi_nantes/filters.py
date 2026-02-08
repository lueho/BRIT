from crispy_forms.helper import FormHelper
from crispy_forms.layout import Field, Layout, Row
from django.forms import CheckboxSelectMultiple, RadioSelect
from django_filters.filters import (
    BooleanFilter,
    ModelChoiceFilter,
    MultipleChoiceFilter,
)
from django_tomselect.app_settings import TomSelectConfig
from django_tomselect.widgets import TomSelectModelWidget

from maps.models import Catchment
from utils.filters import BaseCrispyFilterSet, UserCreatedObjectScopedFilterSet
from utils.object_management.permissions import (
    apply_scope_filter,
    filter_queryset_for_user,
)

from .models import Culture, Greenhouse, NantesGreenhouses

HEATING_CHOICES = (
    ("", "All"),
    (True, "Heated"),
    (False, "Not heated"),
)

LIGHTING_CHOICES = (
    ("", "All"),
    (True, "Lighting"),
    (False, "No lighting"),
)

ABOVE_GROUND_CHOICES = (
    ("", "All"),
    (True, "Above Ground"),
    (False, "On Ground"),
)

HIGH_WIRE_CHOICES = (
    ("", "All"),
    (True, "High-Wire"),
    (False, "Classic"),
)

CROP_CHOICES = (("Tomato", "Tomato"), ("Cucumber", "Cucumber"))


class GreenhouseTypeFilterFormHelper(FormHelper):
    layout = Layout(
        Row(
            Field("heated", wrapper_class="col-md-6"),
            Field("lighted", wrapper_class="col-md-6"),
            Field("above_ground", wrapper_class="col-md-6"),
            Field("high_wire", wrapper_class="col-md-6"),
        )
    )


class GreenhouseTypeFilter(UserCreatedObjectScopedFilterSet):
    heated = BooleanFilter(widget=RadioSelect(choices=HEATING_CHOICES), label="Heating")
    lighted = BooleanFilter(
        widget=RadioSelect(choices=LIGHTING_CHOICES), label="Lighting"
    )
    above_ground = BooleanFilter(
        widget=RadioSelect(choices=ABOVE_GROUND_CHOICES), label="Production mode"
    )
    high_wire = BooleanFilter(
        widget=RadioSelect(choices=HIGH_WIRE_CHOICES), label="Culture management"
    )

    class Meta:
        model = Greenhouse
        fields = ("scope", "heated", "lighted", "above_ground", "high_wire")
        form_helper = GreenhouseTypeFilterFormHelper


class CultureListFilter(UserCreatedObjectScopedFilterSet):
    name = ModelChoiceFilter(
        queryset=Culture.objects.none(),
        field_name="name",
        label="Culture Name",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="culture-autocomplete",
                filter_by=("scope", "name"),
            ),
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = getattr(self, "request", None)
        queryset = Culture.objects.all()
        if request and hasattr(request, "user"):
            queryset = filter_queryset_for_user(queryset, request.user)

        scope_value = None
        try:
            if hasattr(self, "data") and self.data:
                scope_value = self.data.get("scope")
        except Exception:
            scope_value = None

        if scope_value:
            queryset = apply_scope_filter(
                queryset, scope_value, user=getattr(request, "user", None)
            )

        self.filters["name"].queryset = queryset

    class Meta:
        model = Culture
        fields = ("scope", "name")


class NantesGreenhouseFilterSetFormHelper(FormHelper):
    layout = Layout(
        Row(
            Field("catchment", wrapper_class="col-md-12"),
        ),
        Row(
            Field("heated", wrapper_class="col-md-6"),
            Field("lighted", wrapper_class="col-md-6"),
            Field("above_ground", wrapper_class="col-md-6"),
            Field("high_wire", wrapper_class="col-md-6"),
            Field("crops", wrapper_class="col-md-12"),
        ),
    )


class NantesGreenhousesFilterSet(BaseCrispyFilterSet):
    catchment = ModelChoiceFilter(
        queryset=Catchment.objects.all(),
        widget=TomSelectModelWidget(
            config=TomSelectConfig(url="nantesgreenhouses-catchment-autocomplete")
        ),
        method="catchment_filter",
        label="Catchment",
    )
    crops = MultipleChoiceFilter(
        field_name="culture_1", widget=CheckboxSelectMultiple(), choices=CROP_CHOICES
    )
    heated = BooleanFilter(widget=RadioSelect(choices=HEATING_CHOICES), label="Heating")
    lighted = BooleanFilter(
        widget=RadioSelect(choices=LIGHTING_CHOICES), label="Lighting"
    )
    above_ground = BooleanFilter(
        widget=RadioSelect(choices=ABOVE_GROUND_CHOICES), label="Production mode"
    )
    high_wire = BooleanFilter(
        widget=RadioSelect(choices=HIGH_WIRE_CHOICES), label="Culture management"
    )

    class Meta:
        model = NantesGreenhouses
        fields = (
            "catchment",
            "heated",
            "lighted",
            "above_ground",
            "high_wire",
            "crops",
        )
        form_helper = NantesGreenhouseFilterSetFormHelper

    @staticmethod
    def catchment_filter(qs, __, value):
        return qs.filter(geom__within=value.region.borders.geom)


class GreenhouseFilterFormHelper(FormHelper):
    layout = Layout(
        Row(
            Field("heated", wrapper_class="col-md-6"),
            Field("lighted", wrapper_class="col-md-6"),
            Field("above_ground", wrapper_class="col-md-6"),
            Field("high_wire", wrapper_class="col-md-6"),
            Field("crops", wrapper_class="col-md-12"),
        )
    )


class GreenhouseFilter(BaseCrispyFilterSet):
    crops = MultipleChoiceFilter(
        field_name="culture_1", widget=CheckboxSelectMultiple(), choices=CROP_CHOICES
    )
    heated = BooleanFilter(widget=RadioSelect(choices=HEATING_CHOICES), label="Heating")
    lighted = BooleanFilter(
        widget=RadioSelect(choices=LIGHTING_CHOICES), label="Lighting"
    )
    above_ground = BooleanFilter(
        widget=RadioSelect(choices=ABOVE_GROUND_CHOICES), label="Production mode"
    )
    high_wire = BooleanFilter(
        widget=RadioSelect(choices=HIGH_WIRE_CHOICES), label="Culture management"
    )

    class Meta:
        model = NantesGreenhouses
        fields = ("heated", "lighted", "above_ground", "high_wire", "crops")
        form_helper = GreenhouseFilterFormHelper
