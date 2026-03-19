from django.core.exceptions import ValidationError
from django.db import transaction
from django.forms import BaseInlineFormSet, CharField, DateInput, Textarea
from django_tomselect.forms import TomSelectConfig, TomSelectModelChoiceField

from utils.forms import (
    MARKDOWN_HELP_TEXT,
    ModalModelFormMixin,
    SimpleForm,
    SimpleModelForm,
)

from .bibtex import (
    BibtexArticleParseError,
    parse_bibtex_article_entries,
)
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
        sources = self.create_sources(owner=owner)
        if len(sources) != 1:
            raise ValueError("The BibTeX import form contains multiple entries.")
        return sources[0]

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
        authors = self._resolve_authors(
            owner=owner,
            parsed_authors=parsed_entry["authors"],
        )

        source = Source.objects.create(
            owner=owner,
            type="article",
            citation_key="",
            publisher=parsed_entry["publisher"],
            title=parsed_entry["title"],
            journal=parsed_entry["journal"],
            volume=parsed_entry["volume"],
            number=parsed_entry["number"],
            eid=parsed_entry["eid"],
            pages=parsed_entry["pages"],
            month=parsed_entry["month"],
            year=parsed_entry["year"],
            abstract=parsed_entry["abstract"],
            url=parsed_entry["url"],
            doi=parsed_entry["doi"],
        )
        for position, author in enumerate(authors, start=1):
            SourceAuthor.objects.create(
                source=source,
                author=author,
                position=position,
            )
        source.update_abbreviation()

        return source

    def _resolve_authors(self, *, owner, parsed_authors):
        authors = []
        author_ids = set()

        for parsed_author in parsed_authors:
            first_names = " ".join(str(parsed_author.get("first_names") or "").split())
            last_names = " ".join(str(parsed_author.get("last_names") or "").split())
            suffix = " ".join(str(parsed_author.get("suffix") or "").split())
            if not last_names:
                continue

            author_queryset = Author.objects.filter(
                first_names__iexact=first_names,
                last_names__iexact=last_names,
            )
            if suffix:
                author_queryset = author_queryset.filter(suffix__iexact=suffix)

            author = author_queryset.first()
            if author is None:
                if not owner.has_perm("bibliography.add_author"):
                    raise ValidationError(
                        "You need permission to create missing authors from BibTeX imports."
                    )
                author = Author.objects.create(
                    owner=owner,
                    first_names=first_names,
                    last_names=last_names,
                    suffix=suffix,
                )

            if author.pk not in author_ids:
                authors.append(author)
                author_ids.add(author.pk)

        return authors


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
        label="Source",
    )

    class Meta:
        model = Source
        fields = ("source",)
