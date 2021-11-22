import datetime

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Field, Layout, Submit
from django import forms

from bibliography.models import Source
from brit.forms import CustomModelForm, CustomModalModelForm
from maps.models import NutsRegion
from materials.models import Material, MaterialGroup
from . import models


class CollectorModelForm(CustomModelForm):
    class Meta:
        model = models.Collector
        fields = ('name', 'description')


class CollectorModalModelForm(CustomModalModelForm):
    class Meta:
        model = models.Collector
        fields = ('name', 'description')


class CollectionSystemModelForm(CustomModelForm):
    class Meta:
        model = models.CollectionSystem
        fields = ('name', 'description')


class CollectionSystemModalModelForm(CustomModalModelForm):
    class Meta:
        model = models.CollectionSystem
        fields = ('name', 'description')


class WasteCategoryModelForm(CustomModelForm):
    class Meta:
        model = models.WasteCategory
        fields = ('name', 'description')


class WasteCategoryModalModelForm(CustomModalModelForm):
    class Meta:
        model = models.WasteCategory
        fields = ('name', 'description')


class WasteComponentModelForm(CustomModelForm):
    class Meta:
        model = models.WasteComponent
        fields = ('name', 'description')


class WasteComponentModalModelForm(CustomModalModelForm):
    class Meta:
        model = models.WasteComponent
        fields = ('name', 'description')


class WasteStreamModelForm(CustomModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        groups = MaterialGroup.objects.filter(name='Biowaste component')
        self.fields['allowed_materials'].queryset = Material.objects.filter(groups__in=groups)

    class Meta:
        model = models.WasteStream
        fields = ('name', 'category', 'allowed_materials', 'composition', 'description')


class WasteStreamModalModelForm(CustomModalModelForm):
    class Meta:
        model = models.WasteStream
        fields = ('name', 'category', 'allowed_materials', 'composition', 'description')


class WasteFlyerModelForm(CustomModelForm):
    last_accessed = forms.DateField(initial=datetime.date.today)

    class Meta:
        model = Source
        fields = ('publisher', 'title', 'year', 'abbreviation', 'url', 'last_accessed',)


class WasteFlyerModalModelForm(CustomModelForm):
    class Meta:
        model = Source
        fields = ('publisher', 'title', 'year', 'abbreviation', 'url', 'last_accessed',)


class ForeignkeyField(Field):
    template = 'foreignkey-field.html'


class CollectionModelForm(forms.ModelForm):
    # TODO: Can the RelatedFieldWidgetWrapper be used for this:
    # collector = forms.ModelChoiceField(queryset=models.Collector.objects.all(), widget=RelatedFieldWidgetWrapper)

    class Meta:
        model = models.Collection
        fields = ('name', 'collector', 'catchment', 'collection_system', 'waste_stream', 'flyer', 'description')

    @property
    def helper(self):
        helper = FormHelper()
        helper.layout = Layout()
        for field_name, field in self.fields.items():
            if isinstance(field, forms.ModelChoiceField):
                helper.layout.append(ForeignkeyField(field_name))
            else:
                helper.layout.append(Field(field_name))
        helper.add_input(Submit('submit', 'Save'))
        return helper


class CollectionModalModelForm(CustomModalModelForm):
    class Meta:
        model = models.Collection
        fields = ('name', 'collector', 'catchment', 'collection_system', 'waste_stream', 'flyer', 'description')


class CollectionFilterForm(forms.Form):
    collection_system = forms.ModelMultipleChoiceField(queryset=models.CollectionSystem.objects.all())
    waste_category = forms.ModelMultipleChoiceField(queryset=models.WasteCategory.objects.all())
    countries = forms.MultipleChoiceField(
        choices=NutsRegion.objects.values_list('cntr_code', 'cntr_code').distinct().order_by('cntr_code'))
    allowed_materials = forms.ModelMultipleChoiceField(queryset=models.WasteComponent.objects.all())
