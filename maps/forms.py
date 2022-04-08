from crispy_forms.helper import FormHelper
from crispy_forms.layout import Field, Layout
from django.forms import (Form,
                          ModelChoiceField,
                          ModelForm,
                          MultipleChoiceField,
                          ChoiceField,
                          IntegerField,
                          )
from django.forms.widgets import CheckboxSelectMultiple, RadioSelect
from django.urls import reverse

from brit.forms import CustomModelForm, CustomModalModelForm, ModalFormHelper

from .models import Attribute, Region, Catchment, NutsRegion, LauRegion, RegionAttributeValue


class AttributeModelForm(CustomModelForm):
    class Meta:
        model = Attribute
        fields = ('name', 'unit', 'description')


class AttributeModalModelForm(CustomModalModelForm):
    class Meta:
        model = Attribute
        fields = ('name', 'unit', 'description',)


class RegionAttributeValueModelForm(CustomModelForm):
    class Meta:
        model = RegionAttributeValue
        fields = ('region', 'attribute', 'value', 'standard_deviation')


class RegionAttributeValueModalModelForm(CustomModalModelForm):
    class Meta:
        model = RegionAttributeValue
        fields = ('region', 'attribute', 'value', 'standard_deviation')


# ----------- Catchments -----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CatchmentModelForm(ModelForm):
    class Meta:
        model = Catchment
        fields = ('name', 'description', 'parent_region', 'region')
        # fields = ('parent_region', 'name', 'description', 'geom',)
        # widgets = {'geom': LeafletWidget()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.fields['geom'].label = ''

    # def clean(self):
    #     catchment = super().clean()
    #     region = catchment.get('parent_region')
    #     if region and catchment:
    #         if not region.geom.contains(catchment.get('geom')):
    #             self.add_error('geom', 'The catchment must be inside the region.')


class CatchmentQueryForm(Form):
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class NutsRegionQueryForm(Form):
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


class NutsAndLauCatchmentQueryForm(Form):
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


class NutsMapFilterForm(Form):
    levl_code = IntegerField(label='Level', min_value=0, max_value=3)
    cntr_code = MultipleChoiceField(label='Country', choices=(('DE', 'DE'), ('FR', 'FR'),))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cntr_code'].choices = \
            NutsRegion.objects.values_list('cntr_code', 'cntr_code').distinct().order_by('cntr_code')
