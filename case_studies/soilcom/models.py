from django.db import models
from django.urls import reverse

from brit.models import NamedUserObjectModel
from materials.models import Material


class Collector(NamedUserObjectModel):

    def get_absolute_url(self):
        return reverse('collector_detail', args=[self.id])

    @staticmethod
    def get_create_url():
        return reverse('collector_create')

    class Meta:
        verbose_name = 'Waste Collector'


class CollectionSystem(NamedUserObjectModel):

    def get_absolute_url(self):
        return reverse('collection_system_detail', args=[self.id])

    class Meta:
        verbose_name = 'Waste Collection System'


class WasteStreamCategory(NamedUserObjectModel):
    pass


class WasteStreamAllowed(NamedUserObjectModel):
    category = models.ForeignKey(WasteStreamCategory, on_delete=models.PROTECT)
    materials = models.ManyToManyField(Material)
