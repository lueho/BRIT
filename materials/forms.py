from bootstrap_modal_forms.forms import BSModalModelForm, BSModalForm
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Field
from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from django.utils.safestring import mark_safe
from extra_views import InlineFormSetFactory

from bibliography.models import Source
from distributions.models import TemporalDistribution
from .models import (
    Material,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialComponentGroupSettings,
    MaterialComponentShare,
    MaterialGroup,
)

from brit.forms import CustomModelForm, CustomModalModelForm, ModalFormHelper


class MaterialGroupModelForm(CustomModelForm):
    class Meta:
        model = MaterialGroup
        fields = ('name', 'description')


class MaterialGroupModalModelForm(CustomModalModelForm):
    class Meta:
        model = MaterialGroup
        fields = ('name', 'description')


class MaterialModelForm(CustomModelForm):
    class Meta:
        model = Material
        fields = ('name', 'description', 'groups')


class MaterialModalModelForm(CustomModalModelForm):
    class Meta:
        model = Material
        fields = ('name', 'description', 'groups')


class ComponentModelForm(BSModalModelForm):
    class Meta:
        model = MaterialComponent
        fields = ('name', 'description',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = ModalFormHelper()


class AddComponentForm(BSModalForm):
    component = forms.ModelChoiceField(queryset=MaterialComponent.objects.all())

    class Meta:
        fields = ('component',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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


class ComponentGroupModelForm(BSModalModelForm):
    class Meta:
        model = MaterialComponentGroup
        fields = ('name', 'description',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = ModalFormHelper()


class AddComponentGroupForm(BSModalForm):
    group = forms.ModelChoiceField(queryset=MaterialComponentGroup.objects.all())
    fractions_of = forms.ModelChoiceField(queryset=MaterialComponent.objects.all())

    class Meta:
        fields = ['group', 'fractions_of', ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = ModalFormHelper()


class ComponentShareUpdateForm(BSModalModelForm):
    class Meta:
        model = MaterialComponentShare
        fields = ('average', 'standard_deviation')
        widgets = {
            'average': forms.NumberInput(attrs={'min': 0, 'max': 1.0, 'step': 0.01}),
            'standard_deviation': forms.NumberInput(attrs={'min': 0, 'max': 1.0, 'step': 0.01})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = ModalFormHelper()


class CompositionUpdateForm(BSModalModelForm):
    class Meta:
        model = MaterialComponentShare
        fields = ('component', 'average', 'standard_deviation')
        widgets = {
            'average': forms.NumberInput(attrs={'min': 0, 'max': 1.0, 'step': 0.01}),
            'standard_deviation': forms.NumberInput(attrs={'min': 0, 'max': 1.0, 'step': 0.01})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = ModalFormHelper()


class ItemForm(BSModalModelForm):
    class Meta:
        model = MaterialComponentShare
        fields = ('component', 'average', 'standard_deviation')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()


class BaseCompositionFormSet(BaseInlineFormSet):
    def clean(self):
        """Checks that the sum of all weight fractions is 1."""
        if any(self.errors):
            return
        if sum([form.cleaned_data.get('average') for form in self.forms]) != 1.0:
            raise ValidationError("The weight fractions must sum up to 1.")


class PlainTextComponentWidget(forms.Widget):
    def render(self, name, value, attrs=None, renderer=None):
        if hasattr(self, 'initial'):
            value = self.initial
        object_name = MaterialComponent.objects.get(id=value).name

        return mark_safe("<div style=\"min-width: 7em; padding-right: 12px;\">" + (str(
            object_name) if value is not None else '-') + "</div>" + f"<input type='hidden' name='{name}' value='{value}'>")


class InlineComponentShare(InlineFormSetFactory):
    model = MaterialComponentShare
    fields = ('component', 'average', 'standard_deviation')
    factory_kwargs = {
        'formset': BaseCompositionFormSet,
        'extra': 0,
        'can_delete': False,
        'widgets': {
            'component': PlainTextComponentWidget(),
            'average': forms.NumberInput(attrs={'min': 0, 'max': 1.0, 'step': 0.01}),
            'standard_deviation': forms.NumberInput(attrs={'min': 0, 'max': 1.0, 'step': 0.01})
        }
    }


class AddTemporalDistributionForm(BSModalModelForm):
    class Meta:
        model = MaterialComponentGroupSettings
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()


class ComponentShareDistributionFormSetHelper(FormHelper):
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
