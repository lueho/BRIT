import celery
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from utils.models import CRUDUrlsMixin, NamedUserCreatedObject, UserCreatedObject


class Author(UserCreatedObject):
    first_names = models.CharField(max_length=1023, null=True, blank=True)
    middle_names = models.CharField(max_length=1023, null=True, blank=True)
    last_names = models.CharField(max_length=1023, null=True, blank=True)
    suffix = models.CharField(max_length=100, null=True, blank=True)
    preferred_citation = models.CharField(max_length=2046, null=True, blank=True)

    class Meta:
        ordering = ['last_names', 'first_names']

    def __str__(self):
        parts = [part for part in [self.last_names, self.first_names] if part]
        return ', '.join(parts)

    @property
    def bibtex_name(self):
        """Formats the author's name according to BibTeX conventions."""
        name_parts = []
        if self.last_names:
            name_parts.append(self.last_names)
        initials_parts = []
        if self.first_names:
            initials_parts += [name.strip()[0].upper() + '.' for name in self.first_names.split(' ')]
        if self.middle_names:
            initials_parts += [name.strip()[0].upper() + '.' for name in self.middle_names.split(' ')]
        if initials_parts:
            name_parts.append(' '.join(initials_parts))
        if self.suffix:
            name_parts.append(self.suffix)
        return ', '.join(name_parts)

    @property
    def abbreviated_full_name(self):
        """Improved abbreviation handling, respecting middle names and suffix."""
        name = self.last_names if self.last_names else ''
        initials = [name.strip()[0].upper() for name in
                    f"{self.first_names + ' ' if self.first_names else ''}{self.middle_names + ' ' if self.middle_names else ''}".split(
                        ' ') if name]
        if initials:
            name += f', {". ".join(initials)}.'
        if self.suffix:
            name += f', {self.suffix}'
        return name


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
    ('article', 'article'),
    ('dataset', 'dataset'),
    ('book', 'book'),
    ('website', 'website'),
    ('custom', 'custom'),
)


class Source(UserCreatedObject):
    type = models.CharField(max_length=255, choices=SOURCE_TYPES, default='custom')
    authors = models.ManyToManyField(
        Author,
        through='SourceAuthor',
        related_name='sources'
    )
    publisher = models.CharField(max_length=127, blank=True, null=True)
    title = models.CharField(max_length=500)
    journal = models.CharField(max_length=500, blank=True, null=True)
    issue = models.CharField(max_length=255, blank=True, null=True)
    year = models.IntegerField(blank=True, null=True)
    abbreviation = models.CharField(max_length=50)
    abstract = models.TextField(blank=True, null=True)
    licence = models.ForeignKey(Licence, on_delete=models.PROTECT, blank=True, null=True)
    attributions = models.TextField(blank=True, null=True)
    url = models.URLField(max_length=511, blank=True, null=True)
    url_valid = models.BooleanField(default=False)
    url_checked = models.DateField(blank=True, null=True)
    doi = models.CharField(max_length=255, blank=True, null=True)
    last_accessed = models.DateField(blank=True, null=True)

    class Meta:
        verbose_name = 'Source'

    def ordered_authors(self):
        return self.sourceauthors.order_by('position').select_related('author')

    @property
    def authors_ordered(self):
        return [sa.author for sa in self.ordered_authors()]

    def __str__(self):
        return self.abbreviation


@receiver(post_save, sender=Source)
def check_url_valid(sender, instance, created, **kwargs):
    if created:
        celery.current_app.send_task('check_source_url', (instance.pk,))


class SourceAuthor(models.Model):
    source = models.ForeignKey('Source', on_delete=models.CASCADE, related_name='sourceauthors')
    author = models.ForeignKey('Author', on_delete=models.CASCADE, related_name='sourceauthors')
    position = models.PositiveIntegerField()

    class Meta:
        ordering = ['position']
        constraints = [
            models.UniqueConstraint(fields=['source', 'position'], name='unique_source_position'),
            models.UniqueConstraint(fields=['source', 'author'], name='unique_source_author'),
        ]

    def __str__(self):
        return f"{self.author} - Position {self.position}"

    def save(self, *args, **kwargs):
        if self.position < 1:
            raise ValueError("Position must be a positive integer starting from 1.")
        super().save(*args, **kwargs)
