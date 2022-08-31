from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from brit.models import OwnedObjectModel, CRUDUrlsMixin, NamedUserObjectModel
import celery


class Author(CRUDUrlsMixin, OwnedObjectModel):
    first_names = models.CharField(max_length=1023, null=True, blank=True)
    last_names = models.CharField(max_length=1023, null=True, blank=True)

    def __str__(self):
        name = ''
        if self.last_names:
            name += self.last_names
        if self.first_names:
            name += f', {self.first_names}'
        return name


class Licence(NamedUserObjectModel):
    reference_url = models.URLField()

    def __str__(self):
        return self.name


SOURCE_TYPES = (
    ('article', 'article'),
    ('dataset', 'dataset'),
    ('book', 'book'),
    ('website', 'website'),
    ('custom', 'custom'),
)


class Source(CRUDUrlsMixin, OwnedObjectModel):
    type = models.CharField(max_length=255, choices=SOURCE_TYPES, default='custom')
    authors = models.ManyToManyField(Author, related_name='sources')
    publisher = models.CharField(max_length=127, blank=True, null=True)
    title = models.CharField(max_length=500, null=True)
    journal = models.CharField(max_length=500, blank=True, null=True)
    issue = models.CharField(max_length=255, blank=True, null=True)
    year = models.IntegerField(null=True)
    abbreviation = models.CharField(max_length=50, null=True)
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

    def __str__(self):
        return self.abbreviation


@receiver(post_save, sender=Source)
def check_url_valid(sender, instance, created, **kwargs):
    if created:
        celery.current_app.send_task('check_source_url', (instance.pk,))
