from django.core.exceptions import ValidationError
from django.db import transaction
from django.forms import (BaseInlineFormSet, DateInput, ModelChoiceField)
from extra_views import InlineFormSetFactory

from utils.forms import AutoCompleteModelForm, ModalModelFormMixin, SimpleModelForm
from utils.widgets import BSModelSelect2
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
    class Meta:
        model = Source
        fields = (
            'abbreviation', 'publisher', 'title', 'type', 'journal', 'issue', 'year', 'licence',
            'attributions', 'url', 'url_valid', 'url_checked', 'doi', 'last_accessed')
        widgets = {
            'url_checked': DateInput(attrs={'type': 'date'}),
            'last_accessed': DateInput(attrs={'type': 'date'})
        }


class SourceModalModelForm(ModalModelFormMixin, SourceModelForm):
    pass


class SourceAuthorForm(AutoCompleteModelForm):
    author = ModelChoiceField(
        queryset=Author.objects.all(),
        widget=BSModelSelect2(url='author-autocomplete'),
        label='Authors',
        required=False
    )

    class Meta:
        model = SourceAuthor
        fields = ('author',)


class SourceAuthorFormSet(BaseInlineFormSet):
    def clean(self):
        """
        Validate that no duplicate authors exist for this source.
        """
        super().clean()

        if any(self.errors):
            # Don't validate if individual forms have errors
            return

        forms = [form for form in self.forms if form.cleaned_data and not form.cleaned_data.get('DELETE', False)]

        # Check for duplicate authors
        authors = {}
        for form in forms:
            author = form.cleaned_data.get('author')

            if author:
                if author.id in authors:
                    raise ValidationError(
                        f"Author '{author}' appears multiple times. Each author can only appear once for a source."
                    )
                authors[author.id] = True

    def save(self, commit=True):
        """
        Save all objects and assign positions based on form order.
        """
        with transaction.atomic():
            # First save all objects without worrying about position
            objects = super().save(commit=False)

            if commit:
                # Get all forms that aren't being deleted and have data
                valid_forms = [
                    form for form in self.forms
                    if form.cleaned_data and not form.cleaned_data.get('DELETE', False)
                ]

                # Assign positions based on form order
                for position, form in enumerate(valid_forms, 1):
                    # Update position on the instance
                    form.instance.position = position
                    form.instance.save()

                # Handle deletions
                for obj in self.deleted_objects:
                    obj.delete()

                # Normalize positions to ensure they're sequential
                self._normalize_positions()

        return objects

    def _normalize_positions(self):
        """
        Ensure positions are sequential without gaps.
        """
        source = self.instance
        authors = list(source.sourceauthors.all().order_by('position'))

        # Update positions if necessary
        for i, author in enumerate(authors, 1):
            if author.position != i:
                author.position = i
                author.save(update_fields=['position'])


class SourceAuthorInline(InlineFormSetFactory):
    model = SourceAuthor
    form_class = SourceAuthorForm
    formset_class = SourceAuthorFormSet
    fields = ('author',)
    factory_kwargs = {
        'extra': 0,
        'min_num': 1,
        'can_delete': True,
    }


class SourceSimpleFilterForm(AutoCompleteModelForm):
    source = ModelChoiceField(queryset=Source.objects.all(), widget=BSModelSelect2(url='source-autocomplete'))

    class Meta:
        model = Source
        fields = ('source',)
