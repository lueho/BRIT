from django.db import models

from brit.models import OwnedObjectModel, CRUDUrlsMixin


class Licence(models.Model):
    name = models.CharField(max_length=255)
    reference_url = models.URLField()

    def __str(self):
        return self.name


SOURCE_TYPES = (
    ('article', 'article'),
    ('dataset', 'dataset'),
    ('book', 'book'),
    ('website', 'website'),
    ('custom', 'custom'),
    ('waste_flyer', 'waste_flyer')
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
            'Last accessed:': {'type': 'text', 'text': self.last_accessed},
        }
        if self.doi:
            d['DOI:'] = {'type': 'link', 'href': f'https://doi.org/{self.doi}', 'text': self.doi}
        if self.licence:
            d['License:'] = {'type': 'link', 'href': self.licence.reference_url, 'text': self.licence.name}
        d['Attributions:'] = {'type': 'text', 'text': self.attributions}
        return d

    def __str__(self):
        return self.abbreviation
