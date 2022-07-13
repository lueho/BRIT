from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout
from django.forms import Form
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


class SourceFilterFormHelper(FormHelper):
    form_tag = False
    include_media = False
    layout = Layout(
        'abbreviation',
        'authors',
        'title',
        'type',
        'year'
    )


class SourceFilterForm(Form):

    class Meta:
        model = Source
        fields = ('abbreviation', 'authors', 'title', 'type', 'year')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = SourceFilterFormHelper()
        self.fields['abbreviation'].widget.attrs = {'data-theme': 'bootstrap4'}
        self.fields['authors'].widget.attrs = {'data-theme': 'bootstrap4'}
        self.fields['title'].widget.attrs = {'data-theme': 'bootstrap4'}

