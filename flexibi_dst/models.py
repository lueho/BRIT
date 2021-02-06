from django.contrib.auth.models import User
from django.db import models


class LiteratureSource(models.Model):
    authors = models.CharField(max_length=500, null=True)
    title = models.CharField(max_length=500, null=True)
    abbreviation = models.CharField(max_length=50, null=True)

    def __str__(self):
        return self.abbreviation


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


class Timestep(models.Model):
    """
    Defines a timestep for organisation of seasonal distributions
    """
    name = models.CharField(max_length=255, blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    distribution = models.ForeignKey(TemporalDistribution, default=1, on_delete=models.CASCADE)

    def __str__(self):
        return self.name
