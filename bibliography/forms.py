from brit.forms import CustomModalModelForm, OwnedObjectModelForm

from .models import Source


class SourceModelForm(OwnedObjectModelForm):
    class Meta:
        model = Source
        exclude = ('created_at', 'created_by', 'lastmodified_at',
                   'lastmodified_by', 'owner', 'type', 'visible_to_groups')


class SourceModalModelForm(CustomModalModelForm):
    class Meta:
        model = Source
        fields = '__all__'
