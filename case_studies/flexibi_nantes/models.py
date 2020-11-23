from django.contrib.auth.models import User
from django.contrib.gis.db.models import PointField
from django.db import models

from scenario_builder.models import Material, SeasonalDistribution


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
    owner = models.ForeignKey(User, on_delete=models.CASCADE, default=1)
    heated = models.BooleanField(blank=True, null=True)
    lighted = models.BooleanField(blank=True, null=True)
    high_wire = models.BooleanField(blank=True, null=True)
    above_ground = models.BooleanField(blank=True, null=True)
    nb_cycles = models.IntegerField(null=True)
    culture_1 = models.CharField(max_length=20, blank=True, null=True)
    culture_2 = models.CharField(max_length=20, blank=True, null=True)
    culture_3 = models.CharField(max_length=20, blank=True, null=True)
    seasonal_distributions = models.ManyToManyField(SeasonalDistribution)

    def grouped_distributions(self):
        grouped_distributions = {}
        for distribution in self.seasonal_distributions.all():
            feedstock = distribution.material
            if feedstock not in grouped_distributions:
                grouped_distributions[feedstock] = []
            grouped_distributions[feedstock].append({
                'component': distribution.component,
                'distribution': distribution
            })
        return grouped_distributions

    def growth_cycles(self):
        growth_cycles = {}
        if self.culture_1:
            growth_cycles['Cycle 1'] = self.culture_1
        if self.culture_2:
            growth_cycles['Cycle 2'] = self.culture_2
        if self.culture_3:
            growth_cycles['Cycle 3'] = self.culture_3
        return growth_cycles
