from django.contrib.gis.db.models import PointField
from django.db import models

from scenario_builder.models import SeasonalDistribution


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

    class Meta:
        db_table = 'gis_source_manager_nantesgreenhouses'


class Greenhouse(models.Model):
    heated = models.BooleanField(blank=True, null=True)
    lighted = models.BooleanField(blank=True, null=True)
    high_wire = models.BooleanField(blank=True, null=True)
    above_ground = models.BooleanField(blank=True, null=True)
    seasonal_distribution = models.ForeignKey(SeasonalDistribution, on_delete=models.CASCADE, null=True)
