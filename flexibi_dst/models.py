from django.contrib.auth.models import User
from django.db import models


class TemporalDistribution(models.Model):
    """
    Model to organize timesteps into named distributions (e.g. months are timesteps of the temporal distribution 'months
    of the year').
    """
    name = models.CharField(max_length=255, blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        unique_together = [['name', 'owner']]


class Timestep(models.Model):
    """
    Defines a timestep for organisation of seasonal distributions
    """
    name = models.CharField(max_length=255, blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    distribution = models.ForeignKey(TemporalDistribution, default=1, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

    class Meta:
        unique_together = [['name', 'owner']]
