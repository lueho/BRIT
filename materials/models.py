from django.contrib.auth.models import User
from django.db import models
from django.db.models import signals
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from factory.django import mute_signals

from bibliography.models import Source
from brit.models import NamedUserObjectModel
from distributions.models import Timestep, TemporalDistribution
from distributions.plots import DataSet, DoughnutChart
from users.models import ReferenceUsers
from .tables import averages_table_factory, distribution_table_factory


class MaterialGroup(NamedUserObjectModel):

    def get_absolute_url(self):
        return reverse('material_group_detail', args=[self.id])

    class Meta:
        verbose_name = 'Material Group'


class Material(NamedUserObjectModel):
    """
    Holds all materials used
    """
    groups = models.ManyToManyField(MaterialGroup, blank=True)

    def settings(self, owner):
        return self.materialsettings_set.filter(owner=owner)

    @property
    def standard_settings(self):
        return self.materialsettings_set.get(standard=True)

    def initialize_standard_settings(self):
        base_group = BaseObjects.objects.get.base_group
        base_component = BaseObjects.objects.get.base_component

        settings = MaterialSettings.objects.create(
            material=self,
            owner=self.owner,
            standard=True,
            full_name='',
            description=''
        )
        settings = MaterialComponentGroupSettings.objects.create(
            material_settings=settings,
            owner=self.owner,
            group=base_group,
            fractions_of=base_component
        )
        settings.add_component(base_component)

    class Meta:
        verbose_name = 'Material'
        unique_together = [['name', 'owner']]


@receiver(post_save, sender=Material)
def initialize_material(sender, instance, created, **kwargs):
    if created:
        instance.initialize_standard_settings()


class MaterialSettings(NamedUserObjectModel):
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    preview = models.ImageField(default='img/generic_material.jpg', null=False)
    full_name = models.CharField(max_length=255, blank=True, null=True)
    customization_name = models.CharField(max_length=255, default='Customization')
    publish = models.BooleanField(default=False)
    standard = models.BooleanField(default=True)

    def add_base_group_and_component(self):
        """
        Initializes a first component group 'Total Material', which contains the component 'Fresh matter (FM)'. These
        are the starting point with a total of 1 that all other weight fractions can refer to.
        """
        base_group = BaseObjects.objects.get.base_group
        base_component = BaseObjects.objects.get.base_component
        group_settings = MaterialComponentGroupSettings.objects.create(
            material_settings=self,
            owner=self.owner,
            group=base_group,
            fractions_of=base_component
        )
        CompositionSet.objects.create(
            owner=self.owner,
            group_settings=group_settings,
            timestep=BaseObjects.objects.get.base_timestep
        )
        group_settings.add_component(base_component)

    def add_component_group(self, group, **kwargs):
        if 'component_group_settings' not in kwargs:
            kwargs['component_group_settings'] = MaterialComponentGroupSettings.objects.create(
                owner=self.owner,
                group=group,
                material_settings=self,
                fractions_of=kwargs.setdefault('fractions_of', BaseObjects.objects.get.base_component)
            )

        return kwargs['component_group_settings']

    @property
    def component_ids(self):
        """
        Ids of components of groups that are assigned to this material.
        """
        return [pk for setting in self.materialcomponentgroupsettings_set.all() for pk in setting.component_ids]

    @property
    def components(self):
        """
        Queryset of all components that have been assigned to this group.
        """
        return MaterialComponent.objects.filter(id__in=self.component_ids)

    @property
    def grouped_components(self):
        """
        Dictionary with group objects as keys and lists with according components as values.
        """
        group_settings = self.materialcomponentgroupsettings_set.all()
        result = {}
        for gs in group_settings:
            group = gs.group
            components = [component for component in gs.components()]
            result[group] = components
        return result

    @property
    def component_groups(self):
        return MaterialComponentGroup.objects.filter(
            id__in=[setting['group'] for setting in
                    self.materialcomponentgroupsettings_set
                        .exclude(group=BaseObjects.objects.get.base_group)
                        .values('group').distinct()]
        )

    @property
    def group_ids(self):
        """
        Ids of component groups that have been assigned to this material.
        """
        return [setting['group'] for setting in self.materialcomponentgroupsettings_set.values('group').distinct()]

    @property
    def blocked_ids(self):
        """
        Returns a list of group ids that cannot be added to the material because they are already assigned.
        """
        ids = self.group_ids
        return ids

    @property
    def shares(self):
        return MaterialComponentShare.objects.filter(composition_set__group_settings__material_settings=self)

    def create_copy(self, owner, name='Customization', description=''):
        material_settings_copy = MaterialSettings.objects.create(
            material=self.material,
            owner=owner,
            standard=False,
            name=name,
            description=description
        )
        for group_settings_original in self.materialcomponentgroupsettings_set.all():
            with mute_signals(signals.post_save):
                group_settings_copy = MaterialComponentGroupSettings.objects.create(
                    material_settings=material_settings_copy,
                    owner=self.owner,
                    group=group_settings_original.group,
                    fractions_of=group_settings_original.fractions_of
                )
            for source in group_settings_original.sources.all():
                group_settings_copy.sources.add(source)
            for distribution in group_settings_original.temporal_distributions.all():
                group_settings_copy.add_temporal_distribution(distribution)
            for component in group_settings_original.components():
                group_settings_copy.add_component(component)
        return material_settings_copy

    @property
    def name(self):
        if self.standard:
            return self.material.name
        else:
            if self.full_name:
                return self.full_name
            else:
                return f'{self.material.name} ({self.customization_name})'

    @property
    def group_settings(self):
        return self.materialcomponentgroupsettings_set.exclude(group=BaseObjects.objects.get.base_group)

    def composition(self):
        grouped_shares = {}
        for setting in self.group_settings:
            grouped_shares[setting] = {
                'averages': [],
                'averages_composition': setting.average_composition,
                'averages_table': setting.averages_table(),
                'averages_chart': setting.averages_chart(),
                'distribution_tables': setting.distribution_tables(),
            }
            for share in setting.average_composition.materialcomponentshare_set.all():
                grouped_shares[setting]['averages'].append(share)
        return grouped_shares

    def get_absolute_url(self):
        return reverse('material_settings', kwargs={'pk': self.id})


class MaterialComponent(NamedUserObjectModel):
    """
    Represents any kind of component that a material can consists of (e.g. water, any kind of chemical element
    or more complex components, such as carbohydrates)
    """

    @staticmethod
    def get_absolute_url():
        return reverse('component_list')

    @property
    def detail_url(self):
        return reverse('component_detail', kwargs={'pk': self.id})

    @property
    def update_url(self):
        return reverse('component_update', kwargs={'pk': self.id})

    @property
    def delete_url(self):
        return reverse('component_delete', kwargs={'pk': self.id})

    class Meta:
        verbose_name = 'component'
        unique_together = [['name', 'owner']]


class MaterialComponentGroup(NamedUserObjectModel):
    """
    Container model to group MaterialComponent instances
    """

    @staticmethod
    def get_absolute_url():
        return reverse('material_component_group_list')

    @property
    def detail_url(self):
        return reverse('material_component_group_detail', kwargs={'pk': self.id})

    @property
    def update_url(self):
        return reverse('material_component_group_update', kwargs={'pk': self.id})

    @property
    def delete_url(self):
        return reverse('material_component_group_delete', kwargs={'pk': self.id})


    class Meta:
        verbose_name = 'material_component_group'
        verbose_name_plural = 'groups'
        unique_together = [['name', 'owner']]


class MaterialComponentGroupSettings(models.Model):
    """
    Utility model to store the settings for component groups for each material in each customization. This model is not
    supposed to be edited directly by a user. It depends on user objects and must be deleted, when any of the user
    objects it depends on is deleted.
    """

    owner = models.ForeignKey(User, default=8, on_delete=models.CASCADE)
    group = models.ForeignKey(MaterialComponentGroup, null=True, on_delete=models.CASCADE)
    material_settings = models.ForeignKey(MaterialSettings, null=True, on_delete=models.CASCADE)
    temporal_distributions = models.ManyToManyField(TemporalDistribution)
    fractions_of = models.ForeignKey(MaterialComponent, on_delete=models.CASCADE, default=1)
    sources = models.ManyToManyField(Source)

    @property
    def material(self):
        return self.material_settings.material

    @property
    def shares(self):
        return MaterialComponentShare.objects.filter(composition_set__group_settings=self)

    @property
    def component_ids(self):
        """
        Ids of all material components that have been assigned to this group.
        """
        return [share['component'] for share in self.shares.values('component').distinct()]

    def components(self):
        """
        Queryset of all components that have been assigned to this group.
        """
        return MaterialComponent.objects.filter(id__in=self.component_ids)

    @property
    def average_composition(self):
        return self.compositionset_set.get(timestep=BaseObjects.objects.get.base_timestep)

    @property
    def blocked_component_ids(self):
        """
        Returns a list of ids that cannot be added to the group because they are either already assigned to the group
        or would create a circular reference.
        """
        ids = self.component_ids
        ids.append(self.fractions_of.id)
        return ids

    @property
    def blocked_distribution_ids(self):
        return [dist.id for dist in self.temporal_distributions.all()]

    @property
    def temporal_distribution_ids(self):
        return [dist.id for dist in self.temporal_distributions.all()]

    def add_component(self, component, **kwargs):
        for cs in self.compositionset_set.all():
            cs.add_component(component, **kwargs)

    def remove_component(self, component):
        """
        Removes the component from all compositions in which it appears.
        """
        for composition_set in self.compositionset_set.all():
            composition_set.remove_component(component)

    def add_temporal_distribution(self, distribution):
        """
        Adds the temporal distribution to the m2m field and also creates shares for all timesteps of the distribution
        for all components of this group.
        """
        # In case this method is called manually and not by m2m_changed
        if distribution not in self.temporal_distributions.all():
            self.temporal_distributions.add(distribution)

        # Use average and standard deviation of component averages as default values for all timesteps
        for timestep in distribution.timestep_set.all():
            composition_set = CompositionSet.objects.create(owner=self.owner, group_settings=self, timestep=timestep)
            for share in self.average_composition.materialcomponentshare_set.all():
                composition_set.add_component(share.component, average=share.average,
                                              standard_deviation=share.standard_deviation)

    def remove_temporal_distribution(self, distribution):
        """
        Removes the temporal distribution from the m2m field and also cleans up all related composition sets and shares.
        """
        if distribution in self.temporal_distributions.all():
            self.temporal_distributions.remove(distribution)
            for timestep in distribution.timestep_set.all():
                self.compositionset_set.get(timestep=timestep).delete()

    def averages_table(self):
        return averages_table_factory(self)

    def averages_chart(self):
        return self.average_composition.get_chart()

    def distribution_tables(self):
        return {distribution: distribution_table_factory(self, distribution) for distribution in
                self.temporal_distributions.exclude(id=BaseObjects.objects.get.base_distribution.id)}

    def get_absolute_url(self):
        return self.material_settings.get_absolute_url()

    def __str__(self):
        if self.material_settings.standard:
            return f'Group {self.group.name} of standard material {self.material.name}'
        else:
            return f'Group {self.group.name} of customization of material {self.material.name} by user \
            {self.material.owner.username}'


@receiver(post_save, sender=MaterialComponentGroupSettings)
def initialize_group_settings(sender, instance, created, **kwargs):
    if created:
        base_distribution = BaseObjects.objects.get.base_distribution
        instance.add_temporal_distribution(base_distribution)


class CompositionSet(models.Model):
    """
    A composition set is the container for all weight fraction of a subgroup of components. The sum of all weight
    weight fractions of a composition set must always be 1 (100%).
    """
    owner = models.ForeignKey(User, default=8, on_delete=models.CASCADE)
    group_settings = models.ForeignKey(MaterialComponentGroupSettings, on_delete=models.CASCADE, null=True)
    timestep = models.ForeignKey(Timestep, on_delete=models.CASCADE, null=True)

    def add_component(self, component, **kwargs):
        share = MaterialComponentShare.objects.create(
            owner=self.owner,
            component=component,
            composition_set=self,
            average=kwargs.setdefault('average', 0.0),
            standard_deviation=kwargs.setdefault('standard_deviation', 0.0),
        )
        return share

    def remove_component(self, component):
        self.materialcomponentshare_set.get(component=component).delete()
        if not self.timestep == BaseObjects.objects.get.base_timestep:
            if not self.materialcomponentshare_set.all().exists():
                self.delete()

    def get_chart(self):
        data = {}
        labels = []
        for share in self.materialcomponentshare_set.all():
            labels.append(share.component.name)
            data[share.component.name] = share.average

        dataset = DataSet(
            label='Fraction',
            data=data,
            unit='%'
        )

        chart = DoughnutChart(
            id=f'materialCompositionChart-{self.id}',
            title='Composition',
            unit='%'
        )
        chart.add_dataset(dataset)

        return chart

    def get_absolute_url(self):
        return self.group_settings.get_absolute_url()


class MaterialComponentShare(models.Model):
    """
    Holds the actual values of weight fractions that are part of any material composition. This model is not edited
    directly to maintain consistency within compositions. Use API of CompositionSet instead.
    """
    owner = models.ForeignKey(User, default=8, on_delete=models.CASCADE)
    component = models.ForeignKey(MaterialComponent, on_delete=models.CASCADE)
    composition_set = models.ForeignKey(CompositionSet, on_delete=models.CASCADE, null=True)
    average = models.FloatField(default=0.0)
    standard_deviation = models.FloatField(default=0.0)

    @property
    def as_percentage(self):
        return f'{round(self.average * 100, 1)} ± {round(self.standard_deviation * 100, 1)}%'

    @property
    def material(self):
        return self.material_settings.material

    @property
    def material_settings(self):
        return self.group_settings.material_settings

    @property
    def group(self):
        return self.group_settings.group

    @property
    def group_settings(self):
        return self.composition_set.group_settings

    @property
    def timestep(self):
        return self.composition_set.timestep

    def get_absolute_url(self):
        return reverse('material_settings', kwargs={'pk': self.material_settings.id})

    def __str__(self):
        return f'Component share of material: {self.material.name}, component: {self.component.name}'


class BaseObjectManager(models.Manager):
    BASE_GROUP = 'Total Material'
    BASE_COMPONENT = 'Fresh Matter (FM)'
    BASE_DISTRIBUTION = 'Average'
    BASE_TIMESTEP = 'Average'

    def initialize(self):
        owner = ReferenceUsers.objects.get.standard_owner
        group, created = MaterialComponentGroup.objects.get_or_create(name=self.BASE_GROUP, owner=owner)
        component, created = MaterialComponent.objects.get_or_create(name=self.BASE_COMPONENT, owner=owner)
        distribution, created = TemporalDistribution.objects.get_or_create(name=self.BASE_DISTRIBUTION, owner=owner)
        timestep, created = Timestep.objects.get_or_create(name=self.BASE_TIMESTEP, distribution=distribution,
                                                           owner=owner)
        return super().create(
            base_group=group,
            base_component=component,
            base_distribution=distribution,
            base_timestep=timestep,
        )

    @property
    def get(self):
        if not super().first():
            return self.initialize()
        else:
            return super().first()


class BaseObjects(models.Model):
    """
    Holds information about objects that should be in the database as a standard reference for other models. If they
    are missing (e.g. if a fresh database is used in a new instance of this tool), this model takes care that they are
    created.
    """
    base_group = models.ForeignKey(MaterialComponentGroup, on_delete=models.PROTECT, null=True)
    base_component = models.ForeignKey(MaterialComponent, on_delete=models.PROTECT, null=True)
    base_distribution = models.ForeignKey(TemporalDistribution, on_delete=models.PROTECT, null=True)
    base_timestep = models.ForeignKey(Timestep, on_delete=models.PROTECT, null=True)

    objects = BaseObjectManager()
