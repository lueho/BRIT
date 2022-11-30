from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Field, Layout, Row
from dal import autocomplete
from django.forms import (BaseFormSet, BooleanField, ChoiceField, CheckboxSelectMultiple, ModelChoiceField,
                          ModelMultipleChoiceField, MultipleChoiceField, RadioSelect, URLField)

from materials.models import Material, MaterialCategory, Sample
from users.models import get_default_owner
from utils.forms import (AutoCompleteModelForm, ForeignkeyField, SimpleForm, SimpleModelForm,
                         ModalModelFormMixin)
from .models import (AggregatedCollectionPropertyValue, Collection, CollectionCatchment, CollectionFrequency,
                     CollectionPropertyValue, CollectionSystem, Collector, FREQUENCY_TYPES, WasteCategory,
                     WasteComponent, WasteFlyer, WasteStream)


class CollectorModelForm(AutoCompleteModelForm):
    catchment = ModelChoiceField(
        queryset=CollectionCatchment.objects.all(),
        widget=autocomplete.ModelSelect2(url='catchment-autocomplete'),
        required=False
    )

    class Meta:
        model = Collector
        fields = ('name', 'website', 'catchment', 'description')


class CollectorModalModelForm(ModalModelFormMixin, CollectorModelForm):
    pass


class CollectionSystemModelForm(SimpleModelForm):
    class Meta:
        model = CollectionSystem
        fields = ('name', 'description')


class CollectionSystemModalModelForm(ModalModelFormMixin, CollectionSystemModelForm):
    pass


class WasteCategoryModelForm(SimpleModelForm):
    class Meta:
        model = WasteCategory
        fields = ('name', 'description')


class WasteCategoryModalModelForm(ModalModelFormMixin, WasteCategoryModelForm):
    pass


class WasteComponentModelForm(SimpleModelForm):
    class Meta:
        model = WasteComponent
        fields = ('name', 'description')


class WasteComponentModalModelForm(ModalModelFormMixin, WasteComponentModelForm):
    pass


class WasteStreamModelForm(SimpleModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        categories = MaterialCategory.objects.filter(name='Biowaste component')
        self.fields['allowed_materials'].queryset = Material.objects.filter(categories__in=categories)

    class Meta:
        model = WasteStream
        fields = ('name', 'category', 'allowed_materials', 'composition', 'description')


class WasteStreamModalModelForm(ModalModelFormMixin, WasteStreamModelForm):
    pass


class CollectionFrequencyModelForm(SimpleModelForm):
    class Meta:
        model = CollectionFrequency
        fields = ('name', 'type', 'description')


class CollectionFrequencyModalModelForm(ModalModelFormMixin, CollectionFrequencyModelForm):
    pass


class WasteFlyerModelForm(SimpleModelForm):
    class Meta:
        model = WasteFlyer
        fields = ('url',)
        labels = {'url': 'Sources (Urls)'}

    def save(self, commit=True):
        if commit:
            defaults = {
                'owner': self.instance.owner,
                'title': 'Waste flyer',
                'abbreviation': 'WasteFlyer'
            }
            instance, _ = WasteFlyer.objects.get_or_create(url=self.cleaned_data['url'], defaults=defaults)
            return instance
        else:
            return super().save(commit=False)


class WasteFlyerModalModelForm(ModalModelFormMixin, WasteFlyerModelForm):
    pass


class BaseWasteFlyerUrlFormSet(BaseFormSet):

    def __init__(self, *args, **kwargs):
        self.parent_object = kwargs.pop('parent_object', None)
        self.owner = kwargs.pop('owner', get_default_owner())
        super().__init__(*args, **kwargs)

    def clean(self):
        if any(self.errors):
            return

    def save(self, commit=True):
        child_objects = []
        for form in self.forms:
            if 'url' in form.cleaned_data and form.cleaned_data['url'] not in ('', None):
                child_objects.append(form.save())
        self.parent_object.flyers.set(child_objects)
        # By using set any old flyers that where not included in the current formset are disconnected from the parent
        # collection. By default, these should not remain in the database if they have no other relations.
        WasteFlyer.objects.filter(collections=None).delete()
        return child_objects


class CollectionPropertyValueModelForm(AutoCompleteModelForm):
    collection = ModelChoiceField(
        queryset=Collection.objects.all(),
        widget=autocomplete.ModelSelect2(url='collection-autocomplete'),
        required=True
    )

    class Meta:
        model = CollectionPropertyValue
        fields = ('collection', 'property', 'year', 'average', 'standard_deviation')


class AggregatedCollectionPropertyValueModelForm(AutoCompleteModelForm):
    collections = ModelMultipleChoiceField(
        queryset=Collection.objects.all(),
        widget=autocomplete.ModelSelect2Multiple(url='collection-autocomplete'),
        required=True
    )

    class Meta:
        model = AggregatedCollectionPropertyValue
        fields = ('collections', 'property', 'year', 'average', 'standard_deviation')


class CollectionModelForm(AutoCompleteModelForm):
    catchment = ModelChoiceField(
        queryset=CollectionCatchment.objects.all(),
        widget=autocomplete.ModelSelect2(url='catchment-autocomplete'),
        required=True
    )
    collector = ModelChoiceField(
        queryset=Collector.objects.all(),
        widget=autocomplete.ModelSelect2(url='collector-autocomplete'),
        required=True
    )
    collection_system = ModelChoiceField(
        queryset=CollectionSystem.objects.all(),
        required=True)
    waste_category = ModelChoiceField(
        queryset=WasteCategory.objects.all()
    )
    allowed_materials = ModelMultipleChoiceField(
        queryset=WasteComponent.objects.all(),
        widget=CheckboxSelectMultiple
    )
    frequency = ModelChoiceField(
        queryset=CollectionFrequency.objects.all(),
        widget=autocomplete.ModelSelect2(url='collectionfrequency-autocomplete'),
        required=False
    )

    class Meta:
        model = Collection
        fields = ('catchment', 'collector', 'collection_system', 'waste_category', 'allowed_materials',
                  'connection_rate', 'connection_rate_year', 'frequency', 'fee_system', 'description')
        labels = {
            'description': 'Comments',
            'connection_rate': 'Connection rate [%]',
            'connection_rate_year': 'Year'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
        waste_stream, created = WasteStream.objects.get_or_create(
            defaults={'owner': instance.owner},
            category=data["waste_category"],
            allowed_materials=WasteComponent.objects.filter(id__in=data['allowed_materials'])
        )
        if created:
            waste_stream.allowed_materials.add(*data['allowed_materials'])
        waste_stream.save()
        instance.waste_stream = waste_stream

        if commit:
            return super().save()
        else:
            return super().save(commit=False)


COUNTRY_CHOICES = (
    ('BE', 'BE'),
    ('DE', 'DE'),
    ('DK', 'DK'),
    ('NL', 'NL'),
    ('UK', 'UK'),
    ('SE', 'SE'),
)


class CollectionFilterForm(AutoCompleteModelForm):
    catchment = ModelChoiceField(
        queryset=CollectionCatchment.objects.all(),
        widget=autocomplete.ModelSelect2(url='catchment-autocomplete'),
        required=False
    )
    collector = ModelChoiceField(
        queryset=Collector.objects.all(),
        widget=autocomplete.ModelSelect2(url='collector-autocomplete'),
        required=False
    )
    waste_category = ModelMultipleChoiceField(
        queryset=WasteCategory.objects.all(),
        widget=CheckboxSelectMultiple,
        required=False
    )
    country = MultipleChoiceField(
        choices=COUNTRY_CHOICES,
        required=False
    )
    allowed_materials = ModelMultipleChoiceField(
        queryset=WasteComponent.objects.all(),
        widget=CheckboxSelectMultiple,
        required=False
    )
    frequency_type = ChoiceField(choices=FREQUENCY_TYPES, required=False)

    class Meta:
        model = Collection
        fields = ('catchment', 'collector', 'collection_system', 'country', 'waste_category', 'allowed_materials',
                  'frequency_type', 'fee_system')


class FlyerFilterForm(AutoCompleteModelForm):
    url_valid = BooleanField(widget=RadioSelect())

    class Meta:
        model = WasteFlyer
        fields = ('url_valid',)


class CollectionAddWasteSampleForm(AutoCompleteModelForm):
    sample = ModelChoiceField(queryset=Sample.objects.all(),
                              widget=autocomplete.ModelSelect2(url='sample-autocomplete'))

    class Meta:
        model = Sample
        fields = ('sample',)


class CollectionRemoveWasteSampleForm(SimpleModelForm):
    sample = ModelChoiceField(queryset=Sample.objects.all())

    class Meta:
        model = Collection
        fields = ('sample',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['sample'].queryset = Sample.objects.filter(collections=self.instance)
