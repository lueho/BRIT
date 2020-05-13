from django.contrib.gis.db.models import PointField
from django.db import models

GIS_SOURCE_MODELS = (
    ('HamburgRoadsideTrees', 'HamburgRoadsideTrees'),
)


class HamburgRoadsideTrees(models.Model):
    geom = PointField(blank=True, null=True)
    baumid = models.IntegerField(blank=True, null=True)
    gattung = models.CharField(max_length=56, blank=True, null=True)
    gattung_latein = models.CharField(max_length=56, blank=True, null=True)
    gattung_deutsch = models.CharField(max_length=56, blank=True, null=True)
    art = models.CharField(max_length=56, blank=True, null=True)
    art_latein = models.CharField(max_length=56, blank=True, null=True)
    art_deutsch = models.CharField(max_length=56, blank=True, null=True)
    sorte_latein = models.CharField(max_length=56, blank=True, null=True)
    sorte_deutsch = models.CharField(max_length=56, blank=True, null=True)
    pflanzjahr = models.IntegerField(blank=True, null=True)
    pflanzjahr_portal = models.IntegerField(blank=True, null=True)
    kronendurchmesser = models.IntegerField(blank=True, null=True)
    stammumfang = models.IntegerField(blank=True, null=True)
    strasse = models.CharField(max_length=56, blank=True, null=True)
    hausnummer = models.CharField(max_length=56, blank=True, null=True)
    ortsteil_nr = models.CharField(max_length=56, blank=True, null=True)
    stadtteil = models.CharField(max_length=56, blank=True, null=True)
    bezirk = models.CharField(max_length=56, blank=True, null=True)


CATALOGUE = {
    'HamburgRoadsideTrees': HamburgRoadsideTrees
}
