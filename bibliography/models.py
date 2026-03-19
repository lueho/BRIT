import string

import celery
from django.db import models, transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from utils.object_management.models import (
    NamedUserCreatedObject,
    UserCreatedObject,
    UserCreatedObjectManager,
)


class Author(UserCreatedObject):
    first_names = models.CharField(max_length=1023, null=True, blank=True)
    middle_names = models.CharField(max_length=1023, null=True, blank=True)
    last_names = models.CharField(max_length=1023, null=True, blank=True)
    suffix = models.CharField(max_length=100, null=True, blank=True)
    preferred_citation = models.CharField(max_length=2046, null=True, blank=True)

    class Meta:
        ordering = ["last_names", "first_names"]

    def __str__(self):
        parts = [
            " ".join(self.last_names.split()),
        ]
        if self.first_names:
            parts.append(" ".join(self.first_names.split()))
        if self.suffix:
            parts.append(self.suffix.strip())
        return ", ".join(filter(None, parts))

    @property
    def bibtex_name(self):
        """Formats the author's name according to BibTeX conventions."""
        initials = " ".join(
            [
                f"{name.strip()[0].upper()}."
                for name in (self.first_names or "").split()
                + (self.middle_names or "").split()
            ]
        )
        bibtex = (
            f"{' '.join(self.last_names.split())}{', ' + initials if initials else ''}"
        )
        if self.suffix:
            bibtex += f", {self.suffix.strip()}"
        return bibtex

    @property
    def abbreviated_full_name(self):
        """Returns the abbreviated full name with initials."""
        initials = " ".join(
            [
                f"{name[0].upper()}."
                for name in (self.first_names or "").split()
                + (self.middle_names or "").split()
                if name
            ]
        )
        abbreviated = (
            f"{' '.join(self.last_names.split())}{', ' + initials if initials else ''}"
        )
        if self.suffix:
            abbreviated += f", {self.suffix.strip()}"
        return abbreviated


class Licence(NamedUserCreatedObject):
    reference_url = models.URLField(null=True, blank=True)

    def __str__(self):
        return self.name

    @property
    def bibtex_entry(self):
        """Formats the license information for inclusion in a BibTeX entry."""
        bibtex_note = f"License: {self.name}"
        if self.reference_url:
            bibtex_note += f", URL: {self.reference_url}"
        return bibtex_note


SOURCE_TYPES = (
    ("article", "article"),
    ("dataset", "dataset"),
    ("book", "book"),
    ("website", "website"),
    ("custom", "custom"),
)


class SourceManager(UserCreatedObjectManager):
    def get_or_create_custom_by_title(
        self,
        *,
        owner,
        title: str,
        defaults: dict | None = None,
    ) -> tuple[object, bool]:
        source = (
            self.filter(owner=owner, type="custom", title=title).order_by("id").first()
        )
        if source is not None:
            return source, False
        return self.get_or_create(
            owner=owner,
            type="custom",
            title=title,
            defaults=defaults or {},
        )


class Source(UserCreatedObject):
    objects = SourceManager()

    type = models.CharField(max_length=255, choices=SOURCE_TYPES, default="custom")
    authors = models.ManyToManyField(
        Author, through="SourceAuthor", related_name="sources"
    )
    publisher = models.CharField(max_length=127, blank=True, null=True)
    title = models.CharField(max_length=500)
    journal = models.CharField(max_length=500, blank=True, null=True)
    volume = models.CharField(max_length=255, blank=True, null=True)
    number = models.CharField(max_length=255, blank=True, null=True)
    eid = models.CharField(max_length=255, blank=True, null=True)
    pages = models.CharField(max_length=255, blank=True, null=True)
    month = models.CharField(max_length=50, blank=True, null=True)
    year = models.IntegerField(blank=True, null=True)
    citation_key = models.CharField(max_length=50, blank=True)
    abstract = models.TextField(blank=True, null=True)
    licence = models.ForeignKey(
        Licence, on_delete=models.PROTECT, blank=True, null=True
    )
    attributions = models.TextField(blank=True, null=True)
    url = models.URLField(max_length=2083, blank=True, null=True)
    url_valid = models.BooleanField(default=False)
    url_checked = models.DateField(blank=True, null=True)
    doi = models.CharField(max_length=255, blank=True, null=True)
    last_accessed = models.DateField(blank=True, null=True)

    class Meta:
        verbose_name = "Source"

    def __init__(self, *args, **kwargs):
        if "abbreviation" in kwargs and "citation_key" not in kwargs:
            kwargs["citation_key"] = kwargs.pop("abbreviation")
        if "issue" in kwargs and "number" not in kwargs:
            kwargs["number"] = kwargs.pop("issue")
        if "article_number" in kwargs and "eid" not in kwargs:
            kwargs["eid"] = kwargs.pop("article_number")
        super().__init__(*args, **kwargs)

    def ordered_authors(self):
        return self.sourceauthors.order_by("position").select_related("author")

    @property
    def authors_ordered(self):
        return [sa.author for sa in self.ordered_authors()]

    def __str__(self):
        return self.citation_key or self.title or f"Source #{self.pk}"

    @property
    def abbreviation(self):
        return self.citation_key

    @abbreviation.setter
    def abbreviation(self, value):
        self.citation_key = value

    @property
    def issue(self):
        return self.number

    @issue.setter
    def issue(self, value):
        self.number = value

    @property
    def article_number(self):
        return self.eid

    @article_number.setter
    def article_number(self, value):
        self.eid = value

    def generate_abbreviation(self):
        """Generate a citation key from authors and year.

        Follows standard academic conventions:
        - 1 author:  "LastName Year"
        - 2 authors: "LastName1 & LastName2 Year"
        - 3+ authors: "LastName1 et al. Year"
        - No authors: first word of title + year
        Returns the base key without disambiguation suffix.
        """
        authors = list(
            self.sourceauthors.order_by("position")
            .select_related("author")
            .values_list("author__last_names", flat=True)
        )
        year_part = f" {self.year}" if self.year else ""

        if len(authors) == 1:
            base = f"{authors[0]}{year_part}"
        elif len(authors) == 2:
            base = f"{authors[0]} & {authors[1]}{year_part}"
        elif len(authors) >= 3:
            base = f"{authors[0]} et al.{year_part}"
        else:
            # No authors: use first significant word(s) of title
            title_words = (self.title or "").split()
            if title_words:
                base = f"{title_words[0]}{year_part}"
            else:
                base = f"Source{year_part}"

        return base.strip()

    def _disambiguated_abbreviation(self):
        """Generate an abbreviation with a/b/c suffix if the base key collides."""
        base = self.generate_abbreviation()
        if not base:
            return base

        # Find existing sources with the same base abbreviation (excluding self)
        qs = Source.objects.filter(citation_key__startswith=base).exclude(pk=self.pk)
        existing = set(qs.values_list("citation_key", flat=True))

        if base not in existing:
            return base

        # Try suffixes a, b, c, ...
        for letter in string.ascii_lowercase:
            candidate = f"{base}{letter}"
            if candidate not in existing:
                return candidate

        return base  # fallback if all 26 letters exhausted

    def _base_abbreviation_without_authors(self):
        """Generate a base abbreviation from title/year (no author data needed)."""
        year_part = f" {self.year}" if self.year else ""
        title_words = (self.title or "").split()
        if title_words:
            return f"{title_words[0]}{year_part}".strip()
        return f"Source{year_part}".strip()

    def save(self, *args, **kwargs):
        if not self.citation_key:
            if self.pk:
                # Existing object: can use full generation with authors
                self.citation_key = self._disambiguated_abbreviation()
            else:
                # First save: generate from title/year, then disambiguate
                base = self._base_abbreviation_without_authors()
                existing = set(
                    Source.objects.filter(citation_key__startswith=base).values_list(
                        "citation_key", flat=True
                    )
                )
                if base not in existing:
                    self.citation_key = base
                else:
                    for letter in string.ascii_lowercase:
                        candidate = f"{base}{letter}"
                        if candidate not in existing:
                            self.citation_key = candidate
                            break
                    else:
                        self.citation_key = base
        super().save(*args, **kwargs)

    def update_abbreviation(self):
        """Regenerate the abbreviation from current authors/year and save."""
        self.citation_key = self._disambiguated_abbreviation()
        self.save(update_fields=["citation_key"])


@receiver(post_save, sender=Source)
def check_url_valid(sender, instance, created, **kwargs):
    if created and instance.url:
        transaction.on_commit(
            lambda: celery.current_app.send_task("check_source_url", (instance.pk,))
        )


@receiver(post_save, sender="bibliography.SourceAuthor")
@receiver(post_delete, sender="bibliography.SourceAuthor")
def update_source_abbreviation_on_author_change(sender, instance, **kwargs):
    """Regenerate source abbreviation when authors are added/removed,
    but only if the current abbreviation looks auto-generated."""
    source = instance.source
    # Only regenerate if the current abbreviation looks auto-generated
    # (title-based fallback from initial save) rather than manually set.
    current = source.citation_key or ""
    title_words = (source.title or "").split()
    title_based = title_words[0] if title_words else "Source"
    if not current or current.startswith(title_based):
        try:
            source.citation_key = source._disambiguated_abbreviation()
            source.save(update_fields=["citation_key"])
        except Exception:
            pass


class SourceAuthor(models.Model):
    source = models.ForeignKey(
        "Source", on_delete=models.CASCADE, related_name="sourceauthors"
    )
    author = models.ForeignKey(
        "Author", on_delete=models.CASCADE, related_name="sourceauthors"
    )
    position = models.PositiveIntegerField()

    class Meta:
        ordering = ["position"]

    def __str__(self):
        return f"{self.author} - Position {self.position}"

    def save(self, *args, **kwargs):
        if self.position < 1:
            raise ValueError("Position must be a positive integer starting from 1.")
            # If this is a new instance (no pk yet), check if one already exists.
        # if self.pk is None:
        #     try:
        #         existing = SourceAuthor.objects.get(source=self.source, author=self.author)
        #         # If it exists, update the primary key to update instead of creating a new record.
        #         self.pk = existing.pk
        #     except SourceAuthor.DoesNotExist:
        #         pass
        super().save(*args, **kwargs)
