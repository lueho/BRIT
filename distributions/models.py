from django.contrib.auth.models import User
from django.db import models

from utils.models import NamedUserObjectModel
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

    objects = TimestepManager()

    def __str__(self):
        return self.name

    class Meta:
        unique_together = [['name', 'owner']]
