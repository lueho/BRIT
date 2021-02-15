from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import signals
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from factory.django import mute_signals

from flexibi_dst.models import Timestep, TemporalDistribution
from library.models import LiteratureSource
from .tables import averages_table_factory, distribution_table_factory


class MaterialManager(models.Manager):

    def feedstocks(self):
        return self.filter(is_feedstock=True)


class Material(models.Model):
    """
    Holds all materials used
    """
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    is_feedstock = models.BooleanField(default=False)
    stan_flow_id = models.CharField(max_length=5,
                                    blank=True,
                                    null=True,
                                    validators=[RegexValidator(regex=r'^[0-9]{5}?',
                                                               message='STAN id must have 5 digits.s',
                                                               code='invalid_stan_id')])

    objects = MaterialManager()

    def settings(self, owner):
        return self.materialsettings_set.filter(owner=owner)

    @property
    def standard_settings(self):
        return self.materialsettings_set.get(standard=True)

    def initialize_standard_settings(self):
        base_group = BaseObjects.get.base_group()
        base_component = BaseObjects.get.base_component()

        settings = MaterialSettings.objects.create(
            material=self,
            owner=self.owner,
            standard=True,
            name='',
            description=''
        )
        settings = MaterialComponentGroupSettings.objects.create(
            material_settings=settings,
            owner=self.owner,
            group=base_group,
            fractions_of=base_component
        )
        settings.add_component(base_component)

    @staticmethod
    def get_absolute_url():
        return reverse('material_list')

    @property
    def detail_url(self):
        return self.materialsettings_set.get(standard=True).get_absolute_url()

    @property
    def update_url(self):
        return reverse('material_update', kwargs={'pk': self.id})

    @property
    def delete_url(self):
        return reverse('material_delete', kwargs={'pk': self.id})

    def __str__(self):
        return self.name

    class Meta:
        unique_together = [['name', 'owner']]


@receiver(post_save, sender=Material)
def initialize_material(sender, instance, created, **kwargs):
    if created:
        instance.initialize_standard_settings()


class MaterialSettings(models.Model):
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    name = models.CharField(max_length=255, default='Customization')
    description = models.TextField(blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    standard = models.BooleanField(default=True)

    def add_base_group_and_component(self):
        """
        Initializes a first component group 'Total Material', which contains the component 'Fresh matter (FM)'. These
        are the starting point with a total of 1 that all other weight fractions can refer to.
        """
        base_group = BaseObjects.get.base_group()
        base_component = BaseObjects.get.base_component()
        group_settings = MaterialComponentGroupSettings.objects.create(
            material_settings=self,
            owner=self.owner,
            group=base_group,
            fractions_of=base_component
        )
        CompositionSet.objects.create(
            owner=self.owner,
            group_settings=group_settings,
            timestep=BaseObjects.get.base_timestep()
        )
        group_settings.add_component(base_component)

    def add_component_group(self, group, **kwargs):
        if 'component_group_settings' not in kwargs:
            kwargs['component_group_settings'] = MaterialComponentGroupSettings.objects.create(
                owner=self.owner,
                group=group,
                material_settings=self,
                fractions_of=kwargs.setdefault('fractions_of', BaseObjects.get.base_component())
            )

        return kwargs['component_group_settings']

    @property
    def component_ids(self):
        """
        Ids of components of groups that are assigned to this material.
        """
        return [pk for setting in self.materialcomponentgroupsettings_set.all() for pk in setting.component_ids]

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

    def composition(self):
        base_group = BaseObjects.get.base_group()
        group_settings = self.materialcomponentgroupsettings_set.exclude(group=base_group)
        grouped_shares = {}
        for setting in group_settings:
            grouped_shares[setting] = {
                'averages': [],
                'averages_composition': setting.average_composition,
                'averages_table': setting.averages_table(),
                'distribution_tables': setting.distribution_tables()
            }
            for share in setting.average_composition.materialcomponentshare_set.all():
                grouped_shares[setting]['averages'].append(share)
        return grouped_shares

    def get_absolute_url(self):
        return reverse('material_settings', kwargs={'pk': self.id})

    def __str__(self):
        if self.standard:
            return f'Standard settings for material {self.material.name}'
        else:
            return f'Customization of material {self.material.name} by user {self.owner.username}'


class MaterialComponent(models.Model):
    """
    Represents any kind of component that a material can consists of (e.g. water, any kind of chemical element
    or more complex components, such as carbohydrates)
    """
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)

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

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'component'
        unique_together = [['name', 'owner']]


class MaterialComponentGroup(models.Model):
    """
    Container model to group MaterialComponent instances
    """
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)

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

    def __str__(self):
        return self.name

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
    sources = models.ManyToManyField(LiteratureSource)

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
        return self.compositionset_set.get(timestep=BaseObjects.get.base_timestep())

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

    def distribution_tables(self):
        return {distribution: distribution_table_factory(self, distribution) for distribution in
                self.temporal_distributions.exclude(id=BaseObjects.get.base_distribution().id)}

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
        base_distribution = BaseObjects.get.base_distribution()
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
        if not self.timestep == BaseObjects.get.base_timestep():
            if not self.materialcomponentshare_set.all().exists():
                self.delete()

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
    STANDARD_OWNER_NAME = 'flexibi'
    BASE_GROUP_NAME = 'Total Material'
    BASE_COMPONENT_NAME = 'Fresh Matter (FM)'
    BASE_DISTRIBUTION_NAME = 'Average'
    BASE_TIMESTEP_NAME = 'Average'

    def initialize(self):
        standard_owner, created = User.objects.get_or_create(username=self.STANDARD_OWNER_NAME)
        group, created = MaterialComponentGroup.objects.get_or_create(name=self.BASE_GROUP_NAME, owner=standard_owner)
        component, created = MaterialComponent.objects.get_or_create(name=self.BASE_COMPONENT_NAME,
                                                                     owner=standard_owner)
        distribution, created = TemporalDistribution.objects.get_or_create(name=self.BASE_DISTRIBUTION_NAME,
                                                                           owner=standard_owner)
        timestep, created = Timestep.objects.get_or_create(name=self.BASE_TIMESTEP_NAME, owner=standard_owner)
        return super().create(
            base_group=group,
            base_component=component,
            base_distribution=distribution,
            base_timestep=timestep,
            standard_owner=standard_owner
        )

    def standard_owner(self):
        if not super().first():
            return self.initialize().standard_owner
        else:
            return super().first().standard_owner

    def base_group(self):
        if not super().first():
            return self.initialize().base_group
        else:
            return super().first().base_group

    def base_component(self):
        if not super().first():
            return self.initialize().base_component
        else:
            return super().first().base_component

    def base_distribution(self):
        if not super().first():
            return self.initialize().base_distribution
        else:
            return super().first().base_distribution

    def base_timestep(self):
        if not super().first():
            return self.initialize().base_timestep
        else:
            return super().first().base_timestep


class BaseObjects(models.Model):
    """
    Holds information about objects that should be in the database as a standard reference for other models. If they
    are missing (e.g. if a fresh database is used in a new instance of this tool), this model takes care that they are
    created.
    """
    standard_owner = models.ForeignKey(User, on_delete=models.PROTECT, null=True)
    base_group = models.ForeignKey(MaterialComponentGroup, on_delete=models.PROTECT, null=True)
    base_component = models.ForeignKey(MaterialComponent, on_delete=models.PROTECT, null=True)
    base_distribution = models.ForeignKey(TemporalDistribution, on_delete=models.PROTECT, null=True)
    base_timestep = models.ForeignKey(Timestep, on_delete=models.PROTECT, null=True)

    get = BaseObjectManager()
