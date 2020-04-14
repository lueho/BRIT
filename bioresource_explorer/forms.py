from django.forms import (IntegerField,
                          ModelForm,
                          TextInput)

from .models import HamburgRoadsideTrees


class HamburgRoadsideTreeFilterForm(ModelForm):
    pflanzjahr_min = IntegerField(required=False, label='Planted earliest in')
    pflanzjahr_max = IntegerField(required=False, label='Planged latest in')

    def __init__(self, *args, **kwargs):
        super(HamburgRoadsideTreeFilterForm, self).__init__(*args, **kwargs)
        self.fields.pop("pflanzjahr")
        self.fields['pflanzjahr_min'].initial = 1801

    class Meta:
        model = HamburgRoadsideTrees
        fields = ['gattung_deutsch', 'bezirk', 'pflanzjahr']
        widgets = {
            'pflanzjahr_min': TextInput(attrs={'id': 'input_pflanzjahr_min', 'name': 'input_pflanzjahr_min'}),
            'bezirk': TextInput(attrs={'name': 'input_bezirk', 'id': 'input_bezirk'})
        }
        labels = {
            'gattung_deutsch': 'Tree type',
            'bezirk': 'City district',
            'pflanzjahr_min': 'Planted earliest',
            'pflanzjahr_max': 'Planted latest',
        }
