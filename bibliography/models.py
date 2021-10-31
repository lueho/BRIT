from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse


class Licence(models.Model):
    name = models.CharField(max_length=255)
    reference_url = models.URLField()

    def __str(self):
        return self.name


SOURCE_TYPES = (
    ('article', 'article'),
    ('dataset', 'dataset'),
    ('website', 'website'),
    ('custom', 'custom'),
)


class Source(models.Model):
    owner = models.ForeignKey(User, default=8, on_delete=models.CASCADE)
    type = models.CharField(max_length=255, choices=SOURCE_TYPES, default='custom')
    authors = models.CharField(max_length=500, null=True)
    publisher = models.CharField(max_length=127, blank=True, null=True)
    title = models.CharField(max_length=500, null=True)
    journal = models.CharField(max_length=500, null=True)
    issue = models.CharField(max_length=255, blank=True, null=True)
    year = models.IntegerField(null=True)
    abbreviation = models.CharField(max_length=50, null=True)
    abstract = models.TextField(blank=True, null=True)
    licence = models.ForeignKey(Licence, on_delete=models.PROTECT, blank=True, null=True)
    attributions = models.TextField(blank=True, null=True)
    url = models.URLField(blank=True, null=True)
    doi = models.CharField(max_length=255, blank=True, null=True)
    last_accessed = models.DateField(blank=True, null=True)

    def get_absolute_url(self):
        return reverse('literature source_detail', kwargs={'pk': self.id})

    def __str__(self):
        return self.abbreviation
