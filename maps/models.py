from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.contrib.gis.db.models import MultiPolygonField, PointField

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
    ('NutsRegion', 'NutsRegion'),
    ('WasteCollection', 'WasteCollection')
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

    def __str__(self):
        try:
            return self.nutsregion.__str__()
        except Region.nutsregion.RelatedObjectDoesNotExist:
            return self.name


class NutsRegion(Region):
    nuts_id = models.CharField(max_length=5, blank=True, null=True)
    levl_code = models.IntegerField(blank=True, null=True)
    cntr_code = models.CharField(max_length=2, blank=True, null=True)
    name_latn = models.CharField(max_length=70, blank=True, null=True)
    nuts_name = models.CharField(max_length=106, blank=True, null=True)
    mount_type = models.IntegerField(blank=True, null=True)
    urbn_type = models.IntegerField(blank=True, null=True)
    coast_type = models.IntegerField(blank=True, null=True)
    parent = models.ForeignKey('self', related_name='children', on_delete=models.PROTECT, null=True)

    @property
    def pedigree(self):
        pedigree = {}

        # add parents
        instance = self
        for lvl in range(self.levl_code, -1, -1):
            pedigree[f'qs_{lvl}'] = NutsRegion.objects.filter(id=instance.id)
            instance = instance.parent

        # add children
        for lvl in range(self.levl_code + 1, 4):
            pedigree[f'qs_{lvl}'] = NutsRegion.objects.filter(levl_code=lvl, nuts_id__startswith=self.nuts_id)

        return pedigree

    def __str__(self):
        return f'{self.nuts_name} ({self.nuts_id})'


class Catchment(NamedUserObjectModel):
    parent_region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='child_catchments', null=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, null=True)
    type = models.CharField(max_length=14, choices=TYPES, default='custom')

    @property
    def geom(self):
        return self.region.geom

    @property
    def nutsregion_pk(self):
        try:
            return self.region.nutsregion.pk
        except Region.nutsregion.RelatedObjectDoesNotExist:
            return None

    @property
    def nuts_lvl(self):
        try:
            return self.region.nutsregion.levl_code
        except Region.nutsregion.RelatedObjectDoesNotExist:
            return None

    @staticmethod
    def get_absolute_url():
        return reverse('catchment_list')

    def __str__(self):
        return self.region.__str__()


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
        return reverse(f'{self.model_name}')

    def __str__(self):
        return self.name
