from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Field
from django.core.exceptions import ValidationError
from django.forms import HiddenInput, ModelChoiceField, ModelMultipleChoiceField, NumberInput, Widget
from django.forms.models import BaseInlineFormSet
from django.utils.safestring import mark_safe
from extra_views import InlineFormSetFactory

from bibliography.models import Source, SOURCE_TYPES
from distributions.models import TemporalDistribution
from utils.forms import SimpleForm, SimpleModelForm, ModalForm, ModalModelForm, ModalModelFormMixin

from .models import (Composition, Material, MaterialCategory, MaterialComponent, MaterialComponentGroup,
                     MaterialProperty, MaterialPropertyValue, Sample, SampleSeries, WeightShare)


class MaterialCategoryModelForm(SimpleModelForm):
    class Meta:
        model = MaterialCategory
        fields = ('name', 'description')


class MaterialCategoryModalModelForm(ModalModelFormMixin, MaterialCategoryModelForm):
    pass


class MaterialModelForm(SimpleModelForm):
    class Meta:
        model = Material
        fields = ('name', 'description', 'categories')


class MaterialModalModelForm(ModalModelFormMixin, MaterialModelForm):
    pass


class ComponentModelForm(SimpleModelForm):
    class Meta:
        model = MaterialComponent
        fields = ('name', 'description')


class ComponentModalModelForm(ModalModelFormMixin, ComponentModelForm):
    pass


class ComponentGroupModelForm(SimpleModelForm):
    class Meta:
        model = MaterialComponentGroup
        fields = ('name', 'description')


class ComponentGroupModalModelForm(ModalModelFormMixin, ComponentGroupModelForm):
    pass


class MaterialPropertyModelForm(SimpleModelForm):
    class Meta:
        model = MaterialProperty
        fields = ('name', 'unit', 'description')


class MaterialPropertyModalModelForm(ModalModelFormMixin, MaterialPropertyModelForm):
    pass


class MaterialPropertyValueModelForm(SimpleModelForm):
    class Meta:
        model = MaterialPropertyValue
        fields = ('property', 'average', 'standard_deviation')


class MaterialPropertyValueModalModelForm(ModalModelFormMixin, MaterialPropertyValueModelForm):
    pass


class SampleFilterFormHelper(FormHelper):
    form_tag = False
    include_media = False
    layout = Layout(
        'material',
        'timestep'
    )


class SampleFilterForm(SimpleForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = SampleFilterFormHelper()
        self.fields['material'].widget.attrs = {'data-theme': 'bootstrap4'}


class SampleSeriesModelForm(SimpleModelForm):
    class Meta:
        model = SampleSeries
        fields = ('name', 'material', 'publish', 'description', 'preview')
        labels = {'publish': 'featured'}


class SampleSeriesModalModelForm(ModalModelFormMixin, SampleSeriesModelForm):
    pass


class SampleSeriesAddTemporalDistributionModalModelForm(ModalModelForm):
    distribution = ModelChoiceField(queryset=TemporalDistribution.objects.all())

    class Meta:
        model = SampleSeries
        fields = ('distribution',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['distribution'].queryset = TemporalDistribution.objects.difference(
            self.instance.temporal_distributions.all())


class SampleModelForm(SimpleModelForm):
    sources = ModelMultipleChoiceField(
        queryset=Source.objects.filter(type__in=[t[0] for t in SOURCE_TYPES]).order_by('abbreviation'),
        required=False
    )

    class Meta:
        model = Sample
        fields = ('name', 'series', 'timestep', 'taken_at', 'description', 'preview', 'sources')

class SampleModalModelForm(ModalModelFormMixin, SampleModelForm):
    pass


class CompositionModelForm(SimpleModelForm):
    class Meta:
        model = Composition
        fields = ('group', 'sample', 'fractions_of')


class CompositionModalModelForm(ModalModelFormMixin, CompositionModelForm):
    pass


class AddCompositionModalForm(ModalModelForm):
    group = ModelChoiceField(queryset=MaterialComponentGroup.objects.all())
    fractions_of = ModelChoiceField(queryset=MaterialComponent.objects.all())

    class Meta:
        model = SampleSeries
        fields = ['group', 'fractions_of', ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['group'].queryset = MaterialComponentGroup.objects.exclude(id__in=self.instance.blocked_ids)
        self.fields['fractions_of'].queryset = self.instance.components
        self.fields['fractions_of'].empty_label = None


class AddComponentModalForm(ModalModelForm):
    component = ModelChoiceField(queryset=MaterialComponent.objects.all())

    class Meta:
        model = Composition
        fields = ('component',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['component'].queryset = MaterialComponent.objects.exclude(
            id__in=self.instance.blocked_component_ids
        )


class AddLiteratureSourceForm(ModalForm):
    source = ModelChoiceField(queryset=Source.objects.all())

    class Meta:
        fields = ('source',)


class AddSeasonalVariationForm(ModalForm):
    temporal_distribution = ModelChoiceField(queryset=TemporalDistribution.objects.all())

    class Meta:
        fields = ('temporal_distribution',)


class WeightShareModelForm(SimpleModelForm):
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


class WeightShareInlineForm(WeightShareModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.get('component').label = ' '
        self.fields.get('component').required = False


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
            'owner': HiddenInput(),
            'average': NumberInput(attrs={'min': 0, 'max': 100, 'step': 0.01}),
            'standard_deviation': NumberInput(attrs={'min': 0, 'max': 100, 'step': 0.01})
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


class PlainTextComponentWidget(Widget):
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
        'form': WeightShareInlineForm,
        'formset': WeightShareInlineFormset,
        'extra': 0,
        'can_delete': True,
        'widgets': {
            'component': PlainTextComponentWidget(),
            'average': NumberInput(attrs={'min': 0, 'max': 100, 'step': 0.01}),
            'standard_deviation': NumberInput(attrs={'min': 0, 'max': 100, 'step': 0.01})
        }
    }


class AddTemporalDistributionForm(ModalModelForm):
    class Meta:
        model = Composition
        fields = '__all__'


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
