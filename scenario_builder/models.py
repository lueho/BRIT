from django.contrib.gis.db.models import PolygonField
from django.db import models

TYPES = (
    ('administrative', 'administrative'),
    ('custom', 'custom'),
)


class Catchment(models.Model):
    title = models.CharField(max_length=256)
    description = models.TextField()
    type = models.CharField(max_length=14, choices=TYPES, default='custom')
    geom = PolygonField()

    def __unicode__(self):
        return self.title
