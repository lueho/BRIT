from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Field, Layout, Row, Submit
from dal import autocomplete
from django import forms
from django.forms import BaseModelFormSet
from extra_views import InlineFormSetFactory

from bibliography.models import Source
from brit.forms import CustomModelForm, CustomModalModelForm
from materials.models import Material, MaterialCategory
from . import models


class CollectorModelForm(CustomModelForm):
    class Meta:
        model = models.Collector
        fields = ('name', 'website', 'description')


class CollectorModalModelForm(CustomModalModelForm):
    class Meta:
        model = models.Collector
        fields = ('name', 'website', 'description')


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
        categories = MaterialCategory.objects.filter(name='Biowaste component')
        self.fields['allowed_materials'].queryset = Material.objects.filter(categories__in=categories)

    class Meta:
        model = models.WasteStream
        fields = ('name', 'category', 'allowed_materials', 'composition', 'description')


class WasteStreamModalModelForm(CustomModalModelForm):
    class Meta:
        model = models.WasteStream
        fields = ('name', 'category', 'allowed_materials', 'composition', 'description')


class CollectionFrequencyModelForm(CustomModelForm):
    class Meta:
        model = models.CollectionFrequency
        fields = ('name', 'description')


class CollectionFrequencyModalModelForm(CustomModalModelForm):
    class Meta:
        model = models.CollectionFrequency
        fields = ('name', 'description')


class WasteFlyerModelForm(CustomModelForm):
    class Meta:
        model = models.WasteFlyer
        fields = ('url',)
        labels = {'url': 'Sources (Urls)'}

    def save(self, commit=True):
        if commit:
            defaults = {
                'owner': self.instance.owner,
                'title': 'Waste flyer',
                'abbreviation': 'WasteFlyer'
            }
            instance, _ = models.WasteFlyer.objects.get_or_create(url=self.cleaned_data['url'], defaults=defaults)
            return instance
        else:
            return super().save(commit=False)


class WasteFlyerModelFormSet(BaseModelFormSet):
    parent_object = None

    def __init__(self, **kwargs):
        self.parent_object = kwargs.pop('parent_object', None)
        super().__init__(**kwargs)

    def clean(self):
        if any(self.errors):
            return
        for form in self.forms:
            if not form.cleaned_data.get('url') and form.cleaned_data.get('id'):
                flyer = form.cleaned_data.get('id')
                if self.parent_object:
                    self.parent_object.flyers.remove(flyer)
                if not flyer.collections.exists():
                    form.cleaned_data.get('id').delete()
                self.forms.remove(form)


class WasteFlyerModalModelForm(CustomModelForm):
    class Meta:
        model = Source
        fields = ('publisher', 'title', 'year', 'abbreviation', 'url', 'last_accessed',)
        labels = {'url': 'Sources'}


class FormSetHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.template = 'bootstrap4/dynamic_table_inline_formset.html'
        self.form_method = 'post'
        self.add_input(Submit("submit", "Save"))


class InlineWasteFlyerFormset(InlineFormSetFactory):
    model = models.WasteFlyer
    fields = ('url',)

    factory_kwargs = {
        'extra': 1,
        'can_delete': True,
    }


class ForeignkeyField(Field):
    template = 'foreignkey-field.html'


class CollectionModelForm(forms.ModelForm):
    collection_system = forms.ModelChoiceField(
        queryset=models.CollectionSystem.objects.all(),
        required=True)
    catchment = forms.ModelChoiceField(
        queryset=models.Catchment.objects.all().order_by('region__nutsregion__nuts_id'),
        widget=autocomplete.ModelSelect2(url='catchment-autocomplete'),
        required=True
    )
    waste_category = forms.ModelChoiceField(
        queryset=models.WasteCategory.objects.all()
    )
    allowed_materials = forms.ModelMultipleChoiceField(
        queryset=models.WasteComponent.objects.all(),
        widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = models.Collection
        fields = ('catchment', 'collector', 'collection_system', 'waste_category', 'allowed_materials',
                  'connection_rate', 'connection_rate_year', 'frequency', 'description')
        labels = {
            'description': 'Comments',
            'connection_rate': 'Connection rate [%]',
            'connection_rate_year': 'Year'
        }
        widgets = {
            'collector': autocomplete.ModelSelect2(url='collector-autocomplete')
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['collector'].widget.attrs = {'data-theme': 'bootstrap4'}
        self.fields['catchment'].widget.attrs = {'data-theme': 'bootstrap4'}
        initial = kwargs.get('initial', {})
        if 'catchment' in initial:
            self.fields['catchment'].queryset = models.Catchment.objects.filter(id=initial['catchment'].id)

    def clean_connection_rate(self):
        connection_rate = self.cleaned_data.get('connection_rate')
        if connection_rate:
            connection_rate /= 100
        return connection_rate

    @property
    def helper(self):
        helper = FormHelper()
        helper.form_tag = False
        # django-crispy-forms and django-autocomplete-light conflict in the order JQuery needs to be loaded.
        # Suppressing media inclusion here and explicitly adding {{ form.media }} in the template solves this.
        # See https://github.com/yourlabs/django-autocomplete-light/issues/788
        helper.include_media = False
        helper.layout = Layout(
            Field('catchment'),
            ForeignkeyField('collector'),
            ForeignkeyField('collection_system'),
            ForeignkeyField('waste_category'),
            Field('allowed_materials'),
            Row(
                Column(Field('connection_rate')),
                Column(Field('connection_rate_year'))
            ),
            ForeignkeyField('frequency'),
            Field('description')
        )
        return helper

    def save(self, commit=True):
        instance = super().save(commit=False)

        data = self.cleaned_data

        # Create a name
        name = f'{data["catchment"]} {data["waste_category"]} {data["collection_system"]}'
        instance.name = name

        # Associate with a new or existing waste stream
        waste_stream, created = models.WasteStream.objects.get_or_create(
            defaults={'owner': instance.owner},
            category=data["waste_category"],
            allowed_materials=models.WasteComponent.objects.filter(id__in=data['allowed_materials'])
        )
        if created:
            waste_stream.allowed_materials.add(*data['allowed_materials'])
        waste_stream.save()
        instance.waste_stream = waste_stream

        if commit:
            return super().save()
        else:
            return super().save(commit=False)


class CollectionFilterForm2(forms.Form):
    collection_system = forms.ModelMultipleChoiceField(
        queryset=models.CollectionSystem.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    waste_category = forms.ModelMultipleChoiceField(
        queryset=models.WasteCategory.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    countries = forms.MultipleChoiceField(
        choices=set(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    allowed_materials = forms.ModelMultipleChoiceField(
        queryset=models.WasteComponent.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['countries'].choices = set(
            sorted(set((c.catchment.region.country_code, c.catchment.region.country_code) for c in
                       models.Collection.objects.all())))


class CollectionFilterFormHelper(FormHelper):
    form_tag = False
    include_media = False
    layout = Layout(
        'catchment',
        'collector',
        'collection_system',
        'country',
        'waste_category',
        'allowed_materials',
    )


COUNTRY_CHOICES = (
    ('BE', 'BE'),
    ('DE', 'DE'),
    ('DK', 'DK'),
    ('NL', 'NL'),
    ('UK', 'UK'),
)


class CollectionFilterForm(forms.Form):
    catchment = forms.ModelChoiceField(
        queryset=models.Catchment.objects.all(),
        widget=autocomplete.ModelSelect2(url='catchment-autocomplete'),
        required=False
    )
    collector = forms.ModelChoiceField(
        queryset=models.Collector.objects.all(),
        widget=autocomplete.ModelSelect2(url='collector-autocomplete'),
        required=False
    )
    waste_category = forms.ModelMultipleChoiceField(
        queryset=models.WasteCategory.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    country = forms.MultipleChoiceField(
        choices=COUNTRY_CHOICES,
        required=False
    )
    allowed_materials = forms.ModelMultipleChoiceField(
        queryset=models.WasteComponent.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = models.Collection
        fields = ('catchment', 'collector', 'collection_system', 'country', 'waste_category', 'allowed_materials')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = CollectionFilterFormHelper()
        self.fields['catchment'].widget.attrs = {'data-theme': 'bootstrap4'}
        self.fields['collector'].widget.attrs = {'data-theme': 'bootstrap4'}
        # self.fields['country'].choices = set(
        #     sorted(set((c.catchment.region.country_code, c.catchment.region.country_code) for c in
        #                models.Collection.objects.all())))
