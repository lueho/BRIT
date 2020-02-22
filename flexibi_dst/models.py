from django.contrib.gis.db.models import MultiPolygonField
from django.db import models

class Districts_HH(models.Model):
    geom = MultiPolygonField(blank=True, null=True)
    name = models.CharField(max_length=20, blank=True, null=True)
    
    class Meta:
        db_table = 'districts_hh'