from brit.forms import CustomModalModelForm, OwnedObjectModelForm

from .models import Author, Licence, Source


class AuthorModelForm(OwnedObjectModelForm):
    class Meta:
        model = Author
        fields = ('first_names', 'last_names')


class AuthorModalModelForm(CustomModalModelForm):
    class Meta:
        model = Author
        fields = ('first_names', 'last_names')


class LicenceModelForm(OwnedObjectModelForm):
    class Meta:
        model = Licence
        fields = ('name', 'reference_url')


class LicenceModalModelForm(CustomModalModelForm):
    class Meta:
        model = Licence
        fields = ('name', 'reference_url')


class SourceModelForm(OwnedObjectModelForm):
    class Meta:
        model = Source
        exclude = ('created_at', 'created_by', 'lastmodified_at',
                   'lastmodified_by', 'owner', 'type', 'visible_to_groups')


class SourceModalModelForm(CustomModalModelForm):
    class Meta:
        model = Source
        fields = '__all__'
