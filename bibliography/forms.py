from dal.autocomplete import ModelSelect2, ModelSelect2Multiple
from django.forms import DateInput, ModelChoiceField, ModelMultipleChoiceField

from utils.forms import AutoCompleteModelForm, ModalModelFormMixin, SimpleModelForm
from .models import Author, Licence, Source, SourceAuthor


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
    authors = ModelMultipleChoiceField(
        queryset=Author.objects.all(),
        required=False,
        widget=ModelSelect2Multiple(url='author-autocomplete')
    )

    class Meta:
        model = Source
        fields = (
            'abbreviation', 'authors', 'publisher', 'title', 'type', 'journal', 'issue', 'year', 'licence',
            'attributions', 'url', 'url_valid', 'url_checked', 'doi', 'last_accessed')
        widgets = {
            'url_checked': DateInput(attrs={'type': 'date'}),
            'last_accessed': DateInput(attrs={'type': 'date'})
        }

    def save(self, commit=True):
        # Pop authors from cleaned_data so they won't be handled automatically
        authors = self.cleaned_data.pop('authors', [])
        instance = super().save(commit=False)

        if commit:
            instance.save()
            # Clear existing SourceAuthor instances (important for updates)
            SourceAuthor.objects.filter(source=instance).delete()
            # Create new through model instances with the ordering from the queryset
            for position, author in enumerate(authors, start=1):
                SourceAuthor.objects.create(
                    source=instance,
                    author=author,
                    position=position
                )
        return instance


class SourceModalModelForm(ModalModelFormMixin, SourceModelForm):
    pass


class SourceSimpleFilterForm(AutoCompleteModelForm):
    source = ModelChoiceField(queryset=Source.objects.all(), widget=ModelSelect2(url='source-autocomplete'))

    class Meta:
        model = Source
        fields = ('source',)
