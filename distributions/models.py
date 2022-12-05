from django.contrib.auth.models import User
from django.db import models
from django.db.models import Max
from django.db.models.signals import post_save
from django.dispatch import receiver

from utils.models import NamedUserObjectModel, OwnedObjectModel
from users.models import get_default_owner


class TemporalDistributionManager(models.Manager):
    def default(self):
        return self.get_queryset().get(name='Average', owner=get_default_owner())


class TemporalDistribution(NamedUserObjectModel):
    """
    Model to organize timesteps into named distributions (e.g. months are timesteps of the temporal distribution 'months
    of the year').
    """

    objects = TemporalDistributionManager()

    def __str__(self):
        return self.name

    class Meta:
        unique_together = [['name', 'owner']]


class TimestepManager(models.Manager):
    def default(self):
        return self.get_queryset().get(name='Average', owner=get_default_owner())


class Timestep(NamedUserObjectModel):
    """
    Defines a timestep for organisation of seasonal distributions
    """
    distribution = models.ForeignKey(TemporalDistribution, on_delete=models.CASCADE)
    order = models.IntegerField(default=90)

    objects = TimestepManager()

    class Meta:
        unique_together = [['name', 'owner']]
        ordering = ['order']

    @property
    def abbreviated(self):
        return self.name[:3]

    def __str__(self):
        return self.name


@receiver(post_save, sender=Timestep)
def add_next_order_value(sender, instance, created, **kwargs):
    if created:
        timesteps = Timestep.objects.filter(distribution=instance.distribution)
        instance.order = timesteps.aggregate(Max('order'))['order__max'] + 10
        instance.save()


class Period(OwnedObjectModel):
    """
    A period is a part of a full temporal distribution. Any temporal distribution can be divided into an arbitrary
    number of periods, each of which has a start and stop timestep.
    """
    distribution = models.ForeignKey(TemporalDistribution, on_delete=models.PROTECT)
    first_timestep = models.ForeignKey(Timestep, on_delete=models.PROTECT, related_name='first_of_periods')
    last_timestep = models.ForeignKey(Timestep, on_delete=models.PROTECT, related_name='last_of_periods')

    class Meta:
        unique_together = [['distribution', 'first_timestep', 'last_timestep']]

    def __str__(self):
        return f'Period: {self.first_timestep.abbreviated}. through {self.last_timestep.abbreviated}.'
