import requests
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone

from brit.models import OwnedObjectModel, CRUDUrlsMixin, NamedUserObjectModel


class Author(CRUDUrlsMixin, OwnedObjectModel):
    first_names = models.CharField(max_length=1023)
    last_names = models.CharField(max_length=1023)

    def __str__(self):
        return f'{self.first_names} {self.last_names}'


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
    # ('waste_flyer', 'waste_flyer')
)


class Source(CRUDUrlsMixin, OwnedObjectModel):
    type = models.CharField(max_length=255, choices=SOURCE_TYPES, default='custom')
    authors = models.CharField(max_length=500, blank=True, null=True)
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

    def as_dict(self):
        d = {
            'Author(s):': {'type': 'text', 'text': self.authors},
            'Title:': {'type': 'text', 'text': self.title},
            'Publisher:': {'type': 'text', 'text': self.publisher},
            'Journal:': {'type': 'text', 'text': self.journal},
            'Issue:': {'type': 'text', 'text': self.issue},
            'Year:': {'type': 'text', 'text': self.year},
            'Abstract:': {'type': 'text', 'text': self.abstract},
            'URL:': {'type': 'link', 'href': self.url, 'text': self.url},
            'url valid': {'type': 'text', 'text': f'{self.url_valid} ({self.url_checked.strftime("%d.%m.%Y")})'},
            'Last accessed:': {'type': 'text', 'text': self.last_accessed},
        }
        if self.doi:
            d['DOI:'] = {'type': 'link', 'href': f'https://doi.org/{self.doi}', 'text': self.doi}
        if self.licence:
            d['License:'] = {'type': 'link', 'href': self.licence.reference_url, 'text': self.licence.name}
        d['Attributions:'] = {'type': 'text', 'text': self.attributions}
        return d

    def check_url(self):
        if not self.url:
            return False
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20200101 Firefox/84.0',
            'Accept-Language': 'en-GB,en;q=0.5',
            'Referer': 'https://www.wikipedia.org',
            'DNT': '1'
        }
        try:
            response = requests.head(self.url, headers=headers, allow_redirects=True)
        except requests.exceptions.RequestException:
            return False
        else:
            if response.status_code == 405:
                response = requests.get(self.url, headers=headers, allow_redirects=True)
            return response.status_code == 200

    def __str__(self):
        return self.abbreviation


@receiver(pre_save, sender=Source)
def check_url_valid(sender, instance, **kwargs):
    instance.url_valid = instance.check_url()
    instance.url_checked = timezone.now()
