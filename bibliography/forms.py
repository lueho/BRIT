from brit.forms import CustomModelForm, CustomModalModelForm

from .models import Source


class SourceModelForm(CustomModelForm):
    class Meta:
        model = Source
        fields = '__all__'


class SourceModalModelForm(CustomModalModelForm):
    class Meta:
        model = Source
        fields = '__all__'
