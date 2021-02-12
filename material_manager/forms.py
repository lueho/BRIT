from bootstrap_modal_forms.forms import BSModalModelForm, BSModalForm
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Field
from django import forms
from extra_views import InlineFormSetFactory

from flexibi_dst.models import TemporalDistribution
from library.models import LiteratureSource
from .models import (
    Material,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialComponentGroupSettings,
    MaterialComponentShare,

)


class MaterialModelForm(BSModalModelForm):
    class Meta:
        model = Material
        fields = ('name', 'description')


class ComponentModelForm(BSModalModelForm):
    class Meta:
        model = MaterialComponent
        fields = ('name', 'description',)


class AddComponentForm(BSModalForm):
    component = forms.ModelChoiceField(queryset=MaterialComponent.objects.all())

    class Meta:
        fields = ('component',)


class AddLiteratureSourceForm(BSModalForm):
    source = forms.ModelChoiceField(queryset=LiteratureSource.objects.all())

    class Meta:
        fields = ('source',)


class AddSeasonalVariationForm(BSModalForm):
    temporal_distribution = forms.ModelChoiceField(queryset=TemporalDistribution.objects.all())

    class Meta:
        fields = ('temporal_distribution',)


class ComponentGroupModelForm(BSModalModelForm):
    class Meta:
        model = MaterialComponentGroup
        fields = ('name', 'description',)


class AddComponentGroupForm(BSModalForm):
    group = forms.ModelChoiceField(queryset=MaterialComponentGroup.objects.all())
    fractions_of = forms.ModelChoiceField(queryset=MaterialComponent.objects.all())

    class Meta:
        fields = ['group', 'fractions_of', ]


class ComponentShareUpdateForm(BSModalModelForm):
    class Meta:
        model = MaterialComponentShare
        fields = ('average', 'standard_deviation')
        widgets = {
            'average': forms.NumberInput(attrs={'min': 0, 'max': 1.0, 'step': 0.01}),
            'standard_deviation': forms.NumberInput(attrs={'min': 0, 'max': 1.0, 'step': 0.01})
        }


class CompositionUpdateForm(BSModalModelForm):
    class Meta:
        model = MaterialComponentShare
        fields = ('component', 'average', 'standard_deviation')
        widgets = {
            'average': forms.NumberInput(attrs={'min': 0, 'max': 1.0, 'step': 0.01}),
            'standard_deviation': forms.NumberInput(attrs={'min': 0, 'max': 1.0, 'step': 0.01})
        }


class ItemForm(BSModalModelForm):
    class Meta:
        model = MaterialComponentShare
        fields = ('component', 'average', 'standard_deviation')


class InlineComponentShare(InlineFormSetFactory):
    model = MaterialComponentShare
    fields = ('component', 'average', 'standard_deviation')
    factory_kwargs = {
        'extra': 0,
        'can_delete': False,
        'widgets': {
            'average': forms.NumberInput(attrs={'min': 0, 'max': 1.0, 'step': 0.01}),
            'standard_deviation': forms.NumberInput(attrs={'min': 0, 'max': 1.0, 'step': 0.01})
        }
    }


class AddTemporalDistributionForm(BSModalModelForm):
    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     used_ids = kwargs.get('instance').temporal_distribution_ids
    #     used_ids.append(2)  # TODO: Find better way to avoid the "Averages" from given choices
    #     self.fields['temporal_distributions'].queryset = TemporalDistribution.objects.exclude(id__in=used_ids)

    class Meta:
        model = MaterialComponentGroupSettings
        fields = '__all__'


MaterialComponentShareFormSet = forms.modelformset_factory(
    MaterialComponentShare,
    exclude=('scenario', 'distribution', 'group_settings',),
    extra=2
)


class ComponentShareDistributionFormSetHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_method = 'post'
        self.layout = Layout(
            Row(
                Field('component'),
                Field('average', style="max-width:7em"),
                Field('standard_deviation', style="max-width:7em"),
            ),
        )
        self.render_required_fields = True
