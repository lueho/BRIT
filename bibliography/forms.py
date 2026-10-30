from django.core.exceptions import NON_FIELD_ERRORS, PermissionDenied, ValidationError
from django.db import transaction
from django.forms import BaseInlineFormSet, CharField, DateInput, Textarea
from django.utils import timezone
from django_tomselect.forms import TomSelectConfig, TomSelectModelChoiceField

from utils.forms import (
    MARKDOWN_HELP_TEXT,
    ModalModelFormMixin,
    SimpleForm,
    SimpleModelForm,
)
from utils.object_management.policy import visible_queryset

from .bibtex import (
    BibtexArticleParseError,
    parse_bibtex_article_entries,
)
from .models import Author, Licence, Source, SourceAuthor, author_name_has_letter
from .services import AUTHOR_ADD_DENIED_MESSAGE, create_source_with_authors


class AuthorModelForm(SimpleModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["author_type"].required = False
        if not self.instance.pk:
            self.fields["author_type"].initial = "person"

    class Meta:
        model = Author
        fields = (
            "author_type",
            "first_names",
            "last_names",
            "organization_name",
            "organization_abbreviation",
            "institution",
            "contact_email",
        )


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
            "citation_key",
            "publisher",
            "title",
            "type",
            "journal",
            "volume",
            "number",
            "eid",
            "pages",
            "month",
            "year",
            "licence",
            "attributions",
            "abstract",
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
        help_texts = {"abstract": MARKDOWN_HELP_TEXT}

    def save(self, commit=True):
        url = self.cleaned_data.get("url") or ""
        last_accessed = self.cleaned_data.get("last_accessed")
        if url:
            if self.instance.pk:
                url_changed = url != (Source.objects.get(pk=self.instance.pk).url or "")
            else:
                url_changed = False
            if url_changed or not last_accessed:
                self.instance.last_accessed = timezone.now().date()
        return super().save(commit=commit)


class SourceModalModelForm(ModalModelFormMixin, SourceModelForm):
    pass


class SourceBibtexArticleImportForm(SimpleForm):
    bibtex_entry = CharField(widget=Textarea(attrs={"rows": 18}))

    def clean_bibtex_entry(self):
        bibtex_entry = self.cleaned_data["bibtex_entry"]
        try:
            self.parsed_entries = parse_bibtex_article_entries(bibtex_entry)
        except BibtexArticleParseError as exc:
            raise ValidationError(str(exc)) from exc
        return bibtex_entry

    def create_source(self, *, owner):
        parsed_entries = getattr(self, "parsed_entries", None)
        if parsed_entries is not None and len(parsed_entries) != 1:
            raise ValueError("The BibTeX import form contains multiple entries.")
        return self.create_sources(owner=owner)[0]

    def create_sources(self, *, owner):
        parsed_entries = getattr(self, "parsed_entries", None)
        if parsed_entries is None:
            raise ValueError("The BibTeX import form must be validated before saving.")

        with transaction.atomic():
            sources = []
            for parsed_entry in parsed_entries:
                sources.append(
                    self._create_source_from_parsed_entry(
                        owner=owner,
                        parsed_entry=parsed_entry,
                    )
                )

        return sources

    def _create_source_from_parsed_entry(self, *, owner, parsed_entry):
        authors_data = [
            parsed_author
            for parsed_author in parsed_entry["authors"]
            if self._parsed_author_is_usable(parsed_author)
        ]
        source_data = {
            "type": "article",
            "citation_key": "",
            "publisher": parsed_entry["publisher"],
            "title": parsed_entry["title"],
            "journal": parsed_entry["journal"],
            "volume": parsed_entry["volume"],
            "number": parsed_entry["number"],
            "eid": parsed_entry["eid"],
            "pages": parsed_entry["pages"],
            "month": parsed_entry["month"],
            "year": parsed_entry["year"],
            "abstract": parsed_entry["abstract"],
            "url": parsed_entry["url"],
            "doi": parsed_entry["doi"],
        }
        try:
            source = create_source_with_authors(owner, source_data, authors_data)
        except PermissionDenied as exc:
            if str(exc) == AUTHOR_ADD_DENIED_MESSAGE:
                raise ValidationError(
                    "You need permission to create missing authors from BibTeX imports."
                ) from exc
            raise ValidationError(str(exc)) from exc
        except ValidationError as exc:
            raise ValidationError(
                [
                    f'Entry "{parsed_entry["title"]}": {message}'
                    for message in self._flatten_validation_messages(exc)
                ]
            ) from exc
        source.update_abbreviation()
        return source

    @staticmethod
    def _flatten_validation_messages(exc):
        if not hasattr(exc, "error_dict"):
            return exc.messages
        messages = []
        for field, field_messages in exc.message_dict.items():
            for message in field_messages:
                if field == NON_FIELD_ERRORS:
                    messages.append(message)
                else:
                    label = Source._meta.get_field(field).verbose_name
                    messages.append(f"{label}: {message}")
        return messages

    @staticmethod
    def _parsed_author_is_usable(parsed_author):
        if parsed_author.get("author_type", "person") == "organization":
            name = " ".join(str(parsed_author.get("organization_name") or "").split())
            return author_name_has_letter(name)
        last_names = " ".join(str(parsed_author.get("last_names") or "").split())
        return author_name_has_letter(last_names)


class SourceAuthorForm(SimpleModelForm):
    author = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="author-autocomplete",
            label_field="label",
        ),
        label="Author",
    )

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        user = getattr(request, "user", None)
        self.fields["author"].queryset = visible_queryset(user, Author.objects.all())

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
        if not source.pk:
            return
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
        label="Reference",
    )

    class Meta:
        model = Source
        fields = ("source",)
