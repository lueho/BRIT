from django.forms import (IntegerField,
                          ModelForm,
                          TextInput,
                          CheckboxSelectMultiple,
                          ModelMultipleChoiceField)

from scenario_builder.models import Catchment
from .models import HamburgRoadsideTrees


class HamburgRoadsideTreeFilterForm(ModelForm):
    pflanzjahr_min = IntegerField(required=False, label='Planted earliest in')
    pflanzjahr_max = IntegerField(required=False, label='Planted latest in')
    bezirk = ModelMultipleChoiceField(
        queryset=Catchment.objects.filter(region__name='Hamburg', type='administrative'),
        widget=CheckboxSelectMultiple,
        required=True,
        label='City district'
    )

    def __init__(self, *args, **kwargs):
        super(HamburgRoadsideTreeFilterForm, self).__init__(*args, **kwargs)
        self.fields.pop("pflanzjahr")
        self.fields['pflanzjahr_min'].initial = 1801

    class Meta:
        model = HamburgRoadsideTrees
        fields = ['gattung_deutsch', 'pflanzjahr']
        widgets = {
            'pflanzjahr_min': TextInput(attrs={'id': 'input_pflanzjahr_min', 'function_name': 'input_pflanzjahr_min'}),
        }
        labels = {
            'gattung_deutsch': 'Tree type',
            'pflanzjahr_min': 'Planted earliest',
            'pflanzjahr_max': 'Planted latest',
        }
