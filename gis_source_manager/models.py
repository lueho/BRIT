from django.contrib.gis.db.models import PointField, MultiPolygonField
from django.db import models


class HamburgRoadsideTrees(models.Model):
    geom = PointField(blank=True, null=True)
    baumid = models.IntegerField(blank=True, null=True)
    gattung = models.CharField(max_length=63, blank=True, null=True)
    gattung_latein = models.CharField(max_length=63, blank=True, null=True)
    gattung_deutsch = models.CharField(max_length=63, blank=True, null=True)
    art = models.CharField(max_length=63, blank=True, null=True)
    art_latein = models.CharField(max_length=63, blank=True, null=True)
    art_deutsch = models.CharField(max_length=63, blank=True, null=True)
    sorte_latein = models.CharField(max_length=63, blank=True, null=True)
    sorte_deutsch = models.CharField(max_length=63, blank=True, null=True)
    pflanzjahr = models.IntegerField(blank=True, null=True)
    pflanzjahr_portal = models.IntegerField(blank=True, null=True)
    kronendurchmesser = models.IntegerField(blank=True, null=True)
    stammumfang = models.IntegerField(blank=True, null=True)
    strasse = models.CharField(max_length=63, blank=True, null=True)
    hausnummer = models.CharField(max_length=63, blank=True, null=True)
    ortsteil_nr = models.CharField(max_length=63, blank=True, null=True)
    stadtteil = models.CharField(max_length=63, blank=True, null=True)
    bezirk = models.CharField(max_length=63, blank=True, null=True)


class HamburgGreenAreas(models.Model):
    geom = MultiPolygonField(srid=25832, blank=True, null=True)
    quelle_daten = models.CharField(max_length=63, blank=True, null=True)
    identnummer = models.CharField(max_length=63, blank=True, null=True)
    dgpkey = models.IntegerField(blank=True, null=True)
    anlagenname = models.CharField(max_length=63, blank=True, null=True)
    belegenheit = models.CharField(max_length=63, blank=True, null=True)
    eigentum = models.CharField(max_length=63, blank=True, null=True)
    bezirksnummer = models.IntegerField(blank=True, null=True)
    ortsteil = models.IntegerField(blank=True, null=True)
    flaeche_qm = models.FloatField(blank=True, null=True)
    flaeche_ha = models.FloatField(blank=True, null=True)
    gruenart = models.CharField(max_length=63, blank=True, null=True)
    nutzcode = models.IntegerField(blank=True, null=True)
    stand = models.CharField(max_length=63, blank=True, null=True)
