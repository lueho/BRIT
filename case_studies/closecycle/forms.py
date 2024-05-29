from dal import autocomplete
from django.forms import ModelChoiceField

from maps.models import Region
from utils.forms import AutoCompleteModelForm
from .models import Showcase


class ShowcaseModelForm(AutoCompleteModelForm):
    region = ModelChoiceField(
        queryset=Region.objects.all(),
        widget=autocomplete.ModelSelect2(url='region-autocomplete'),
        required=True
    )

    class Meta:
        model = Showcase
        fields = ('name', 'region', 'description')
