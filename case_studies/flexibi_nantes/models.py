from django.contrib.auth.models import User
from django.contrib.gis.db.models import PointField
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.urls import reverse

from material_manager.models import Material, MaterialComponent, MaterialComponentGroup
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


class GreenhouseGrowthCycle(SeasonalDistribution):
    cycle_number = models.IntegerField(default=1)
    culture = models.CharField(max_length=255, blank=True, default='')
    material = models.ForeignKey(Material, null=True, on_delete=models.CASCADE)
    component = models.ForeignKey(MaterialComponent, blank=True, null=True, on_delete=models.CASCADE)


@receiver(pre_save, sender=GreenhouseGrowthCycle)
def auto_culture(sender, instance, **kwargs):
    """
    Sets the culture equal to the material. At a later stage this might be used to connect different residues to
    the same culture.
    """
    # TODO: This might lead to problems, when the materials are renamed. Find better solution to link residue and culture
    instance.culture = instance.material.name


class GreenhouseManager(models.Manager):

    def types(self):
        types = []
        for greenhouse in self.all():
            d = {
                'heated': greenhouse.heated,
                'lighted': greenhouse.lighted,
                'high_wire': greenhouse.high_wire,
                'above_ground': greenhouse.above_ground
            }
            culture_types = greenhouse.cultures()
            d.update(culture_types)
            types.append(d)
        return types

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

    objects = GreenhouseManager()

    def add_growth_cycle(self, material):
        cycle_number = self.number_of_growth_cycles() + 1
        for component in MaterialComponentGroup.objects.get(name='Macro Components').materialcomponent_set.filter(
                material=material):
            cycle = GreenhouseGrowthCycle.objects.create(cycle_number=cycle_number, material=material,
                                                         component=component)
            self.growth_cycles.add(cycle)

    def components(self):
        return [growth_cycle.component for growth_cycle in self.growth_cycles.all()]

    @property
    def configuration(self):
        config = []
        config.append('Heated') if self.heated else config.append('Not heated')
        config.append('Lighting') if self.lighted else config.append('No lighting')
        config.append('Above ground') if self.above_ground else config.append('On ground')
        config.append('High wire') if self.high_wire else config.append('Classic')
        return config

    def cultures(self):
        cultures = {}
        for growth_cycle in self.growth_cycles.all():
            name = f'culture_{growth_cycle.cycle_number}'
            cultures[name] = growth_cycle.culture
        return cultures

    def remove_growth_cycle(self, cycle_number):
        for distribution in self.growth_cycles.filter(cycle_number=cycle_number):
            self.growth_cycles.remove(distribution)
            distribution.delete()

    def number_of_growth_cycles(self):
        if self.growth_cycles.all().aggregate(models.Max('cycle_number'))['cycle_number__max']:
            return self.growth_cycles.all().aggregate(models.Max('cycle_number'))['cycle_number__max']
        else:
            return 0

    def grouped_growth_cycles(self):
        grouped_growth_cycles = {}
        for cycle_number in range(1, self.number_of_growth_cycles() + 1):
            for component_distribution in self.growth_cycles.filter(cycle_number=cycle_number):
                if cycle_number not in grouped_growth_cycles:
                    grouped_growth_cycles[cycle_number] = {
                        component_distribution.material: []
                    }
                grouped_growth_cycles[cycle_number][component_distribution.material].append(component_distribution)
        return grouped_growth_cycles

    def get_absolute_url(self):
        return reverse('greenhouse_detail', kwargs={'pk': self.id})
