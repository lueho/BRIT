from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from bibliography.models import Source
from brit.models import NamedUserObjectModel
from maps.models import Catchment
from materials.models import Material, MaterialGroup, MaterialSettings


class Collector(NamedUserObjectModel):
    website = models.URLField(max_length=511, blank=True, null=True)

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


class WasteStreamQueryset(models.query.QuerySet):

    def match_allowed_materials(self, allowed_materials):
        """
        Returns a queryset of all waste streams that match the given combination of allowed_materials
        :param allowed_materials: Queryset
        :return: Queryset
        """

        return self.alias(
            allowed_materials_count=models.Count('allowed_materials'),
            allowed_materials_matches=models.Count('allowed_materials',
                                                   filter=models.Q(allowed_materials__in=allowed_materials))
        ).filter(
            allowed_materials_count=len(allowed_materials),
            allowed_materials_matches=len(allowed_materials)
        )

    def get_or_create(self, defaults=None, **kwargs):
        """
        Customizes the regular get_or_create to incorporate comparison of many-to-many relationships of
        allowed_materials. I.e. a queryset of allowed_materials can be passed to this method to get a waste stream
        with exactly that combination of allowed materials. Each possible combination can only appear once in the
        database.
        """

        if defaults:
            defaults = defaults.copy()

        if 'allowed_materials' in kwargs:
            allowed_materials = kwargs.pop('allowed_materials')
            qs = self.match_allowed_materials(allowed_materials)
        else:
            allowed_materials = Material.objects.none()
            qs = self

        if defaults:
            allowed_materials = defaults.pop('allowed_materials', allowed_materials)

        instance, created = super(WasteStreamQueryset, qs).get_or_create(defaults=defaults, **kwargs)

        if created:
            instance.allowed_materials.add(*allowed_materials)
            if not instance.name:
                instance.name = f'{instance.category.name} {len(allowed_materials)}'
                instance.save()

        return instance, created

    def update_or_create(self, defaults=None, **kwargs):
        """
        Updates one object that matches the given kwargs on the fields given in defaults. In comparison to the
        conventional update_or_create, this method enforces that every combination of allowed materials and category
        only exists uniquely in the database.

        """

        if defaults:
            defaults = defaults.copy()

        instance, created = self.get_or_create(defaults=defaults, **kwargs)

        if not created:

            new_allowed_materials = defaults.pop('allowed_materials', None)
            category = kwargs.get('category', None)

            if new_allowed_materials:
                qs = self.match_allowed_materials(new_allowed_materials)
                if category:
                    qs = qs.filter(category=category)
                if qs.exists():
                    raise ValidationError(
                        """
                        Waste stream cannot be updated. Equivalent waste stream of equal category and same combination of 
                        allowed materials already exists.
                        """
                    )

            self.filter(id=instance.id).update(**defaults)

            if new_allowed_materials:
                instance.allowed_materials.clear()
                instance.allowed_materials.add(*new_allowed_materials)

            instance.refresh_from_db()

        return instance, created


class WasteStream(NamedUserObjectModel):
    category = models.ForeignKey(WasteCategory, on_delete=models.PROTECT)
    allowed_materials = models.ManyToManyField(Material)
    composition = models.ManyToManyField(MaterialSettings)

    objects = WasteStreamQueryset.as_manager()

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

    def __str__(self):
        if self.url:
            return self.url
        else:
            return ''


@receiver(pre_save, sender=WasteFlyer)
def set_source_type(sender, instance, **kwargs):
    instance.type = 'waste_flyer'


class Collection(NamedUserObjectModel):
    collector = models.ForeignKey(Collector, on_delete=models.CASCADE, blank=True, null=True)
    catchment = models.ForeignKey(Catchment, on_delete=models.PROTECT, blank=True, null=True)
    collection_system = models.ForeignKey(CollectionSystem, on_delete=models.CASCADE, blank=True, null=True)
    waste_stream = models.ForeignKey(WasteStream, on_delete=models.SET_NULL, blank=True, null=True)
    flyers = models.ManyToManyField(WasteFlyer, related_name='collections')

    @property
    def geom(self):
        return self.catchment.geom
