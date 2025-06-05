from crispy_forms.helper import FormHelper, Layout
from crispy_forms.layout import Field, Row
from django.forms import ModelMultipleChoiceField, NumberInput, Widget
from django.forms.models import BaseInlineFormSet
from django.utils.safestring import mark_safe
from extra_views import InlineFormSetFactory

from distributions.models import Timestep
from materials.models import MaterialComponent
from utils.forms import ModalModelForm, ModalModelFormMixin, SimpleModelForm
from .models import (
    Culture,
    Greenhouse,
    GreenhouseGrowthCycle,
    GrowthShare,
    GrowthTimeStepSet,
)


class CultureModelForm(SimpleModelForm):
    class Meta:
        model = Culture
        fields = ("name", "residue", "description")


class CultureModalModelForm(ModalModelForm):
    class Meta:
        model = Culture
        fields = ("name", "residue")


class GreenhouseModelForm(SimpleModelForm):
    class Meta:
        model = Greenhouse
        fields = ("name", "heated", "lighted", "above_ground", "high_wire")


class GreenhouseModalModelForm(ModalModelFormMixin, GreenhouseModelForm):
    pass


class GreenhouseGrowthCycleModelForm(SimpleModelForm):
    class Meta:
        model = GreenhouseGrowthCycle
        fields = ("cycle_number", "culture", "greenhouse")


class GrowthCycleModelForm(SimpleModelForm):
    class Meta:
        model = GreenhouseGrowthCycle
        fields = ()


class GrowthTimestepInline(InlineFormSetFactory):
    model = GrowthTimeStepSet
    fields = ["owner", "timestep", "growth_cycle"]


class GrowthCycleCreateForm(ModalModelForm):
    timesteps = ModelMultipleChoiceField(
        queryset=Timestep.objects.filter(distribution__name="Months of the year")
    )

    class Meta:
        model = GreenhouseGrowthCycle
        fields = ("culture",)


class PlainTextComponentWidget(Widget):
    def render(self, name, value, attrs=None, renderer=None):
        if hasattr(self, "initial"):
            value = self.initial
        obj = MaterialComponent.objects.filter(id=value).first()

        return mark_safe(
            '<div style="min-width: 7em; padding-right: 12px;">'
            + (str(obj.name) if value is not None else "-")
            + "</div>"
            + f"<input type='hidden' name='{name}' value='{value}'>"
        )


class InlineGrowthShare(InlineFormSetFactory):
    model = GrowthShare
    fields = ("component", "average", "standard_deviation")
    factory_kwargs = {
        "formset": BaseInlineFormSet,
        "extra": 0,
        "can_delete": False,
        "widgets": {
            "component": PlainTextComponentWidget(),
            "average": NumberInput(attrs={"min": 0, "step": 0.1}),
            "standard_deviation": NumberInput(attrs={"min": 0, "step": 0.1}),
        },
    }


class GrowthShareFormSetHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.template = "bootstrap5/dynamic_table_inline_formset.html"
        self.form_method = "post"
        self.layout = Layout(
            Row(
                Field("component"),
                Field("average", style="max-width:7em"),
                Field("standard_deviation", style="max-width:7em"),
            ),
        )
        self.render_required_fields = True


class AddGreenhouseGrowthCycleModelForm(SimpleModelForm):
    class Meta:
        model = GreenhouseGrowthCycle
        fields = ()


class UpdateGreenhouseGrowthCycleValuesForm(GrowthCycleModelForm):
    pass
