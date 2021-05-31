from django.forms import ModelForm

from .models import LiteratureSource


class LitSourceModelForm(ModelForm):
    class Meta:
        model = LiteratureSource
        fields = '__all__'
