from django.core.exceptions import ValidationError
from django.db import transaction
from django.forms import BaseInlineFormSet, DateInput
from django_tomselect.forms import TomSelectConfig, TomSelectModelChoiceField

from utils.forms import ModalModelFormMixin, SimpleModelForm

from .models import Author, Licence, Source, SourceAuthor


class AuthorModelForm(SimpleModelForm):
    class Meta:
        model = Author
        fields = ("first_names", "last_names")


class AuthorModalModelForm(ModalModelFormMixin, AuthorModelForm):
    pass


class LicenceModelForm(SimpleModelForm):
    class Meta:
        model = Licence
        fields = ("name", "reference_url")


class LicenceModalModelForm(ModalModelFormMixin, LicenceModelForm):
    pass


class SourceModelForm(SimpleModelForm):
    class Meta:
        model = Source
        fields = (
            "abbreviation",
            "publisher",
            "title",
            "type",
            "journal",
            "issue",
            "year",
            "licence",
            "attributions",
            "url",
            "url_valid",
            "url_checked",
            "doi",
            "last_accessed",
        )
        widgets = {
            "url_checked": DateInput(attrs={"type": "date"}),
            "last_accessed": DateInput(attrs={"type": "date"}),
        }


class SourceModalModelForm(ModalModelFormMixin, SourceModelForm):
    pass


class SourceAuthorForm(SimpleModelForm):
    author = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="author-autocomplete",
            label_field="label",
        ),
        label="Authors",
    )

    class Meta:
        model = SourceAuthor
        fields = ("author",)


class SourceAuthorFormSet(BaseInlineFormSet):
    def clean(self):
        """
        Validates the whole formset
        """
        if any(self.errors):
            return

        # Get all forms that have authors
        authors = []
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get("DELETE", False):
                author = form.cleaned_data.get("author")
                if author:
                    if author in authors:
                        raise ValidationError("Each author can only be added once.")
                    authors.append(author)

    def save(self, commit=True):
        """
        Save all objects and assign positions based on form order.
        Only save forms that have an author selected.
        """
        with transaction.atomic():
            # IMPORTANT: Override super().save() to prevent empty forms from creating objects
            if commit:
                # Get all forms that aren't being deleted and have data
                valid_forms = [
                    form
                    for form in self.forms
                    if form.cleaned_data
                    and not form.cleaned_data.get("DELETE", False)
                    and form.cleaned_data.get("author")
                ]

                # Only save valid forms, not all forms
                saved_objects = []
                for position, form in enumerate(valid_forms, 1):
                    # Update position on the instance
                    form.instance.position = position
                    saved_object = form.save(commit=True)
                    saved_objects.append(saved_object)

                # Handle deletions – explicitly delete instances from forms marked for deletion
                for form in self.forms:
                    if (
                        form.cleaned_data
                        and form.cleaned_data.get("DELETE", False)
                        and form.instance.pk
                    ):
                        form.instance.delete()

                # Normalize positions to ensure they're sequential
                self._normalize_positions()

                return saved_objects
            else:
                # For commit=False, still filter to valid forms only
                valid_forms = [
                    form
                    for form in self.forms
                    if form.cleaned_data
                    and not form.cleaned_data.get("DELETE", False)
                    and form.cleaned_data.get("author")
                ]

                objects = []
                for form in valid_forms:
                    obj = form.save(commit=False)
                    objects.append(obj)
                return objects

    def _normalize_positions(self):
        """
        Ensure positions are sequential without gaps.
        """
        source = self.instance
        authors = list(source.sourceauthors.all().order_by("position"))

        # Update positions if necessary
        for i, author in enumerate(authors, 1):
            if author.position != i:
                author.position = i
                author.save(update_fields=["position"])


class SourceSimpleFilterForm(SimpleModelForm):
    source = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="source-autocomplete",
            label_field="text",
        ),
        label="Source",
    )

    class Meta:
        model = Source
        fields = ("source",)
