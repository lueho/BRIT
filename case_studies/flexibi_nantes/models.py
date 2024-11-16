from django.contrib.auth.models import User
from django.contrib.gis.db.models import PointField
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.urls import reverse

from distributions.models import TemporalDistribution, Timestep
from materials.models import (Composition, Material, MaterialComponent, MaterialComponentGroup, SampleSeries)
from utils.models import NamedUserObjectModel


class NantesGreenhouses(models.Model):
    geom = PointField(blank=True, null=True)
    id_exp = models.CharField(max_length=255, blank=True, null=True)
    nom_exp = models.CharField(max_length=255, blank=True, null=True)
    id_serre = models.CharField(max_length=255, blank=True, null=True)
    lat = models.FloatField(blank=True, null=True)
    lon = models.FloatField(blank=True, null=True)
    surface_ha = models.FloatField(blank=True, null=True)
    nb_cycles = models.IntegerField(blank=True, null=True)
    culture_1 = models.CharField(max_length=255, blank=True, null=True)
    start_cycle_1 = models.CharField(max_length=255, blank=True, null=True)
    end_cycle_1 = models.CharField(max_length=255, blank=True, null=True)
    culture_2 = models.CharField(max_length=255, blank=True, null=True)
    start_cycle_2 = models.CharField(max_length=255, blank=True, null=True)
    end_cycle_2 = models.CharField(max_length=255, blank=True, null=True)
    culture_3 = models.CharField(max_length=255, blank=True, null=True)
    start_cycle_3 = models.CharField(max_length=20, blank=True, null=True)
    end_cycle_3 = models.CharField(max_length=255, blank=True, null=True)
    layer = models.CharField(max_length=255, blank=True, null=True)
    heated = models.BooleanField(blank=True, null=True)
    lighted = models.BooleanField(blank=True, null=True)
    high_wire = models.BooleanField(blank=True, null=True)
    above_ground = models.BooleanField(blank=True, null=True)


class GreenhouseManager(models.Manager):

    def types(self):
        types = []
        for greenhouse in self.all():
            greenhouse_type = {
                'heated': greenhouse.heated,
                'lighted': greenhouse.lighted,
                'high_wire': greenhouse.high_wire,
                'above_ground': greenhouse.above_ground,
            }
            greenhouse_type.update(greenhouse.cultures())
            types.append(greenhouse_type)
        return types


class Greenhouse(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, default=1)
    name = models.CharField(max_length=255, blank=True, null=True)
    heated = models.BooleanField(blank=True, null=True)
    lighted = models.BooleanField(blank=True, null=True)
    high_wire = models.BooleanField(blank=True, null=True)
    above_ground = models.BooleanField(blank=True, null=True)

    objects = GreenhouseManager()

    def components(self):
        return list(set([share.component for share in self.shares]))

    @property
    def shares(self):
        return GrowthShare.objects.filter(timestepset__growth_cycle__greenhouse=self)

    @property
    def growth_cycles(self):
        return self.greenhousegrowthcycle_set.all()

    @property
    def growth_cycle_list(self):
        return [cycle.culture.name for cycle in self.greenhousegrowthcycle_set.all()]

    def sort_growth_cycles(self):
        growth_cycles = list(self.greenhousegrowthcycle_set.all())
        growth_cycles.sort(key=lambda x: x.min_timestep.id)
        for n, c in enumerate(growth_cycles):
            GreenhouseGrowthCycle.objects.filter(pk=c.pk).update(cycle_number=n + 1)

    @property
    def number_of_growth_cycles(self):
        return self.greenhousegrowthcycle_set.count()

    def configuration(self):
        return {gc: {'culture': gc.culture,
                     'timesteps': [t for t in gc.timesteps],
                     'table': gc.table_data} for gc in
                self.greenhousegrowthcycle_set.all().order_by('cycle_number')}

    def cultures(self):
        cultures = {
            'culture_1': None,
            'culture_2': None,
            'culture_3': None
        }
        for growth_cycle in self.growth_cycles.all():
            name = f'culture_{growth_cycle.cycle_number}'
            cultures.update({name: growth_cycle.culture.name})
        return cultures

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
        return reverse('greenhouse-detail', kwargs={'pk': self.id})

    @property
    def detail_url(self):
        return reverse('greenhouse-detail', kwargs={'pk': self.id})

    @property
    def update_url(self):
        return reverse('greenhouse-update', kwargs={'pk': self.id})

    @property
    def delete_url(self):
        return reverse('greenhouse-delete', kwargs={'pk': self.id})

    @property
    def filter_kwargs(self):
        kwargs = {
            'heated': self.heated,
            'lighted': self.lighted,
            'high_wire': self.high_wire,
            'above_ground': self.above_ground,
        }
        cultures = {
            'culture_1': None,
            'culture_2': None,
            'culture_3': None
        }
        for growth_cycle in self.growth_cycles.all():
            name = f'culture_{growth_cycle.cycle_number}'
            cultures.update({name: growth_cycle.culture.name})
        kwargs.update(cultures)
        return kwargs

    def __str__(self):
        h = 'heated' if self.heated else 'not heated'
        l = 'lighting' if self.lighted else 'no lighting'
        g = 'above ground' if self.above_ground else 'on ground'
        s = 'high wire' if self.high_wire else 'classic'
        return f'Greenhouse: {h}, {l}, {g}, {s}'


class Culture(NamedUserObjectModel):
    residue = models.ForeignKey(SampleSeries, on_delete=models.PROTECT, null=True)


class GreenhouseGrowthCycle(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    cycle_number = models.IntegerField(default=1)
    culture = models.ForeignKey(Culture, on_delete=models.CASCADE, null=True)
    greenhouse = models.ForeignKey(Greenhouse, on_delete=models.CASCADE, null=True)
    group_settings = models.ForeignKey(Composition, on_delete=models.CASCADE, null=True)

    def add_timestep(self, timestep):
        ts_set = GrowthTimeStepSet.objects.create(owner=self.owner, timestep=timestep, growth_cycle=self)
        for component in self.group_settings.components:
            ts_set.add_component(component)

    @property
    def values(self):
        """Returns the growth shares as list with length of the reference temporal distribution"""

        # For now, the reference temporal distribution is hard coded
        reference_distribution = CaseStudyBaseObjects.objects.get.reference_distribution
        value_dict = {timestep: 0 for timestep in reference_distribution.timesteps}
        for share in self.shares:
            value_dict[share.timestep] += share.average
        return list(value_dict.values())

    @property
    def shares(self):
        return GrowthShare.objects.filter(timestepset__growth_cycle=self)

    @property
    def timesteps(self):
        return Timestep.objects.filter(id__in=[ts.timestep.id for ts in self.growthtimestepset_set.all()])

    @property
    def min_timestep(self):
        return Timestep.objects.get(id=self.timesteps.aggregate(models.Min('id'))['id__min'])

    @property
    def table_data(self):
        table_data = []
        components = self.group_settings.components()
        for component in components:
            table_row = {'Component': component.name}
            shares = GrowthShare.objects.filter(
                component=component,
                timestepset__growth_cycle=self,
                timestepset__timestep__in=self.timesteps.all()
            ).order_by('timestepset__timestep__id')
            for share in shares:
                table_row[share.timestep.name] = f'{share.average}'
            table_data.append(table_row)

        # If no components, create a row with None values
        if not table_data:
            table_row = {'component': None}
            for timestep in self.timesteps.all():
                table_row[timestep.name] = None
            table_data.append(table_row)

        return table_data

    def get_absolute_url(self):
        return reverse('greenhouse-detail', kwargs={'pk': self.greenhouse.id})


@receiver(post_delete, sender=GreenhouseGrowthCycle)
def reorder_growth_cycles_post_delete(sender, instance, **kwargs):
    instance.greenhouse.sort_growth_cycles()


class GrowthTimeStepSet(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    timestep = models.ForeignKey(Timestep, on_delete=models.CASCADE)
    growth_cycle = models.ForeignKey(GreenhouseGrowthCycle, on_delete=models.CASCADE, null=True)

    def add_component(self, component, **kwargs):
        share = GrowthShare.objects.create(
            owner=self.owner,
            component=component,
            timestepset=self,
            average=kwargs.get('average', 0.0),
            standard_deviation=kwargs.get('standard_deviation', 0.0)
        )
        return share

    def get_absolute_url(self):
        return self.growth_cycle.greenhouse.get_absolute_url()


class GrowthShare(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    component = models.ForeignKey(MaterialComponent, on_delete=models.CASCADE, null=True)
    timestepset = models.ForeignKey(GrowthTimeStepSet, on_delete=models.CASCADE, null=True)
    average = models.FloatField(default=0.0)
    standard_deviation = models.FloatField(default=0.0)

    @property
    def timestep(self):
        return self.timestepset.timestep


class BaseObjectManager(models.Manager):
    DISTRIBUTION = 'Months of the year'

    def initialize(self):
        distribution, created = TemporalDistribution.objects.get_or_create(name=self.DISTRIBUTION)
        if created:
            months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            for month in months:
                Timestep.objects.create(name=month, distribution=distribution)

        return super().create(
            reference_distribution=distribution,
        )

    @property
    def get(self):
        if not super().first():
            return self.initialize()
        else:
            return super().first()


class CaseStudyBaseObjects(models.Model):
    """
    Holds information about objects that should be in the database as a standard reference for other models. If they
    are missing (e.g. if a fresh database is used in a new instance of this tool), this model takes care that they are
    created.
    """
    reference_distribution = models.ForeignKey(TemporalDistribution, on_delete=models.PROTECT, null=True)

    objects = BaseObjectManager()
