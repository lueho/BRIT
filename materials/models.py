from django.conf import settings
from django.db import models
from django.db.models import Max
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from factory.django import mute_signals

from bibliography.models import Source
from brit.models import NamedUserObjectModel
from distributions.models import Timestep, TemporalDistribution
from users.models import get_default_owner


class MaterialCategory(NamedUserObjectModel):
    pass

class BaseMaterial(NamedUserObjectModel):
    """
    Base for all specialized models of material
    """
    type = models.CharField(max_length=127, default='material')
    categories = models.ManyToManyField(MaterialCategory, blank=True)

    class Meta:
        verbose_name = 'Material'
        unique_together = [['name', 'owner']]


class MaterialManager(models.Manager):

    def get_queryset(self):
        return super().get_queryset().filter(type='material')


class Material(BaseMaterial):
    """
    Generic material class for many purposes. E.g. this is used as top level definition to link semantic definition of
    materials with analysis data.
    """

    class Meta:
        proxy = True


class MaterialComponentManager(models.Manager):
    def default(self):
        return self.get_queryset().get(name='Fresh Matter (FM)', owner=get_default_owner())

    def other(self):
        return self.get_queryset().get(name='Other', owner=get_default_owner())


class MaterialComponent(BaseMaterial):
    """
    Component class of a material for which a weight fraction can be assigned but which cannot itself be defined as a
    material (e.g. total solids, volatile solids, etc.)
    """

    objects = MaterialComponentManager()

    class Meta:
        proxy = True
        verbose_name = 'component'


@receiver(post_save, sender=MaterialComponent)
def add_type_component(sender, instance, created, **kwargs):
    if created:
        instance.type = 'component'
        instance.save()


def get_default_component():
    return MaterialComponent.objects.get_or_create(
        owner=get_default_owner(),
        name=getattr(settings, 'DEFAULT_MATERIALCOMPONENT_NAME', 'Fresh Matter (FM)')
    )[0]


def get_default_component_pk():
    return MaterialComponent.objects.get_or_create(
        owner=get_default_owner(),
        name=getattr(settings, 'DEFAULT_MATERIALCOMPONENT_NAME', 'Fresh Matter (FM)')
    )[0].pk


class MaterialComponentGroupManager(models.Manager):
    def default(self):
        return self.get_queryset().get(name='Total Material', owner=get_default_owner())


class MaterialComponentGroup(NamedUserObjectModel):
    """
    Definition of a group of components that belong together to form a composition which can be described with
    weight fractions. E.g. Macro component, chemical elements, etc. The actual composition is described in its own
    model: Composition. This is a container that allows to identify comparable compositions.
    """

    objects = MaterialComponentGroupManager()

    class Meta:
        unique_together = [['name', 'owner']]


def get_default_group():
    return MaterialComponentGroup.objects.get_or_create(
        owner=get_default_owner(),
        name=getattr(settings, 'DEFAULT_MATERIALCOMPONENTGROUP_NAME', 'Total Material')
    )[0]


class SampleSeries(NamedUserObjectModel):
    """
    Sample series are used to add concrete experimental data to the abstract semantic definition of materials. A sample
    series consists of several samples that are taken from a comparable source at different times. That way a temporal
    distribution of material properties and compositions over time can be described.
    """
    material = models.ForeignKey(Material, on_delete=models.PROTECT)
    preview = models.ImageField(default='materials/img/generic_material.jpg', null=False)
    publish = models.BooleanField(default=False)
    standard = models.BooleanField(default=True)
    temporal_distributions = models.ManyToManyField(TemporalDistribution)

    def add_component_group(self, group, fractions_of=None):
        """Adds compositions of a component group to all samples of this sample series."""
        if not fractions_of:
            fractions_of = MaterialComponent.objects.default()
        for sample in self.samples.all():
            Composition.objects.create(
                owner=self.owner,
                group=group,
                sample=sample,
                fractions_of=fractions_of
            )

    def remove_component_group(self, group):
        """Removes all compositions of a component group from all samples of this sample series."""
        for sample in self.samples.all():
            Composition.objects.filter(sample=sample, group=group).delete()

    def add_component(self, component, group):
        """Creates WeightShare objects for a new component for all samples of a SampleSeries at once."""
        for sample in self.samples.all():
            for composition in sample.compositions.filter(group=group):
                composition.add_component(component)

    def remove_component(self, component, group):
        """Removes all WeightShare objects of a given component and component group"""
        for sample in self.samples.all():
            for composition in sample.compositions.filter(group=group):
                composition.remove_component(component)

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
            Sample.objects.create(owner=self.owner, series=self, timestep=timestep)

    def remove_temporal_distribution(self, distribution):
        """
        Removes the temporal distribution from the m2m field and also cleans up all related composition sets and shares.
        """
        if distribution in self.temporal_distributions.all():
            for timestep in distribution.timestep_set.all():
                self.samples.filter(timestep=timestep).delete()
            self.temporal_distributions.remove(distribution)

    @property
    def components(self):
        """
        Queryset of all components that have been assigned to this group.
        """
        return MaterialComponent.objects.filter(id__in=[share['component'] for share in
                                                        WeightShare.objects.filter(
                                                            composition__sample__series=self).values(
                                                            'component').distinct()])

    @property
    def component_groups(self):
        return MaterialComponentGroup.objects.filter(
            id__in=[composition['group'] for composition in
                    Composition.objects.filter(
                        sample__series=self
                    ).exclude(
                        id=MaterialComponentGroup.objects.default().id
                    ).values('group').distinct()]
        )

    @property
    def group_ids(self):
        """
        Ids of component groups that have been assigned to this material.
        """
        return [setting['group'] for setting in
                Composition.objects.filter(sample__series=self).values('group').distinct()]

    @property
    def blocked_ids(self):
        """
        Returns a list of group ids that cannot be added to the material because they are already assigned.
        """
        return self.group_ids

    @property
    def shares(self):
        return WeightShare.objects.filter(composition__sample__series=self)

    def duplicate(self, creator, **kwargs):

        with mute_signals(post_save):
            duplicate = SampleSeries.objects.create(
                owner=creator,
                name=kwargs.get('name', self.name),
                material=kwargs.get('material', self.material)
            )

            for sample in self.samples.all():
                sample_duplicate = sample.duplicate(creator)
                sample_duplicate.series = duplicate
                sample_duplicate.save()

            duplicate.temporal_distributions.set(self.temporal_distributions.all())

        return duplicate

    @property
    def full_name(self):
        return f'{self.material.name} {self.name}'

    @property
    def group_settings(self):
        return Composition.objects.filter(
            sample__series=self
        ).exclude(
            group=MaterialComponentGroup.objects.default()
        )


@receiver(post_save, sender=SampleSeries)
def add_default_temporal_distribution(sender, instance, created, **kwargs):
    if created:
        instance.add_temporal_distribution(TemporalDistribution.objects.default())


class MaterialProperty(NamedUserObjectModel):
    unit = models.CharField(max_length=63)

    def __str__(self):
        return f'{self.name} [{self.unit}]'


class MaterialPropertyValue(NamedUserObjectModel):
    property = models.ForeignKey(MaterialProperty, on_delete=models.PROTECT)
    average = models.FloatField()
    standard_deviation = models.FloatField()

    def duplicate(self, creator):
        with mute_signals(post_save):
            duplicate = MaterialPropertyValue.objects.create(
                owner=creator,
                property=self.property,
                average=self.average,
                standard_deviation=self.standard_deviation,
            )
        return duplicate


class Sample(NamedUserObjectModel):
    """
    Representation of a single sample that was taken at a specific location and time. Equivalent samples are associated
    with a SampleSeries to temporal distribution of properties and composition.
    """
    series = models.ForeignKey(SampleSeries, related_name='samples', on_delete=models.CASCADE)
    timestep = models.ForeignKey(Timestep, related_name='samples', on_delete=models.PROTECT, null=True)
    taken_at = models.DateTimeField(blank=True, null=True)
    preview = models.ImageField(blank=True, null=True)
    properties = models.ManyToManyField(MaterialPropertyValue)
    sources = models.ManyToManyField(Source)

    def duplicate(self, creator, **kwargs):
        with mute_signals(post_save):
            duplicate = Sample.objects.create(
                owner=creator,
                series=kwargs.get('series', self.series),
                timestep=kwargs.get('timestep', self.timestep),
                taken_at=kwargs.get('taken_at', self.taken_at),
            )
        for composition in self.compositions.all():
            duplicate_composition = composition.duplicate(creator)
            duplicate_composition.sample = duplicate
            duplicate_composition.save()

        for prop in self.properties.all():
            duplicate.properties.add(prop.duplicate(creator))

        return duplicate


@receiver(post_save, sender=Sample)
def add_default_composition(sender, instance, created, **kwargs):
    if created:
        composition = Composition.objects.create(
            owner=instance.owner,
            group=get_default_group(),
            sample=instance,
            fractions_of=get_default_component(),
        )
        composition.add_component(MaterialComponent.objects.default())


class Composition(NamedUserObjectModel):
    """
    Utility model to store the settings for component groups for each material in each customization. This model is not
    supposed to be edited directly by a user. It depends on user objects and must be deleted, when any of the user
    objects it depends on is deleted.
    """
    group = models.ForeignKey(MaterialComponentGroup, related_name='compositions', on_delete=models.PROTECT)
    sample = models.ForeignKey(Sample, related_name='compositions', on_delete=models.CASCADE)
    fractions_of = models.ForeignKey(MaterialComponent, on_delete=models.PROTECT, default=get_default_component_pk)
    order = models.IntegerField(default=90)

    class Meta:
        ordering = ['order']

    @property
    def material(self):
        return self.sample.series.material

    @property
    def timestep(self):
        return self.sample.timestep

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
    def blocked_component_ids(self):
        """
        Returns a list of ids that cannot be added to the group because they are either already assigned to the group
        or would create a circular reference.
        """
        ids = self.component_ids
        ids.append(self.fractions_of.id)
        ids.append(self.material.id)
        return ids

    @property
    def blocked_distribution_ids(self):
        return [dist.id for dist in self.sample.series.temporal_distributions.all()]

    def add_component(self, component, **kwargs):
        """
        Convenience method to create a correct WeightShare object with correct for this model.
        """
        return WeightShare.objects.create(
            owner=self.owner,
            component=component,
            composition=self,
            average=kwargs.setdefault('average', 0.0),
            standard_deviation=kwargs.setdefault('standard_deviation', 0.0),
        )

    def remove_component(self, component):
        """
        Removes the component from all compositions in which it appears.
        """
        self.shares.filter(component=component).delete()

    def add_temporal_distribution(self, distribution):
        """
        Adds the temporal distribution to the m2m field and also creates shares for all timesteps of the distribution
        for all components of this group.
        """
        self.sample.series.add_temporal_distribution(distribution)

    def remove_temporal_distribution(self, distribution):
        """
        Removes the temporal distribution from the m2m field and also cleans up all related composition sets and shares.
        """
        self.sample.series.remove_temporal_distribution(distribution)

    def order_up(self):
        current_order = self.order
        next_composition = self.sample.compositions.filter(order__gt=self.order).order_by('order').first()
        if next_composition:
            self.order = next_composition.order
            next_composition.order = current_order
            next_composition.save()
            self.save()

    def order_down(self):
        current_order = self.order
        previous_composition = self.sample.compositions.filter(order__lt=self.order).order_by('-order').first()
        if previous_composition:
            self.order = previous_composition.order
            previous_composition.order = current_order
            previous_composition.save()
            self.save()

    def duplicate(self, creator):
        with mute_signals(post_save):
            duplicate = Composition.objects.create(
                owner=creator,
                group=self.group,
                sample=self.sample,
                fractions_of=self.fractions_of,
                order=self.order
            )
        for share in self.shares.all():
            duplicate_share = share.duplicate(creator)
            duplicate_share.composition = duplicate
            duplicate_share.save()

        return duplicate

    def get_absolute_url(self):
        return self.sample.get_absolute_url()

    def __str__(self):
        return f'Composition of {self.group.name} of sample {self.sample.name}'


@receiver(post_save, sender=Composition)
def add_next_order_value(sender, instance, created, **kwargs):
    if created:
        compositions = Composition.objects.filter(sample=instance.sample)
        instance.order = compositions.aggregate(Max('order'))['order__max'] + 10
        instance.save()


class WeightShare(NamedUserObjectModel):
    """
    Holds the actual values of weight fractions that are part of any material composition. This model is not edited
    directly to maintain consistency within compositions. Use API of Composition instead.
    """
    component = models.ForeignKey(MaterialComponent, related_name='shares', on_delete=models.CASCADE)
    composition = models.ForeignKey(Composition, related_name='shares', on_delete=models.CASCADE)
    average = models.FloatField(default=0.0)
    standard_deviation = models.FloatField(default=0.0)

    class Meta:
        ordering = ['-average']

    @property
    def as_percentage(self):
        return f'{round(self.average * 100, 1)} ± {round(self.standard_deviation * 100, 1)}%'

    @property
    def material(self):
        return self.composition.sample.series.material

    @property
    def material_settings(self):
        return self.composition.sample.series

    @property
    def group(self):
        return self.composition.group

    @property
    def group_settings(self):
        return self.composition

    @property
    def timestep(self):
        return self.composition.sample.timestep

    def get_absolute_url(self):
        return reverse('sampleseries-detail', kwargs={'pk': self.composition.sample.series.id})

    def duplicate(self, creator):
        duplicate = WeightShare.objects.create(
            owner=creator,
            component=self.component,
            composition=self.composition,
            average=self.average,
            standard_deviation=self.standard_deviation)
        return duplicate

    def __str__(self):
        return f'Component share of material: {self.material.name}, component: {self.component.name}'
