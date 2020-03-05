from django.contrib.gis.db.models import PointField
from django.db import models

    
class HamburgRoadsideTrees(models.Model):
    geom = PointField(blank=True, null=True)
    baumid = models.IntegerField(blank=True, null=True)
    gattung_latein = models.CharField(max_length=20, blank=True, null=True)
    gattung_deutsch = models.CharField(max_length=20, blank=True, null=True)
    art_latein = models.CharField(max_length=20, blank=True, null=True)
    art_deutsch = models.CharField(max_length=20, blank=True, null=True)
    pflanzjahr = models.IntegerField(blank=True, null=True)
    kronendurchmesser = models.IntegerField(blank=True, null=True)
    stammumfang = models.IntegerField(blank=True, null=True)
    strasse = models.CharField(max_length=50, blank=True, null=True)
    hausnummer = models.CharField(max_length=10, blank=True, null=True)
    ortsteil_nr = models.CharField(max_length=10, blank=True, null=True)
    stadtteil = models.CharField(max_length=30, blank=True, null=True)
    bezirk = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'trees_hh_roadside'
    
    @property
    def lat_lng(self):
        return list(getattr(self.geom, 'coords', [])[::-1])