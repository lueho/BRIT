from django.db import models

from ..models import NamedUserCreatedObject


class PropertyUnit(NamedUserCreatedObject):
    dimensionless = models.BooleanField(default=False, null=True)
    reference_quantity = models.ForeignKey(
        'Property',
        related_name='reference_quantity_in_units',
        on_delete=models.PROTECT,
        blank=True,
        null=True
    )

    class Meta:
        unique_together = ['owner', 'name']


class Property(NamedUserCreatedObject):
    """
    Defines properties that can be shared among other models. Allows to compare instances of different models that share
    the same properties while enforcing the use of matching units.
    """
    unit = models.CharField(max_length=63)
    allowed_units = models.ManyToManyField(PropertyUnit)


class PropertyValue(NamedUserCreatedObject):
    """
    Serves to link any abstract property definition (see "Property" class) to a concrete instance
    of any other model with a concrete value. Intended to be related to other models through many-to-many relations.
    """
    property = models.ForeignKey(Property, on_delete=models.PROTECT)
    unit = models.ForeignKey(PropertyUnit, on_delete=models.PROTECT, blank=True, null=True)
    average = models.FloatField()
    standard_deviation = models.FloatField(blank=True, null=True)

    class Meta:
        abstract = True
        ordering = ['property__name']

    def __str__(self):
        name = f'{self.property}: {self.average}'
        if self.standard_deviation:
            name += f' ± {self.standard_deviation}'
        return name
