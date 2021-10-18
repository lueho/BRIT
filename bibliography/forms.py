from django.forms import ModelForm

from .models import Source


class LitSourceModelForm(ModelForm):
    class Meta:
        model = Source
        fields = '__all__'
