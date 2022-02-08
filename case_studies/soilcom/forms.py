import datetime

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Field, Layout, Submit
from django import forms
from django.contrib.auth.models import User

from bibliography.models import Source
from brit.forms import CustomModelForm, CustomModalModelForm
from maps.models import Region
from materials.models import Material, MaterialGroup
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
    url = forms.URLField(max_length=511, widget=forms.URLInput)

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
    collection_system = forms.ModelChoiceField(queryset=models.CollectionSystem.objects.all(), required=True)
    catchment = forms.ModelChoiceField(queryset=models.Catchment.objects.all().order_by('region__nutsregion__nuts_id'))
    waste_category = forms.ModelChoiceField(queryset=models.WasteCategory.objects.all())
    allowed_materials = forms.ModelMultipleChoiceField(queryset=models.WasteComponent.objects.all(),
                                                       widget=forms.CheckboxSelectMultiple)
    flyer_url = forms.URLField(required=False)

    class Meta:
        model = models.Collection
        fields = (
            'catchment', 'collector', 'collection_system', 'waste_category', 'allowed_materials', 'flyer_url',
            'description'
        )
        labels = {
            'description': 'Comments'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        initial = kwargs.get('initial', {})
        if 'catchment' in initial:
            self.fields['catchment'].queryset = models.Catchment.objects.filter(id=initial['catchment'].id)

    @property
    def helper(self):
        helper = FormHelper()
        helper.layout = Layout(
            Field('catchment'),
            ForeignkeyField('collector'),
            Field('collection_system'),
            Field('waste_category'),
            Field('allowed_materials'),
            Field('flyer_url'),
            Field('description')
        )
        helper.add_input(Submit('submit', 'Save'))
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
        waste_stream.allowed_materials.add(*data['allowed_materials'])
        waste_stream.save()
        instance.waste_stream = waste_stream

        # Associate with a new or existing waste collection source flyer
        if data['flyer_url']:
            region_id = None
            try:
                region_id = data["catchment"].region.nutsregion.nuts_id
            except AttributeError:
                pass
            except Region.nutsregion.RelatedObjectDoesNotExist:
                pass
            try:
                region_id = data["catchment"].region.lauregion.lau_id
            except AttributeError:
                pass
            except Region.lauregion.RelatedObjectDoesNotExist:
                pass
            flyer, created = models.WasteFlyer.objects.get_or_create(
                type='waste_flyer',
                url=data['flyer_url'],
                defaults={
                    'owner': instance.owner,
                    'title': f'Waste flyer {data["catchment"]}',
                    'abbreviation': f'WasteFlyer{region_id}',
                }
            )
            instance.flyer = flyer

        if commit:
            instance.save()
        return instance


class CollectionModalModelForm(CustomModalModelForm):
    class Meta:
        model = models.Collection
        fields = ('name', 'collector', 'catchment', 'collection_system', 'waste_stream', 'flyer', 'description')


COUNTRY_SET = set(sorted(set((c.catchment.region.country_code, c.catchment.region.country_code) for c in
                             models.Collection.objects.all())))


class CollectionFilterForm(forms.Form):
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
        choices=COUNTRY_SET,
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    allowed_materials = forms.ModelMultipleChoiceField(
        queryset=models.WasteComponent.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    last_editor = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(
            id__in=[i[0] for i in models.Collection.objects.values_list('lastmodified_by').distinct()]),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    