from django.forms import (Form,
                          ModelChoiceField,
                          ModelForm,
                          MultipleChoiceField,
                          )
from django.forms.widgets import CheckboxSelectMultiple
from leaflet.forms.widgets import LeafletWidget

from .models import Region, Catchment


# ----------- Catchments -----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CatchmentCreateForm(ModelForm):
    class Meta:
        model = Catchment
        fields = ['region', 'name', 'description', 'geom', ]
        widgets = {'geom': LeafletWidget()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['geom'].label = ''


class CatchmentForm(ModelForm):
    class Meta:
        model = Catchment
        fields = ('region', 'name', 'description', 'geom',)
        widgets = {'geom': LeafletWidget()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['geom'].label = ''

    def clean(self):
        catchment = super().clean()
        region = catchment.get('region')
        if region and catchment:
            if not region.geom.contains(catchment.get('geom')):
                self.add_error('geom', 'The catchment must be inside the region.')


class CatchmentQueryForm(Form):
    region = ModelChoiceField(queryset=Region.objects.all())
    category = MultipleChoiceField(
        choices=(('standard', 'Standard'), ('custom', 'Custom'),),
        widget=CheckboxSelectMultiple
    )
    catchment = ModelChoiceField(queryset=Catchment.objects.all())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
