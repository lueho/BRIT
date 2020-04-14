from django.forms import ModelForm
from leaflet.forms.widgets import LeafletWidget

from .models import Catchment


class CatchmentForm(ModelForm):
    class Meta:
        model = Catchment
        fields = ['title', 'description', 'geom', ]
        widgets = {'geom': LeafletWidget()}

# class CatchmentSelectForm(ModelForm):

# title = ModelMultipleChoiceField(queryset=Catchment.objects.all(),
# required=True,
# widget=FilteredSelectedMultiple("Catchments", is_stacked=False)

# class Media:
# css = {'all': ('/static/admin/css/widgets.css',), }
# js = {'',)

# def __init__(self, parents=None, *args, **kwargs):
# super(CatchmentSelectForm, self).__init__(*args, **kwargs)
