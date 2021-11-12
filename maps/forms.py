from django.forms import (Form,
                          ModelChoiceField,
                          ModelForm,
                          MultipleChoiceField,
                          IntegerField,
                          )
from django.forms.widgets import CheckboxSelectMultiple
from leaflet.forms.widgets import LeafletWidget

from .models import Region, Catchment, NutsRegion


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
    region = ModelChoiceField(queryset=Region.objects.all())
    category = MultipleChoiceField(
        choices=(('standard', 'Standard'), ('custom', 'Custom'),),
        widget=CheckboxSelectMultiple
    )
    catchment = ModelChoiceField(queryset=Catchment.objects.all())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class NutsMapFilterForm(Form):
    levl_code = IntegerField(label='Level', min_value=0, max_value=3)
    cntr_code = MultipleChoiceField(label='Country', choices=(('DE', 'DE'), ('FR', 'FR'),))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cntr_code'].choices = \
            NutsRegion.objects.values_list('cntr_code', 'cntr_code').distinct().order_by('cntr_code')
