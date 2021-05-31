from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse


class LiteratureSource(models.Model):
    owner = models.ForeignKey(User, default=8, on_delete=models.CASCADE)
    authors = models.CharField(max_length=500, null=True)
    title = models.CharField(max_length=500, null=True)
    abbreviation = models.CharField(max_length=50, null=True)
    abstract = models.TextField(blank=True, null=True)

    def get_absolute_url(self):
        return reverse('literature source_detail', kwargs={'pk': self.id})

    def __str__(self):
        return self.abbreviation
