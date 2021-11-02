from django.db import models
from django.urls import reverse
from django.contrib.gis.db.models import MultiPolygonField, PointField

from django.contrib.auth.models import User
from bibliography.models import Source

TYPES = (
    ('administrative', 'administrative'),
    ('custom', 'custom'),
)

GIS_SOURCE_MODELS = (
    ('HamburgRoadsideTrees', 'HamburgRoadsideTrees'),
    ('HamburgGreenAreas', 'HamburgGreenAreas'),
    ('NantesGreenhouses', 'NantesGreenhouses')
)


class Region(models.Model):
    name = models.CharField(max_length=56, null=False)
    country = models.CharField(max_length=56, null=False)
    geom = MultiPolygonField(null=True)

    @staticmethod
    def get_absolute_url():
        return reverse('catchment_list')

    def __str__(self):
        return self.name


class Catchment(models.Model):
    name = models.CharField(max_length=256, default="Custom Catchment")
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    description = models.TextField(blank=True, null=True)
    type = models.CharField(max_length=14, choices=TYPES, default='custom')
    geom = MultiPolygonField()

    @staticmethod
    def get_absolute_url():
        return reverse('catchment_list')

    def __str__(self):
        return self.name


class SFBSite(models.Model):
    name = models.CharField(max_length=20, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    geom = PointField(null=True)

    def __str__(self):
        return self.name


class GeoDataset(models.Model):
    """
    Holds meta information about datasets from the core module or scenario extensions.
    """
    name = models.CharField(max_length=56, null=False)
    preview = models.ImageField(upload_to='images', default='img/generic_map.png')
    publish = models.BooleanField(default=False)
    description = models.TextField(blank=True, null=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, null=False)
    model_name = models.CharField(max_length=56, choices=GIS_SOURCE_MODELS, null=True)
    sources = models.ManyToManyField(Source)

    def get_absolute_url(self):
        return reverse(f'{self.model_name}')

    def __str__(self):
        return self.name
