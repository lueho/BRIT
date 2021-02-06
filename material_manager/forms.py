from crispy_forms.bootstrap import StrictButton, FieldWithButtons
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Field
from django import forms
from django.forms import (modelformset_factory,
                          ModelForm)

from flexibi_dst.models import (
    TemporalDistribution,
    Timestep,
)
from .models import (
    Material,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialComponentGroupSettings,
    MaterialComponentShare,

)


# ----------- Materials/Feedstocks -------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MaterialModelForm(ModelForm):
    class Meta:
        model = Material
        fields = ('name', 'description', 'is_feedstock', 'stan_flow_id',)


class MaterialComponentModelForm(ModelForm):
    class Meta:
        model = MaterialComponent
        fields = ('name', 'description',)


class MaterialComponentGroupModelForm(ModelForm):
    class Meta:
        model = MaterialComponentGroup
        fields = ('name', 'description',)


# class MaterialAddComponentGroupForm(ModelForm):
#     initial = {}
#
#     class Meta:
#         model = MaterialComponentGroupSettings
#         fields = ('scenario', 'material', 'group', 'fractions_of',)
#
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.initial = kwargs.get('initial')
#         self.fields['scenario'].queryset = Scenario.objects.all()
#         self.fields['scenario'].initial = self.initial.get('scenario')
#         self.fields['material'].queryset = Material.objects.all()
#         self.fields['material'].initial = self.initial.get('material')

# @property
# def helper(self):
#     helper = FormHelper()
#     helper.form_method = 'POST'
#     helper.layout = Layout(
#         Field('scenario', type='hidden'),
#         Field('material', type='hidden'),
#         Row(
#             Field('group', type='select'),
#             FieldWithButtons('fractions_of',
#                              StrictButton("Add", type="submit", name="add_group", css_class="btn-primary")),
#         )
#     )
#     return helper

class MaterialAddComponentGroupForm(ModelForm):
    class Meta:
        model = MaterialComponentGroupSettings
        fields = ('material_settings', 'group', 'fractions_of',)


class AddComponentForm(ModelForm):
    class Meta:
        model = MaterialComponentShare
        fields = ('component',)


# class AddComponentForm(Form):
#     component = ModelChoiceField(queryset=MaterialComponent.objects.all())


class MaterialComponentShareUpdateForm(ModelForm):
    class Meta:
        model = MaterialComponentShare
        fields = ('average', 'standard_deviation', 'source')


MaterialComponentShareFormSet = modelformset_factory(
    MaterialComponentShare,
    exclude=('scenario', 'distribution', 'group_settings',),
    extra=2
)


class MaterialComponentDistributionFormSetHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_method = 'post'
        self.layout = Layout(
            Row(
                Field('component'),
                Field('average'),
                Field('standard_deviation'),
            ),
        )
        self.render_required_fields = True


class MaterialComponentGroupShareDistributionUpdateForm(ModelForm):
    class Meta:
        model = MaterialComponentShare
        fields = ('component', 'average', 'standard_deviation',)


MaterialComponentGroupShareDistributionFormSet = modelformset_factory(
    MaterialComponentShare,
    form=MaterialComponentGroupShareDistributionUpdateForm,
    extra=0
)


class MaterialComponentGroupAddComponentForm(ModelForm):
    initial = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial = kwargs.get('initial')
        group_settings = self.initial.get('group_settings')
        self.fields['group_settings'].queryset = MaterialComponentGroupSettings.objects.filter(id=group_settings.id)
        self.fields['group_settings'].initial = group_settings
        self.fields['group_settings'].empty_label = None
        # self.fields['group_settings'].widget = HiddenInput()
        self.fields['timestep'].queryset = Timestep.objects.filter(name='Average')
        self.fields['timestep'].initial = Timestep.objects.get(name='Average')
        self.fields['timestep'].empty_label = None
        # self.fields['timestep'].widget = HiddenInput()
        self.fields['component'].label = 'Add component'
        self.fields['component'].queryset = MaterialComponent.objects.exclude(id__in=group_settings.component_ids)

    @property
    def helper(self):
        helper = FormHelper()
        helper.form_method = 'POST'
        helper.layout = Layout(
            Field('group_settings', type='hidden'),
            Field('timestep', type='hidden'),
            Row(
                FieldWithButtons('component',
                                 StrictButton("Add", type="submit", name="add_component", css_class="btn-primary")),
            )
        )
        return helper

    class Meta:
        model = MaterialComponentShare
        fields = ('group_settings', 'component', 'timestep',)


class MaterialComponentGroupAddTemporalDistributionForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        used_ids = kwargs.get('instance').temporal_distribution_ids
        used_ids.append(2)  # TODO: Find better way to avoid the "Averages" from given choices
        self.fields['temporal_distributions'].queryset = TemporalDistribution.objects.exclude(id__in=used_ids)

    class Meta:
        model = MaterialComponentGroupSettings
        fields = '__all__'
