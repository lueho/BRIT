from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Field, Layout, Row
from dal.autocomplete import ModelSelect2
# from django.contrib.gis.db.models import MultiPolygonField
from django.contrib.gis.forms import MultiPolygonField
from django.db.models import Subquery
from django.forms import (BaseFormSet, ChoiceField, DateInput, DateField, ModelChoiceField, MultipleChoiceField,
                          ValidationError)
from django.forms.widgets import CheckboxSelectMultiple, RadioSelect
from django.urls import reverse
from leaflet.forms.widgets import LeafletWidget

from utils.forms import AutoCompleteForm, AutoCompleteModelForm, SimpleForm, SimpleModelForm, ModalModelFormMixin
from .models import Attribute, Region, Catchment, GeoPolygon, LauRegion, NutsRegion, RegionAttributeValue, Location


class LocationModelForm(SimpleModelForm):
    class Meta:
        model = Location
        fields = ('name', 'geom', 'address')
        widgets = {'geom': LeafletWidget()}


class RegionModelForm(AutoCompleteModelForm):
    geom = MultiPolygonField(widget=LeafletWidget())

    class Meta:
        model = Region
        fields = ('name', 'geom', 'country', 'description')

    def save(self, commit=True):
        geom = self.cleaned_data.pop('geom')
        instance = super().save(commit=False)
        instance.borders = GeoPolygon.objects.create(geom=geom)
        if commit:
            instance.save()
        return instance


class AttributeModelForm(SimpleModelForm):
    class Meta:
        model = Attribute
        fields = ('name', 'unit', 'description')


class AttributeModalModelForm(ModalModelFormMixin, AttributeModelForm):
    pass


class RegionAttributeValueModelForm(AutoCompleteModelForm):
    region = ModelChoiceField(
        queryset=Region.objects.all(),
        widget=ModelSelect2(url='region-autocomplete'),
    )
    date = DateField(widget=DateInput(attrs={'type': 'date'}))

    class Meta:
        model = RegionAttributeValue
        fields = ('region', 'attribute', 'date', 'value', 'standard_deviation')


class RegionAttributeValueModalModelForm(ModalModelFormMixin, RegionAttributeValueModelForm):
    pass


# ----------- Catchments -----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CatchmentModelForm(AutoCompleteModelForm):
    region = ModelChoiceField(
        queryset=Region.objects.all(),
        widget=ModelSelect2(url='region-autocomplete'),
        required=True
    )
    parent_region = ModelChoiceField(
        queryset=Region.objects.all(),
        widget=ModelSelect2(url='region-autocomplete'),
        required=False
    )

    class Meta:
        model = Catchment
        fields = ('name', 'region', 'parent_region', 'description')


class CatchmentDrawCustomModelForm(AutoCompleteModelForm):
    geom = MultiPolygonField(widget=LeafletWidget())
    parent_region = ModelChoiceField(
        queryset=Region.objects.all(),
        widget=ModelSelect2(url='region-autocomplete'),
        required=False
    )

    class Meta:
        model = Catchment
        fields = ('name', 'geom', 'parent_region', 'description')


class CatchmentCreateMergeLauForm(AutoCompleteModelForm):
    parent = ModelChoiceField(
        queryset=Catchment.objects.all(),
        widget=ModelSelect2(url='catchment-autocomplete'),
        label='Parent catchment',
        required=True
    )

    class Meta:
        model = Catchment
        fields = ('name', 'parent', 'description')


class RegionMergeFormHelper(FormHelper):
    form_tag = False
    disable_csrf = True
    layout = (
        Row(Column(Field('region')), css_class='formset-form')
    )


class RegionMergeForm(AutoCompleteForm):
    region = ModelChoiceField(
        queryset=Region.objects.filter(pk__in=Subquery(LauRegion.objects.all().values('pk'))),
        widget=ModelSelect2(url='region-of-lau-autocomplete'),
        label='Regions',
        required=False
    )


class RegionMergeFormSet(BaseFormSet):

    def clean(self):
        if any(self.errors):
            return
        non_empty_forms = 0
        for form in self.forms:
            if 'region' not in form.cleaned_data or not form.cleaned_data['region']:
                continue
            else:
                non_empty_forms += 1
        if non_empty_forms < 1:
            raise ValidationError('You must select at least one region.')


class CatchmentQueryForm(SimpleForm):
    schema = ChoiceField(
        choices=(('nuts', 'NUTS'), ('custom', 'Custom'),),
        widget=RadioSelect
    )
    region = ModelChoiceField(queryset=Region.objects.all())
    category = MultipleChoiceField(
        choices=(('standard', 'Standard'), ('custom', 'Custom'),),
        widget=CheckboxSelectMultiple
    )
    catchment = ModelChoiceField(queryset=Catchment.objects.all())


class NutsRegionQueryForm(SimpleForm):
    level_0 = ModelChoiceField(queryset=NutsRegion.objects.filter(levl_code=0).order_by('nuts_id'))
    level_1 = ModelChoiceField(queryset=NutsRegion.objects.filter(levl_code=1).order_by('nuts_id'), required=False)
    level_2 = ModelChoiceField(queryset=NutsRegion.objects.filter(levl_code=2).order_by('nuts_id'), required=False)
    level_3 = ModelChoiceField(queryset=NutsRegion.objects.filter(levl_code=3).order_by('nuts_id'), required=False)

    @property
    def helper(self):
        helper = FormHelper()
        helper.layout = Layout(
            Field('level_0', data_optionsapi=f'{reverse("data.nuts_region_options")}', data_lvl=0),
            Field('level_1', data_optionsapi=f'{reverse("data.nuts_region_options")}', data_lvl=1),
            Field('level_2', data_optionsapi=f'{reverse("data.nuts_region_options")}', data_lvl=2),
            Field('level_3', data_optionsapi=f'{reverse("data.nuts_region_options")}', data_lvl=3),
        )
        return helper


class NutsAndLauCatchmentQueryForm(SimpleForm):
    level_0 = ModelChoiceField(queryset=Catchment.objects.filter(region__nutsregion__levl_code=0))
    level_1 = ModelChoiceField(queryset=Catchment.objects.filter(region__nutsregion__levl_code=1), required=False)
    level_2 = ModelChoiceField(queryset=Catchment.objects.filter(region__nutsregion__levl_code=2), required=False)
    level_3 = ModelChoiceField(queryset=Catchment.objects.filter(region__nutsregion__levl_code=3), required=False)
    level_4 = ModelChoiceField(queryset=Catchment.objects.none(), required=False)

    @property
    def helper(self):
        helper = FormHelper()
        helper.layout = Layout(
            Field('level_0', data_optionsapi=f'{reverse("data.nuts_lau_catchment_options")}', data_lvl=0),
            Field('level_1', data_optionsapi=f'{reverse("data.nuts_lau_catchment_options")}', data_lvl=1),
            Field('level_2', data_optionsapi=f'{reverse("data.nuts_lau_catchment_options")}', data_lvl=2),
            Field('level_3', data_optionsapi=f'{reverse("data.nuts_lau_catchment_options")}', data_lvl=3),
            Field('level_4', data_lvl=4)
        )
        return helper
