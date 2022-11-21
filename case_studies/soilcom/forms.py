from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Field, Layout, Row, Submit
from dal import autocomplete
from django import forms
from django.forms import BaseFormSet, Form

from bibliography.models import Source
from utils.forms import CustomModelForm, CustomModalModelForm, ForeignkeyField
from materials.models import Material, MaterialCategory, Sample
from users.models import get_default_owner

from . import models
from .models import CollectionPropertyValue


class CollectorModelForm(CustomModelForm):
    catchment = forms.ModelChoiceField(
        queryset=models.Catchment.objects.all(),
        widget=autocomplete.ModelSelect2(url='catchment-autocomplete'),
        required=False
    )

    class Meta:
        model = models.Collector
        fields = ('name', 'website', 'catchment', 'description')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['catchment'].widget.attrs = {'data-theme': 'bootstrap4'}


class CollectorModalModelForm(CustomModalModelForm):
    catchment = forms.ModelChoiceField(
        queryset=models.Catchment.objects.all(),
        widget=autocomplete.ModelSelect2(url='catchment-autocomplete'),
        required=False
    )

    class Meta:
        model = models.Collector
        fields = ('name', 'website', 'catchment', 'description')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['catchment'].widget.attrs = {'data-theme': 'bootstrap4'}


class CollectorFilterFormHelper(FormHelper):
    form_tag = False
    include_media = False
    layout = Layout(
        'name',
        'catchment',
    )


class CollectorFilterForm(Form):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = CollectorFilterFormHelper()
        self.fields['name'].widget.attrs = {'data-theme': 'bootstrap4'}
        self.fields['catchment'].widget.attrs = {'data-theme': 'bootstrap4'}


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


class WasteFlyerModalModelForm(CustomModelForm):
    class Meta:
        model = Source
        fields = ('publisher', 'title', 'year', 'abbreviation', 'url', 'last_accessed',)
        labels = {'url': 'Sources'}


class UrlForm(forms.Form):
    url = forms.URLField(required=False)


class BaseWasteFlyerUrlFormSet(BaseFormSet):

    def __init__(self, *args, **kwargs):
        self.collection = kwargs.pop('parent_object', None)
        self.owner = kwargs.pop('owner', get_default_owner())
        flyers = self.collection.flyers.all() if self.collection else []
        initial = [{'url': flyer.url} for flyer in flyers]
        super().__init__(*args, initial=initial, **kwargs)

    def clean(self):
        if any(self.errors):
            return

    def save(self, commit=True):
        flyers = []
        for form in self.forms:
            if 'url' in form.cleaned_data and form.cleaned_data['url'] != '':
                flyer, _ = models.WasteFlyer.objects.get_or_create(owner=self.owner, url=form.cleaned_data['url'])
                flyers.append(flyer)
        self.collection.flyers.set(flyers)
        models.WasteFlyer.objects.filter(collections=None).delete()
        return flyers


class FormSetHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.template = 'bootstrap4/dynamic_table_inline_formset.html'
        self.form_method = 'post'
        self.add_input(Submit("submit", "Save"))


class CollectionPropertyValueModelForm(CustomModelForm):
    collection = forms.ModelChoiceField(
        queryset=models.Collection.objects.all(),
        widget=autocomplete.ModelSelect2(url='collection-autocomplete'),
        required=True
    )

    class Meta:
        model = CollectionPropertyValue
        fields = ('collection', 'property', 'year', 'average', 'standard_deviation')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['collection'].widget.attrs = {'data-theme': 'bootstrap4'}


class CollectionModelForm(forms.ModelForm):
    catchment = forms.ModelChoiceField(
        queryset=models.Catchment.objects.all(),
        widget=autocomplete.ModelSelect2(url='catchment-autocomplete'),
        required=True
    )
    collector = forms.ModelChoiceField(
        queryset=models.Collector.objects.all(),
        widget=autocomplete.ModelSelect2(url='collector-autocomplete'),
        required=True
    )
    collection_system = forms.ModelChoiceField(
        queryset=models.CollectionSystem.objects.all(),
        required=True)
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
                  'connection_rate', 'connection_rate_year', 'frequency', 'fee_system', 'description')
        labels = {
            'description': 'Comments',
            'connection_rate': 'Connection rate [%]',
            'connection_rate_year': 'Year'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['catchment'].widget.attrs = {'data-theme': 'bootstrap4'}
        self.fields['collector'].widget.attrs = {'data-theme': 'bootstrap4'}
        if 'connection_rate' in self.initial and self.initial['connection_rate'] is not None:
            self.initial['connection_rate'] *= 100

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
            Field('fee_system'),
            ForeignkeyField('frequency'),
            Field('description')
        )
        return helper

    def save(self, commit=True):
        instance = super().save(commit=False)

        data = self.cleaned_data

        # Create a name
        instance.name = f'{data["catchment"]} {data["waste_category"]} {data["collection_system"]}'

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
        'fee_system'
    )


COUNTRY_CHOICES = (
    ('BE', 'BE'),
    ('DE', 'DE'),
    ('DK', 'DK'),
    ('NL', 'NL'),
    ('UK', 'UK'),
    ('SE', 'SE'),
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
        fields = ('catchment', 'collector', 'collection_system', 'country', 'waste_category', 'allowed_materials',
                  'fee_system')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = CollectionFilterFormHelper()
        self.fields['catchment'].widget.attrs = {'data-theme': 'bootstrap4'}
        self.fields['collector'].widget.attrs = {'data-theme': 'bootstrap4'}
        # self.fields['country'].choices = set(
        #     sorted(set((c.catchment.region.country_code, c.catchment.region.country_code) for c in
        #                models.Collection.objects.all())))


class FlyerFilterFormHelper(FormHelper):
    form_tag = False
    include_media = False


class FlyerFilterForm(forms.Form):
    url_valid = forms.BooleanField(widget=forms.RadioSelect())

    class Meta:
        model = models.WasteFlyer
        fields = ('url_valid',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FlyerFilterFormHelper()


class CollectionAddWasteSampleFormHelper(FormHelper):
    form_tag = False
    include_media = False
    layout = Layout(
        Field('sample'),
        Submit('submit', 'Add')
    )


class CollectionAddWasteSampleForm(CustomModelForm):
    sample = forms.ModelChoiceField(queryset=Sample.objects.all(),
                                    widget=autocomplete.ModelSelect2(url='sample-autocomplete'))

    class Meta:
        model = Sample
        fields = ('sample',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['sample'].widget.attrs = {'data-theme': 'bootstrap4'}

    @property
    def helper(self):
        return CollectionAddWasteSampleFormHelper()


class CollectionRemoveWasteSampleForm(forms.ModelForm):
    sample = forms.ModelChoiceField(queryset=Sample.objects.all())

    class Meta:
        model = models.Collection
        fields = ('sample',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['sample'].queryset = Sample.objects.filter(collections=self.instance)
        self.helper = FormHelper()
        self.helper.add_input(Submit('submit', 'Remove'))
