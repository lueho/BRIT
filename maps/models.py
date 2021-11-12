from django.db import models
from django.urls import reverse
from django.contrib.gis.db.models import MultiPolygonField, PointField

from django.contrib.auth.models import User
from bibliography.models import Source

from brit.models import NamedUserObjectModel

TYPES = (
    ('administrative', 'administrative'),
    ('custom', 'custom'),
)

GIS_SOURCE_MODELS = (
    ('HamburgRoadsideTrees', 'HamburgRoadsideTrees'),
    ('HamburgGreenAreas', 'HamburgGreenAreas'),
    ('NantesGreenhouses', 'NantesGreenhouses'),
    ('NutsRegion', 'NutsRegion')
)


class GeoPolygon(models.Model):
    fid = models.BigAutoField(primary_key=True)
    geom = MultiPolygonField(blank=True, null=True)


class Region(NamedUserObjectModel):
    country = models.CharField(max_length=56, null=False)
    borders = models.ForeignKey(GeoPolygon, on_delete=models.PROTECT, null=True)

    @property
    def geom(self):
        return self.borders.geom

    @staticmethod
    def get_absolute_url():
        return reverse('catchment_list')


class NutsRegion(Region):
    nuts_id = models.CharField(max_length=5, blank=True, null=True)
    levl_code = models.IntegerField(blank=True, null=True)
    cntr_code = models.CharField(max_length=2, blank=True, null=True)
    name_latn = models.CharField(max_length=70, blank=True, null=True)
    nuts_name = models.CharField(max_length=106, blank=True, null=True)
    mount_type = models.IntegerField(blank=True, null=True)
    urbn_type = models.IntegerField(blank=True, null=True)
    coast_type = models.IntegerField(blank=True, null=True)


class Catchment(NamedUserObjectModel):
    parent_region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='parent_region', null=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, null=True)
    type = models.CharField(max_length=14, choices=TYPES, default='custom')

    @property
    def geom(self):
        return self.region.geom

    @staticmethod
    def get_absolute_url():
        return reverse('catchment_list')


class SFBSite(NamedUserObjectModel):
    geom = PointField(null=True)


class GeoDataset(NamedUserObjectModel):
    """
    Holds meta information about datasets from the core module or scenario extensions.
    """
    preview = models.ImageField(upload_to='images', default='img/generic_map.png')
    publish = models.BooleanField(default=False)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, null=False)
    model_name = models.CharField(max_length=56, choices=GIS_SOURCE_MODELS, null=True)
    sources = models.ManyToManyField(Source)

    def get_absolute_url(self):
        return reverse(f'{self.model_name}', args=[self.id])

    def __str__(self):
        return self.name
