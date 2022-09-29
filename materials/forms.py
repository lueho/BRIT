from bootstrap_modal_forms.forms import BSModalModelForm, BSModalForm
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Field
from django import forms
from django.forms import Form, ModelChoiceField, ModelMultipleChoiceField
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from django.utils.safestring import mark_safe
from extra_views import InlineFormSetFactory

from bibliography.models import Source, SOURCE_TYPES
from brit.forms import CustomModelForm, CustomModalModelForm, ModalFormHelper
from distributions.models import TemporalDistribution
from .models import (
    Material,
    MaterialComponent,
    MaterialComponentGroup,
    Composition,
    WeightShare,
    MaterialCategory,
    SampleSeries, MaterialProperty,
    Sample, MaterialPropertyValue
)


class MaterialCategoryModelForm(CustomModelForm):
    class Meta:
        model = MaterialCategory
        fields = ('name', 'description')


class MaterialCategoryModalModelForm(CustomModalModelForm):
    class Meta:
        model = MaterialCategory
        fields = ('name', 'description')


class MaterialModelForm(CustomModelForm):
    class Meta:
        model = Material
        fields = ('name', 'description', 'categories')


class MaterialModalModelForm(CustomModalModelForm):
    class Meta:
        model = Material
        fields = ('name', 'description', 'categories')


class ComponentModelForm(CustomModelForm):
    class Meta:
        model = MaterialComponent
        fields = ('name', 'description')


class ComponentModalModelForm(CustomModalModelForm):
    class Meta:
        model = MaterialComponent
        fields = ('name', 'description',)


class ComponentGroupModelForm(CustomModelForm):
    class Meta:
        model = MaterialComponentGroup
        fields = ('name', 'description')


class ComponentGroupModalModelForm(CustomModalModelForm):
    class Meta:
        model = MaterialComponentGroup
        fields = ('name', 'description',)


class MaterialPropertyModelForm(CustomModelForm):
    class Meta:
        model = MaterialProperty
        fields = ('name', 'unit', 'description')


class MaterialPropertyModalModelForm(CustomModalModelForm):
    class Meta:
        model = MaterialProperty
        fields = ('name', 'unit', 'description',)


class MaterialPropertyValueModelForm(CustomModelForm):
    class Meta:
        model = MaterialPropertyValue
        fields = ('property', 'average', 'standard_deviation')


class MaterialPropertyValueModalModelForm(CustomModalModelForm):
    class Meta:
        model = MaterialPropertyValue
        fields = ('property', 'average', 'standard_deviation',)


class SampleFilterFormHelper(FormHelper):
    form_tag = False
    include_media = False
    layout = Layout(
        'material',
        'timestep'
    )

class SampleFilterForm(Form):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = SampleFilterFormHelper()
        self.fields['material'].widget.attrs = {'data-theme': 'bootstrap4'}


class SampleSeriesModelForm(CustomModelForm):
    class Meta:
        model = SampleSeries
        fields = ('name', 'material', 'publish', 'description', 'preview')
        labels = {'publish': 'featured'}


class SampleSeriesModalModelForm(CustomModalModelForm):
    class Meta:
        model = SampleSeries
        fields = ('name', 'material', 'publish', 'description', 'preview')
        labels = {'publish': 'featured'}


class SampleSeriesAddTemporalDistributionModalModelForm(CustomModalModelForm):
    distribution = ModelChoiceField(queryset=TemporalDistribution.objects.all())

    class Meta:
        model = SampleSeries
        fields = ('distribution',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['distribution'].queryset = TemporalDistribution.objects.difference(self.instance.temporal_distributions.all())


class SampleModelForm(CustomModelForm):
    class Meta:
        model = Sample
        fields = ('name', 'series', 'timestep', 'taken_at', 'description', 'preview')


class SampleModalModelForm(CustomModalModelForm):
    sources = ModelMultipleChoiceField(
        queryset=Source.objects.filter(type__in=[t[0] for t in SOURCE_TYPES]).order_by('abbreviation'),
        required=False
    )
    class Meta:
        model = Sample
        fields = ('name', 'series', 'timestep', 'taken_at', 'description', 'preview', 'sources')


class CompositionModelForm(CustomModelForm):
    class Meta:
        model = Composition
        fields = ('group', 'sample', 'fractions_of')


class CompositionModalModelForm(CustomModalModelForm):
    class Meta:
        model = Composition
        fields = ('group', 'sample', 'fractions_of')


class AddCompositionModalForm(BSModalModelForm):
    group = forms.ModelChoiceField(queryset=MaterialComponentGroup.objects.all())
    fractions_of = forms.ModelChoiceField(queryset=MaterialComponent.objects.all())

    class Meta:
        model = SampleSeries
        fields = ['group', 'fractions_of', ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['group'].queryset = MaterialComponentGroup.objects.exclude(id__in=self.instance.blocked_ids)
        self.fields['fractions_of'].queryset = self.instance.components
        self.fields['fractions_of'].empty_label = None
        self.helper = ModalFormHelper()


class AddComponentModalForm(BSModalModelForm):
    component = forms.ModelChoiceField(queryset=MaterialComponent.objects.all())

    class Meta:
        model = Composition
        fields = ('component',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['component'].queryset = MaterialComponent.objects.exclude(
            id__in=self.instance.blocked_component_ids
        )
        self.helper = ModalFormHelper()


class AddLiteratureSourceForm(BSModalForm):
    source = forms.ModelChoiceField(queryset=Source.objects.all())

    class Meta:
        fields = ('source',)


class AddSeasonalVariationForm(BSModalForm):
    temporal_distribution = forms.ModelChoiceField(queryset=TemporalDistribution.objects.all())

    class Meta:
        fields = ('temporal_distribution',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = ModalFormHelper()


class WeightShareModelForm(CustomModelForm):
    class Meta:
        model = WeightShare
        fields = ('component', 'average', 'standard_deviation',)

    def __init__(self, *args, **kwargs):
        if 'instance' in kwargs:
            instance = kwargs.get('instance')
            instance.average *= 100
            instance.standard_deviation *= 100
        super().__init__(*args, **kwargs)

    def clean_average(self):
        return self.cleaned_data.get('average') / 100

    def clean_standard_deviation(self):
        return self.cleaned_data.get('standard_deviation') / 100


class WeightShareInlineFormset(BaseInlineFormSet):

    def clean(self):
        if any(self.errors):
            return
        if self.forms and not all([form.cleaned_data['DELETE'] for form in self.forms]):
            summe = sum([form.cleaned_data.get('average') for form in self.forms if not form.cleaned_data['DELETE']])
            if summe != 1.0:
                raise ValidationError('Weight shares of components must sum up to 100%')
        super().clean()


class InlineWeightShare(InlineFormSetFactory):
    model = WeightShare
    fields = ('owner', 'component', 'average', 'standard_deviation')
    factory_kwargs = {
        'form': WeightShareModelForm,
        'formset': WeightShareInlineFormset,
        'extra': 0,
        'can_delete': True,
        'widgets': {
            'owner': forms.HiddenInput(),
            'average': forms.NumberInput(attrs={'min': 0, 'max': 100, 'step': 0.01}),
            'standard_deviation': forms.NumberInput(attrs={'min': 0, 'max': 100, 'step': 0.01})
        }
    }

    def get_formset_kwargs(self):
        kwargs = super().get_formset_kwargs()
        kwargs['form_kwargs'] = {'initial': {'owner': self.request.user}}
        return kwargs


class WeightShareUpdateFormSetHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.template = 'bootstrap4/dynamic_table_inline_formset.html'
        self.form_method = 'post'
        self.layout = Layout(
            Row(
                Field('component'),
                Field('average'),
                Field('standard_deviation'),
            ),
        )
        self.render_required_fields = True


class WeightShareModalModelForm(WeightShareModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.get('component').label = ' '
        self.fields.get('component').required = False


class PlainTextComponentWidget(forms.Widget):
    def render(self, name, value, attrs=None, renderer=None):
        if hasattr(self, 'initial'):
            value = self.initial
        try:
            object_name = MaterialComponent.objects.get(id=value).name
        except MaterialComponent.DoesNotExist:
            object_name = '-'

        return mark_safe("<div style=\"min-width: 7em; padding-right: 12px;\"><b>" + (str(
            object_name) if value is not None else '-') + "</b></div>" + f"<input type='hidden' name='{name}' value='{value}'>")

        # return mark_safe("<b>" + (str(object_name) if value is not None else '-') + "</b>" +
        #                  f"<input type='hidden' name='{name}' value='{value}'>")


class ModalInlineComponentShare(InlineFormSetFactory):
    model = WeightShare
    fields = ('component', 'average', 'standard_deviation')
    factory_kwargs = {
        'form': WeightShareModalModelForm,
        'formset': WeightShareInlineFormset,
        'extra': 0,
        'can_delete': True,
        'widgets': {
            'component': PlainTextComponentWidget(),
            'average': forms.NumberInput(attrs={'min': 0, 'max': 100, 'step': 0.01}),
            'standard_deviation': forms.NumberInput(attrs={'min': 0, 'max': 100, 'step': 0.01})
        }
    }


class AddTemporalDistributionForm(BSModalModelForm):
    class Meta:
        model = Composition
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()


class ComponentShareDistributionFormSetHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.template = 'bootstrap4/dynamic_table_inline_formset.html'
        self.form_method = 'post'
        self.layout = Layout(
            Row(
                Field('component'),
                Field('average', style="max-width:7em"),
                Field('standard_deviation', style="max-width:7em"),
            ),
        )
        self.render_required_fields = True
