from django.db import models
from django.urls import reverse

from brit.models import NamedUserObjectModel
from materials.models import Material, MaterialSettings


class Collector(NamedUserObjectModel):

    def get_absolute_url(self):
        return reverse('collector_detail', args=[self.id])

    class Meta:
        verbose_name = 'Waste Collector'


class CollectionSystem(NamedUserObjectModel):

    def get_absolute_url(self):
        return reverse('collection_system_detail', args=[self.id])

    class Meta:
        verbose_name = 'Waste Collection System'


class WasteCategory(NamedUserObjectModel):

    def get_absolute_url(self):
        return reverse('waste_category_detail', args=[self.id])

    class Meta:
        verbose_name = 'Waste Category'
        verbose_name_plural = 'Waste categories'


class WasteStream(NamedUserObjectModel):
    category = models.ForeignKey(WasteCategory, on_delete=models.PROTECT)
    allowed_materials = models.ManyToManyField(Material)
    composition = models.ManyToManyField(MaterialSettings)

    def get_absolute_url(self):
        return reverse('waste_stream_detail', args=[self.id])

    class Meta:
        verbose_name = 'Waste Stream'
