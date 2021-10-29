from bootstrap_modal_forms.forms import BSModalModelForm
from crispy_forms.helper import FormHelper, Layout
from crispy_forms.layout import Div, Field
from django.forms import (CheckboxSelectMultiple,
                          ModelMultipleChoiceField,
                          ChoiceField,
                          Form,
                          ModelForm,
                          MultipleChoiceField,
                          RadioSelect,
                          Widget,
                          NumberInput,
                          )
from django.forms.models import BaseInlineFormSet
from django.utils.safestring import mark_safe
from extra_views import InlineFormSetFactory

from distributions.models import Timestep
from materials.models import MaterialComponent
from .models import Culture, Greenhouse, GreenhouseGrowthCycle, NantesGreenhouses, GrowthTimeStepSet, GrowthShare

CROP_CHOICES = (
    (1, "Cucumber"),
    (2, "Tomato"),
)

HEATING_CHOICES = (
    (1, "All"),
    (2, "Heated"),
    (3, "Not heated")
)

LIGHTING_CHOICES = (
    (1, "All"),
    (2, "Lighting"),
    (3, "No Lighting")
)

PROD_MODE_CHOICES = (
    (1, "All"),
    (2, "On Ground"),
    (3, "Above Ground")
)

CULT_MANAGEMENT_CHOICES = (
    (1, "All"),
    (2, "Classic"),
    (3, "High-Wire")
)


class CultureModelForm(BSModalModelForm):
    class Meta:
        model = Culture
        fields = ('name', 'residue')


class GreenhouseModelForm(ModelForm):
    class Meta:
        model = Greenhouse
        fields = ('name', 'heated', 'lighted', 'above_ground', 'high_wire')


class GreenhouseModalModelForm(BSModalModelForm):
    class Meta:
        model = Greenhouse
        fields = ('name', 'heated', 'lighted', 'above_ground', 'high_wire')


class GreenhouseGrowthCycleModelForm(ModelForm):
    class Meta:
        model = GreenhouseGrowthCycle
        fields = ()


class GrowthTimestepInline(InlineFormSetFactory):
    model = GrowthTimeStepSet
    fields = ['owner', 'timestep', 'growth_cycle']


class GrowthCycleCreateForm(BSModalModelForm):
    timesteps = ModelMultipleChoiceField(queryset=Timestep.objects.filter(distribution__name='Months of the year'))

    class Meta:
        model = GreenhouseGrowthCycle
        fields = ('culture',)


class PlainTextComponentWidget(Widget):
    def render(self, name, value, attrs=None, renderer=None):
        if hasattr(self, 'initial'):
            value = self.initial
        object_name = MaterialComponent.objects.get(id=value).name

        return mark_safe("<div style=\"min-width: 7em; padding-right: 12px;\">" + (str(
            object_name) if value is not None else '-') + "</div>" + f"<input type='hidden' name='{name}' value='{value}'>")


class InlineGrowthShare(InlineFormSetFactory):
    model = GrowthShare
    fields = ('component', 'average', 'standard_deviation')
    factory_kwargs = {
        'formset': BaseInlineFormSet,
        'extra': 0,
        'can_delete': False,
        'widgets': {
            'component': PlainTextComponentWidget(),
            'average': NumberInput(attrs={'min': 0, 'step': 0.1}),
            'standard_deviation': NumberInput(attrs={'min': 0, 'step': 0.1})
        }
    }


class GrowthShareFormSetHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.template = 'bootstrap4/table_inline_formset.html'
        self.form_method = 'post'
        self.layout = Layout(
            Row(
                Field('component'),
                Field('average', style="max-width:7em"),
                Field('standard_deviation', style="max-width:7em"),
            ),
        )
        self.render_required_fields = True


class AddGreenhouseGrowthCycleModelForm(ModelForm):
    class Meta:
        model = GreenhouseGrowthCycle
        fields = ()


class UpdateGreenhouseGrowthCycleValuesForm(GreenhouseGrowthCycleModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # initial = kwargs.get('initial')
        # self.fields['material'].initial = initial['material'].id
        # self.fields['material'].widget = HiddenInput()
        # self.fields['component'].initial = initial['component'].id
        # self.fields['component'].widget = HiddenInput()


class Row(Div):
    css_class = "form-row"


class NantesGreenhousesFilterForm(Form):
    crops = MultipleChoiceField(widget=CheckboxSelectMultiple, choices=CROP_CHOICES, initial=('1', '2'))
    heating = ChoiceField(widget=RadioSelect, choices=HEATING_CHOICES, initial='1')
    lighting = ChoiceField(widget=RadioSelect, choices=LIGHTING_CHOICES, initial='1')
    prod_mode = ChoiceField(widget=RadioSelect, choices=PROD_MODE_CHOICES, initial='1')
    cult_man = ChoiceField(widget=RadioSelect, choices=CULT_MANAGEMENT_CHOICES, initial='1')
    helper = FormHelper()
    helper.layout = Layout(
        Row(
            Field('heating', wrapper_class='col-md-6'),
            Field('lighting', wrapper_class='col-md-6'),
            Field('prod_mode', wrapper_class='col-md-6'),
            Field('cult_man', wrapper_class='col-md-6'),
            Field('crops', wrapper_class='col-md-12')
        )
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['heating'].label = 'Heating'
        self.fields['lighting'].label = 'Lighting'
        self.fields['prod_mode'].label = 'Production Mode'
        self.fields['cult_man'].label = 'Cultivation Management'
        helper = FormHelper()
        helper.layout = Layout(
            Row(
                Field('heating', wrapper_class='col-md-6'),
                Field('lighting', wrapper_class='col-md-6')
            )
        )

    class Meta:
        model = NantesGreenhouses
