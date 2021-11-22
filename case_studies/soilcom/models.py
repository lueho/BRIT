from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from bibliography.models import Source
from brit.models import NamedUserObjectModel
from maps.models import Catchment
from materials.models import Material, MaterialGroup, MaterialSettings


class Collector(NamedUserObjectModel):
    class Meta:
        verbose_name = 'Waste Collector'


class CollectionSystem(NamedUserObjectModel):
    class Meta:
        verbose_name = 'Waste Collection System'


class WasteCategory(NamedUserObjectModel):
    class Meta:
        verbose_name = 'Waste Category'
        verbose_name_plural = 'Waste categories'


class WasteComponentManager(models.Manager):

    def get_queryset(self):
        groups = MaterialGroup.objects.filter(name__in=('Biowaste component',))
        return super().get_queryset().filter(groups__in=groups)


class WasteComponent(Material):
    objects = WasteComponentManager()

    class Meta:
        proxy = True


@receiver(post_save, sender=WasteComponent)
def add_material_group(sender, instance, created, **kwargs):
    if created:
        group = MaterialGroup.objects.get(name='Biowaste component')
        instance.groups.add(group)
        instance.save()


class WasteStream(NamedUserObjectModel):
    category = models.ForeignKey(WasteCategory, on_delete=models.PROTECT)
    allowed_materials = models.ManyToManyField(Material)
    composition = models.ManyToManyField(MaterialSettings)

    class Meta:
        verbose_name = 'Waste Stream'


class WasteFlyerManager(models.Manager):

    def get_queryset(self):
        return super().get_queryset().filter(type='waste_flyer')


class WasteFlyer(Source):
    objects = WasteFlyerManager()

    class Meta:
        proxy = True
        verbose_name = 'Waste Flyer'


class Collection(NamedUserObjectModel):
    collector = models.ForeignKey(Collector, on_delete=models.CASCADE, blank=True, null=True)
    catchment = models.ForeignKey(Catchment, on_delete=models.PROTECT, blank=True, null=True)
    collection_system = models.ForeignKey(CollectionSystem, on_delete=models.CASCADE, blank=True, null=True)
    waste_stream = models.ForeignKey(WasteStream, on_delete=models.CASCADE, blank=True, null=True)
    flyer = models.ForeignKey(WasteFlyer, on_delete=models.CASCADE, blank=True, null=True)

    @property
    def geom(self):
        return self.catchment.geom
