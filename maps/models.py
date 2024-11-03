from django.contrib.gis.db.models import MultiPolygonField, PointField
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.urls import reverse
from tree_queries.models import TreeNode
from tree_queries.query import TreeQuerySet

from bibliography.models import Source
from utils.models import NamedUserObjectModel, OwnedObjectQuerySet

TYPES = (
    ('administrative', 'administrative'),
    ('custom', 'custom'),
    ('nuts', 'nuts'),
    ('lau', 'lau'),
)

GIS_SOURCE_MODELS = (
    ('HamburgRoadsideTrees', 'HamburgRoadsideTrees'),
    ('HamburgGreenAreas', 'HamburgGreenAreas'),
    ('NantesGreenhouses', 'NantesGreenhouses'),
    ('NutsRegion', 'NutsRegion'),
    ('WasteCollection', 'WasteCollection')
)


class Location(NamedUserObjectModel):
    geom = PointField(null=True)
    address = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = 'Location'

    def __str__(self):
        return f"{self.name}{' at ' + self.address if self.address else ''}"


class GeoPolygon(models.Model):
    fid = models.BigAutoField(primary_key=True)
    geom = MultiPolygonField(blank=True, null=True)


class Region(NamedUserObjectModel):
    country = models.CharField(max_length=56, null=False)
    borders = models.ForeignKey(GeoPolygon, on_delete=models.PROTECT, null=True)
    composed_of = models.ManyToManyField('self', symmetrical=False, related_name='composing_regions', blank=True)

    @property
    def geom(self):
        return self.borders.geom

    @property
    def country_code(self):
        try:
            return self.nutsregion.cntr_code
        except Region.nutsregion.RelatedObjectDoesNotExist:
            pass
        try:
            return self.lauregion.cntr_code
        except Region.lauregion.RelatedObjectDoesNotExist:
            return None

    @property
    def nuts_or_lau_id(self):
        try:
            return self.nutsregion.nuts_id
        except Region.nutsregion.RelatedObjectDoesNotExist:
            pass
        try:
            return self.lauregion.lau_id
        except Region.lauregion.RelatedObjectDoesNotExist:
            return None

    def __str__(self):
        try:
            return self.nutsregion.__str__()
        except Region.nutsregion.RelatedObjectDoesNotExist:
            pass
        try:
            return self.lauregion.__str__()
        except Region.lauregion.RelatedObjectDoesNotExist:
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
        if self.levl_code == 3:
            pedigree[f'qs_4'] = self.lau_children.all()

        return pedigree

    def __str__(self):
        return f'{self.nuts_name} ({self.nuts_id})'


class LauRegion(Region):
    cntr_code = models.CharField(max_length=2, blank=True, null=True)
    lau_id = models.CharField(max_length=13, blank=True, null=True)
    lau_name = models.CharField(max_length=113, blank=True, null=True)
    year = models.IntegerField(blank=True, null=True)
    nuts_parent = models.ForeignKey(NutsRegion, related_name='lau_children', on_delete=models.PROTECT, null=True)

    def __str__(self):
        return f'{self.lau_name} ({self.lau_id})'


class CatchmentQueryset(OwnedObjectQuerySet, TreeQuerySet):
    pass


class CatchmentManager(models.Manager):
    def get_queryset(self):
        return CatchmentQueryset(self.model, using=self._db)

    def descendants(self, *args, **kwargs):
        return self.get_queryset().descendants(*args, **kwargs)

    def ancestors(self, *args, **kwargs):
        return self.get_queryset().ancestors(*args, **kwargs)


class Catchment(NamedUserObjectModel, TreeNode):
    parent_region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='child_catchments', null=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, null=True)
    type = models.CharField(max_length=14, choices=TYPES, default='custom')

    objects = CatchmentManager()

    @property
    def geom(self):
        return self.region.geom

    @property
    def level(self):
        if hasattr(self.region, 'nutsregion'):
            return self.region.nutsregion.levl_code
        if hasattr(self.region, 'lauregion'):
            return 4

    def __str__(self):
        return self.name if self.name else self.region.__str__()


@receiver(post_delete, sender=Catchment)
def delete_unused_custom_region(sender, instance, **kwargs):
    if not instance.region.catchment_set.exists() and instance.type == 'custom':
        instance.region.delete()


class GeoDataset(NamedUserObjectModel):
    """
    Holds meta information about datasets from the core module or scenario extensions.
    """
    preview = models.ImageField(upload_to='maps_geodataset/', default='generic_map.png')
    publish = models.BooleanField(default=False)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, null=False)
    model_name = models.CharField(max_length=56, choices=GIS_SOURCE_MODELS, null=True)
    sources = models.ManyToManyField(Source, related_name='geodatasets')
    resources = models.ManyToManyField(Source, related_name='resource_to_geodatasets')

    def get_absolute_url(self):
        return reverse(f'{self.model_name}')

    def __str__(self):
        return self.name


class Attribute(NamedUserObjectModel):
    """
    Defines an attribute class that can be attached to features of a map.
    """
    unit = models.CharField(max_length=127)

    def __str__(self):
        return f'{self.name} [{self.unit}]'


class RegionAttributeValue(NamedUserObjectModel):
    """
    Attaches a value of an attribute class to a region
    """
    region = models.ForeignKey(Region, on_delete=models.PROTECT)
    attribute = models.ForeignKey(Attribute, on_delete=models.PROTECT)
    date = models.DateField(blank=True, null=True)
    value = models.FloatField(default=0.0)
    standard_deviation = models.FloatField(default=0.0, blank=True, null=True)


class RegionAttributeTextValue(NamedUserObjectModel):
    """
    Attaches a category value of an attribute class to a region
    """
    region = models.ForeignKey(Region, on_delete=models.PROTECT)
    attribute = models.ForeignKey(Attribute, on_delete=models.PROTECT)
    date = models.DateField(blank=True, null=True)
    value = models.CharField(max_length=511)
