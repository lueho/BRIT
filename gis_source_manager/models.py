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
    geom = MultiPolygonField(srid=4326, blank=True, null=True)
    quelle_daten = models.CharField(max_length=200, blank=True, null=True)
    identnummer = models.CharField(max_length=63, blank=True, null=True)
    dgpkey = models.IntegerField(blank=True, null=True)
    anlagenname = models.CharField(max_length=200, blank=True, null=True)
    belegenheit = models.CharField(max_length=200, blank=True, null=True)
    eigentum = models.CharField(max_length=200, blank=True, null=True)
    bezirksnummer = models.IntegerField(blank=True, null=True)
    ortsteil = models.IntegerField(blank=True, null=True)
    flaeche_qm = models.FloatField(blank=True, null=True)
    flaeche_ha = models.FloatField(blank=True, null=True)
    gruenart = models.CharField(max_length=200, blank=True, null=True)
    nutzcode = models.IntegerField(blank=True, null=True)
    stand = models.CharField(max_length=63, blank=True, null=True)

    # class Meta:
    # managed = False
    # db_table = 'trees_hh_parks'


class NantesGreenhouses(models.Model):
    geom = PointField(blank=True, null=True)
    id_exp = models.CharField(max_length=255, blank=True, null=True)
    nom_exp = models.CharField(max_length=255, blank=True, null=True)
    id_serre = models.CharField(max_length=255, blank=True, null=True)
    lat = models.FloatField(blank=True, null=True)
    lon = models.FloatField(blank=True, null=True)
    surface_ha = models.FloatField(max_length=255, blank=True, null=True)
    nb_cycles = models.IntegerField(blank=True, null=True)
    culture_1 = models.CharField(max_length=20, blank=True, null=True)
    start_cycle_1 = models.CharField(max_length=20, blank=True, null=True)
    end_cycle_1 = models.CharField(max_length=20, blank=True, null=True)
    culture_2 = models.CharField(max_length=20, blank=True, null=True)
    start_cycle_2 = models.CharField(max_length=20, blank=True, null=True)
    end_cycle_2 = models.CharField(max_length=20, blank=True, null=True)
    culture_3 = models.CharField(max_length=20, blank=True, null=True)
    start_cycle_3 = models.CharField(max_length=20, blank=True, null=True)
    end_cycle_3 = models.CharField(max_length=20, blank=True, null=True)
    layer = models.CharField(max_length=20, blank=True, null=True)
    heated = models.BooleanField(blank=True, null=True)
    lighted = models.BooleanField(blank=True, null=True)
    high_wire = models.BooleanField(blank=True, null=True)
    above_ground = models.BooleanField(blank=True, null=True)
