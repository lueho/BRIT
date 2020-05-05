from django.contrib.auth.models import User
from django.contrib.gis.db.models import MultiPolygonField, PointField
from django.db import models

TYPES = (
    ('administrative', 'administrative'),
    ('custom', 'custom'),
)


class Region(models.Model):
    name = models.CharField(max_length=56, null=False)
    country = models.CharField(max_length=56, null=False)
    geom = MultiPolygonField(null=True)

    def __str__(self):
        return self.name


class Catchment(models.Model):
    name = models.CharField(max_length=256, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, null=True)
    description = models.TextField(blank=True, null=True)
    type = models.CharField(max_length=14, choices=TYPES, default='custom', null=True)
    geom = MultiPolygonField(null=True)

    def __str__(self):
        return self.name


class Material(models.Model):
    name = models.CharField(max_length=28)
    description = models.TextField(blank=True, null=True)
    is_feedstock = models.BooleanField(default=False)
    stan_flow_id = models.IntegerField()

    def __str__(self):
        return self.name


class MaterialComponent(models.Model):
    name = models.CharField(max_length=20)
    description = models.TextField(blank=True, null=True)
    average = models.FloatField()
    standard_deviation = models.FloatField(null=True)
    source = models.CharField(max_length=20)
    material = models.ForeignKey(Material, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class SFBSite(models.Model):
    name = models.CharField(max_length=20, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    geom = PointField(null=True)

    def __str__(self):
        return self.name


class Scenario(models.Model):
    name = models.CharField(max_length=56, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    description = models.TextField(blank=True, null=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, null=True)
    site = models.ForeignKey(SFBSite, on_delete=models.CASCADE, null=True)
    catchment = models.ForeignKey(Catchment, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return self.name


class GeoDataset(models.Model):
    name = models.CharField(max_length=56, null=False)
    description = models.TextField(blank=True, null=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, null=False)
    table_name = models.CharField(max_length=56, null=False)

    def __str__(self):
        return self.name


class TreesHhRoadside(models.Model):
    geom = PointField(blank=True, null=True)
    baumid = models.IntegerField(blank=True, null=True)
    gattung_deutsch = models.CharField(max_length=15, blank=True, null=True)
    art_deutsch = models.CharField(max_length=15, blank=True, null=True)
    sorte_deutsch = models.CharField(max_length=15, blank=True, null=True)
    pflanzjahr = models.IntegerField(blank=True, null=True)
    kronendurchmesser = models.IntegerField(blank=True, null=True)
    stammumfang = models.IntegerField(blank=True, null=True)
    strasse = models.CharField(max_length=56, blank=True, null=True)
    hausnummer = models.CharField(max_length=10, blank=True, null=True)
    ortsteil_nr = models.CharField(max_length=5, blank=True, null=True)
    stadtteil = models.CharField(max_length=15, blank=True, null=True)
    bezirk = models.CharField(max_length=15, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'trees_hh_roadside'


class InventoryAlgorithm(models.Model):
    name = models.CharField(max_length=30)
    class_name = models.CharField(max_length=30, null=True)
    description = models.TextField(blank=True, null=True)
    geodataset = models.ForeignKey(GeoDataset, on_delete=models.CASCADE)
    material = models.ForeignKey(Material, on_delete=models.CASCADE)


class InventoryAlgorithmParameter(models.Model):
    name = models.CharField(max_length=30)
    description = models.TextField(blank=True, null=True)
    inventory_algorithm = models.ForeignKey(InventoryAlgorithm, on_delete=models.CASCADE, null=True)
    value = models.FloatField()
    unit = models.CharField(max_length=30, blank=True, null=True)
