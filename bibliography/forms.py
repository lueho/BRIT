from dal.autocomplete import ModelSelect2
from django.forms import DateInput, ModelChoiceField, ModelMultipleChoiceField

from utils.forms import AutoCompleteModelForm, SimpleModelForm, ModalModelFormMixin
from .models import Author, Licence, Source


class AuthorModelForm(SimpleModelForm):
    class Meta:
        model = Author
        fields = ('first_names', 'last_names')


class AuthorModalModelForm(ModalModelFormMixin, AuthorModelForm):
    pass


class LicenceModelForm(SimpleModelForm):
    class Meta:
        model = Licence
        fields = ('name', 'reference_url')


class LicenceModalModelForm(ModalModelFormMixin, LicenceModelForm):
    pass


class SourceModelForm(SimpleModelForm):
    authors = ModelMultipleChoiceField(queryset=Author.objects.all(), required=False)

    class Meta:
        model = Source
        fields = (
            'abbreviation', 'authors', 'publisher', 'title', 'type', 'journal', 'issue', 'year', 'licence',
            'attributions',
            'url', 'url_valid', 'url_checked', 'doi', 'last_accessed')
        widgets = {
            'url_checked': DateInput(attrs={'type': 'date'}),
            'last_accessed': DateInput(attrs={'type': 'date'})
        }


class SourceModalModelForm(ModalModelFormMixin, SourceModelForm):
    pass


class SourceSimpleFilterForm(AutoCompleteModelForm):
    source = ModelChoiceField(queryset=Source.objects.all(), widget=ModelSelect2(url='source-autocomplete'))

    class Meta:
        model = Source
        fields = ('source',)
