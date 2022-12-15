from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Field, Layout, Row, HTML, Div
from dal import autocomplete
from django.core.exceptions import ValidationError
from django.forms import (BooleanField, CheckboxSelectMultiple, HiddenInput, IntegerField, ModelChoiceField,
                          ModelMultipleChoiceField, RadioSelect)
from django.utils.translation import gettext as _

from distributions.models import TemporalDistribution, Timestep
from materials.models import Material, MaterialCategory, Sample
from users.models import get_default_owner
from utils.forms import (AutoCompleteModelForm, ForeignkeyField, M2MInlineFormSet, ModalModelFormMixin, SimpleForm,
                         SimpleModelForm)
from .models import (AggregatedCollectionPropertyValue, Collection, CollectionCatchment, CollectionCountOptions,
                     CollectionFrequency, CollectionPropertyValue, CollectionSeason, CollectionSystem, Collector,
                     WasteCategory, WasteComponent, WasteFlyer, WasteStream)


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


class CollectionSeasonFormHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_tag = False
        self.disable_csrf = True
        self.layout = Layout(
            Div(
                HTML('<p><strong class="title-strong">Season {{ forloop.counter }}</strong></p>'),
                'distribution',
                Row(Column(Field('first_timestep')), Column(Field('last_timestep'))),
                HTML('<p>Total collections in this season</p>'),
                Row(
                    Column(Field('standard')),
                    Column(Field('option_1')),
                    Column(Field('option_2')),
                    Column(Field('option_3')),
                    css_class='formset-form'
                )
            )
        )


class CollectionSeasonForm(SimpleForm):
    distribution = ModelChoiceField(
        queryset=TemporalDistribution.objects.filter(name='Months of the year'),
        initial=TemporalDistribution.objects.get(name='Months of the year'),
        empty_label=None,
        widget=HiddenInput()
    )
    first_timestep = ModelChoiceField(
        queryset=Timestep.objects.filter(distribution=TemporalDistribution.objects.get(name='Months of the year')),
        label='Start'
    )
    last_timestep = ModelChoiceField(
        queryset=Timestep.objects.filter(distribution=TemporalDistribution.objects.get(name='Months of the year')),
        label='End'
    )
    standard = IntegerField(required=False)
    option_1 = IntegerField(required=False)
    option_2 = IntegerField(required=False)
    option_3 = IntegerField(required=False)

    class Meta:
        fields = ('distribution', 'first_timestep', 'last_timestep', 'standard', 'option_1', 'option_2', 'option_3')

    # @property
    # def helper(self):
    #     helper = FormHelper()
    #     helper.layout = Layout(
    #         Row(Column(Field('first_timestep')), Column(Field('last_timestep'))),
    #         Row(Column(Field('cpw_standard')))
    #     )
    #     helper.nam = 'Hello'
    #     return helper

    def save(self):
        self.instance, _ = CollectionSeason.objects.get_or_create(
            distribution=self.cleaned_data['distribution'],
            first_timestep=self.cleaned_data['first_timestep'],
            last_timestep=self.cleaned_data['last_timestep']
        )
        return self.instance


class CollectionSeasonFormSet(M2MInlineFormSet):

    def clean(self):
        for i, form in enumerate(self.forms):
            if i > 0 and self.forms[i - 1].cleaned_data.get('last_timestep').order >= self.forms[i].cleaned_data.get(
                    'first_timestep').order:
                raise ValidationError(_('The seasons must not overlap and must be given in order.'), code='invalid')

    def save(self, commit=True):
        child_objects = super().save(commit=commit)

        for form in self.forms:
            options = CollectionCountOptions.objects.get(frequency=self.parent_object, season=form.instance)
            options.standard = form.cleaned_data['standard']
            options.option_1 = form.cleaned_data['option_1']
            options.option_2 = form.cleaned_data['option_2']
            options.option_3 = form.cleaned_data['option_3']
            options.save()

        CollectionSeason.objects.exclude(
            distribution=TemporalDistribution.objects.get(name='Months of the year'),
            first_timestep=Timestep.objects.get(name='January'),
            last_timestep=Timestep.objects.get(name='December')
        ).filter(collectionfrequency=None).delete()
        return child_objects


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
            url = self.cleaned_data.get('url')
            if url:
                instance, _ = WasteFlyer.objects.get_or_create(url=self.cleaned_data['url'], defaults=defaults)
                return instance
        else:
            return super().save(commit=False)


class WasteFlyerModalModelForm(ModalModelFormMixin, WasteFlyerModelForm):
    pass


class BaseWasteFlyerUrlFormSet(M2MInlineFormSet):

    def __init__(self, *args, **kwargs):
        self.owner = kwargs.pop('owner', get_default_owner())
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        child_objects = super().save(commit=commit)
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
            Field('frequency'),
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


class CollectionFilterFormHelper(FormHelper):
    layout = Layout(
        'catchment',
        'collector',
        'collection_system',
        'waste_category',
        'allowed_materials',
        Field('connection_rate', template="fields/range_slider_field.html"),
        Row(Column(Field('seasonal_frequency')), Column(Field('optional_frequency'))),
        'fee_system'
    )


class CollectionFilterForm(AutoCompleteModelForm):
    class Meta:
        model = Collection
        fields = []

    def __init__(self, *args, **kwargs):
        self.helper = CollectionFilterFormHelper()
        super().__init__(*args, **kwargs)


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
