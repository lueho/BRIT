from django.contrib.auth.models import User
from django.db import models

from users.models import get_default_owner


class TemporalDistributionManager(models.Manager):
    def default(self):
        return self.get_queryset().get(name='Average', owner=get_default_owner())


class TemporalDistribution(models.Model):
    """
    Model to organize timesteps into named distributions (e.g. months are timesteps of the temporal distribution 'months
    of the year').
    """
    name = models.CharField(max_length=255, blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    description = models.TextField(blank=True, null=True)

    objects = TemporalDistributionManager()

    def __str__(self):
        return self.name

    class Meta:
        unique_together = [['name', 'owner']]


class TimestepManager(models.Manager):
    def default(self):
        return self.get_queryset().get(name='Average', owner=get_default_owner())


class Timestep(models.Model):
    """
    Defines a timestep for organisation of seasonal distributions
    """
    name = models.CharField(max_length=255, blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    distribution = models.ForeignKey(TemporalDistribution, on_delete=models.CASCADE)

    objects = TimestepManager()

    def __str__(self):
        return self.name

    class Meta:
        unique_together = [['name', 'owner']]
