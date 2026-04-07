from django.contrib.gis.db.models import MultiPolygonField
from django.db import models
from django.urls import reverse


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

    class Meta:
        db_table = "urban_green_spaces_hamburggreenareas"

    @staticmethod
    def get_absolute_url():
        return reverse("HamburgGreenAreas")


__all__ = ["HamburgGreenAreas"]
