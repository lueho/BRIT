import celery
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from utils.object_management.models import NamedUserCreatedObject, UserCreatedObject


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


class Source(UserCreatedObject):
    type = models.CharField(max_length=255, choices=SOURCE_TYPES, default="custom")
    authors = models.ManyToManyField(
        Author, through="SourceAuthor", related_name="sources"
    )
    publisher = models.CharField(max_length=127, blank=True, null=True)
    title = models.CharField(max_length=500)
    journal = models.CharField(max_length=500, blank=True, null=True)
    issue = models.CharField(max_length=255, blank=True, null=True)
    year = models.IntegerField(blank=True, null=True)
    abbreviation = models.CharField(max_length=50)
    abstract = models.TextField(blank=True, null=True)
    licence = models.ForeignKey(
        Licence, on_delete=models.PROTECT, blank=True, null=True
    )
    attributions = models.TextField(blank=True, null=True)
    url = models.URLField(max_length=511, blank=True, null=True)
    url_valid = models.BooleanField(default=False)
    url_checked = models.DateField(blank=True, null=True)
    doi = models.CharField(max_length=255, blank=True, null=True)
    last_accessed = models.DateField(blank=True, null=True)

    class Meta:
        verbose_name = "Source"

    def ordered_authors(self):
        return self.sourceauthors.order_by("position").select_related("author")

    @property
    def authors_ordered(self):
        return [sa.author for sa in self.ordered_authors()]

    def __str__(self):
        return self.abbreviation


@receiver(post_save, sender=Source)
def check_url_valid(sender, instance, created, **kwargs):
    if created:
        celery.current_app.send_task("check_source_url", (instance.pk,))


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
