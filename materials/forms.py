from decimal import Decimal, ROUND_HALF_UP

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Field, Layout, Row
from dal import autocomplete
from django.core.exceptions import ValidationError
from django.forms import DateTimeInput, DecimalField, HiddenInput, ModelChoiceField, NumberInput, Widget
from django.forms.models import BaseInlineFormSet
from django.utils.safestring import mark_safe
from extra_views import InlineFormSetFactory

from bibliography.models import Source
from distributions.models import TemporalDistribution
from utils.forms import AutoCompleteModelForm, ModalForm, ModalModelForm, ModalModelFormMixin, SimpleModelForm
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


class SampleModelForm(AutoCompleteModelForm):
    class Meta:
        model = Sample
        fields = ('name', 'series', 'timestep', 'taken_at', 'description', 'preview', 'sources')
        widgets = {
            'series': autocomplete.ModelSelect2(url='sampleseries-autocomplete'),
            'taken_at': DateTimeInput(attrs={'type': 'datetime-local'}),
            'sources': autocomplete.ModelSelect2Multiple(url='source-autocomplete'),
        }
        labels = {
            'taken_at': 'Date/Time',
            'preview': 'Image',
        }


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


class PercentageDecimalField(DecimalField):
    def to_python(self, value):
        """
        Convert the input percentage value to a decimal before validation.
        """
        value = super().to_python(value)
        if value is not None:
            return (value / Decimal('100')).quantize(Decimal('.0000000001'), rounding=ROUND_HALF_UP)
        return value

    def prepare_value(self, value):
        """
        Convert the decimal value to a percentage string with at least one decimal place
        for display in the form.
        """
        if isinstance(value, Decimal):
            percentage = value * Decimal('100')
            percentage = percentage.quantize(Decimal('.0000000001'), rounding=ROUND_HALF_UP)
            percentage_str = format(percentage, 'f')  # Fixed-point format

            if '.' in percentage_str:
                # Remove trailing zeros but ensure at least one decimal digit
                percentage_str = percentage_str.rstrip('0').rstrip('.')
                if '.' not in percentage_str:
                    # If all decimals were stripped, add '.0'
                    percentage_str += '.0'
            else:
                # No decimal point, add '.0'
                percentage_str += '.0'

            return percentage_str
        return value


class PercentageInput(NumberInput):
    def __init__(self, attrs=None):
        if attrs is None:
            attrs = {}
        attrs.update({'class': 'percentage-input'})
        super().__init__(attrs)

    def render(self, name, value, attrs=None, renderer=None):
        attrs = attrs or {}
        attrs['step'] = 'any'
        input_html = super().render(name, value, attrs, renderer)
        return mark_safe(input_html)


class WeightShareModelForm(SimpleModelForm):
    average = PercentageDecimalField(
        label='Average (%)',
        min_value=0,
        max_value=100,
        required=True,
        widget=PercentageInput(),
        error_messages={
            'min_value': 'Average must be at least 0%.',
            'max_value': 'Average cannot exceed 100%.',
            'invalid': 'Enter a valid percentage.',
        }
    )
    standard_deviation = PercentageDecimalField(
        label='Standard Deviation (%)',
        min_value=0,
        max_value=100,
        required=True,
        widget=PercentageInput(),
        error_messages={
            'min_value': 'Standard deviation must be at least 0%.',
            'max_value': 'Standard deviation cannot exceed 100%.',
            'invalid': 'Enter a valid percentage.',
        }
    )

    class Meta:
        model = WeightShare
        fields = ('component', 'average', 'standard_deviation',)


class WeightShareInlineForm(WeightShareModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.get('component').label = ' '
        self.fields.get('component').required = False


class WeightShareInlineFormset(BaseInlineFormSet):

    def clean(self):
        super().clean()

        if any(self.errors):
            # If any form has errors, skip further validation
            return

        total_average = Decimal('0.0')
        for form in self.forms:
            if self.can_delete and form.cleaned_data.get('DELETE'):
                continue
            average = form.cleaned_data.get('average')
            if average is None:
                continue  # Or handle as needed
            total_average += average

        # Define a tolerance for decimal comparison
        tolerance = Decimal('0.0000001')
        if not (Decimal('1.0') - tolerance <= total_average <= Decimal('1.0') + tolerance):
            raise ValidationError('Weight shares of components must sum up to 100%.')


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
