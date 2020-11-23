from django.contrib.auth.models import User
from django.contrib.gis.db.models import PointField
from django.db import models
from django.urls import reverse

from scenario_builder.models import Material, MaterialComponent, MaterialComponentGroup, SeasonalDistribution


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


class GreenhouseGrowthCycle(SeasonalDistribution):
    cycle_number = models.IntegerField(default=1)
    material = models.ForeignKey(Material, null=True, on_delete=models.CASCADE)
    component = models.ForeignKey(MaterialComponent, blank=True, null=True, on_delete=models.CASCADE)


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
    growth_cycles = models.ManyToManyField(GreenhouseGrowthCycle)

    def add_growth_cycle(self, material):
        cycle_number = self.number_of_growth_cycles() + 1
        for component in MaterialComponentGroup.objects.get(name='Macro Components').materialcomponent_set.filter(material=material):
            cycle = GreenhouseGrowthCycle.objects.create(cycle_number=cycle_number, material=material, component=component)
            self.growth_cycles.add(cycle)

    def remove_growth_cycle(self, cycle_number):
        for distribution in self.growth_cycles.filter(cycle_number=cycle_number):
            self.growth_cycles.remove(distribution)
            distribution.delete()


    def number_of_growth_cycles(self):
        return self.growth_cycles.all().aggregate(models.Max('cycle_number'))['cycle_number__max']

    def grouped_growth_cycles(self):
        grouped_growth_cycles = {}
        for cycle_number in range(1, self.number_of_growth_cycles() + 1):
            for distribution in self.growth_cycles.filter(cycle_number=cycle_number):
                if cycle_number not in grouped_growth_cycles:
                    grouped_growth_cycles[cycle_number] = {
                        distribution.material: []
                    }
                grouped_growth_cycles[cycle_number][distribution.material].append({
                    'component': distribution.component,
                    'distribution': distribution
                })
        return grouped_growth_cycles

    def get_absolute_url(self):
        return reverse('greenhouse_detail', kwargs={'pk': self.id})

