from django.conf import settings
from django.db import models

from bibliography.models import Source
from utils.object_management.models import NamedUserCreatedObject, get_default_owner


class PropertyBase(NamedUserCreatedObject):
    """
    Abstract base for module-specific property definitions.

    This keeps shared behavior (review workflow, ownership, naming) centralized
    while allowing each module to store its own property records.
    """

    unit = models.CharField(max_length=63)

    class Meta:
        abstract = True


class Unit(NamedUserCreatedObject):
    dimensionless = models.BooleanField(default=False, null=True)
    reference_quantity = models.ForeignKey(
        "Property",
        related_name="reference_quantity_in_units",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
    )

    class Meta:
        unique_together = ["owner", "name"]


def get_default_unit_pk():
    """
    Fetch the PK of the default 'No unit' Unit.
    """
    unit = Unit.objects.get(
        owner=get_default_owner(),
        name=getattr(settings, "DEFAULT_NO_UNIT_NAME", "No unit"),
    )
    return unit.pk


class Property(PropertyBase):
    """
    Defines properties that can be shared among other models. Allows to compare instances of different models that share
    the same properties while enforcing the use of matching units.
    """

    allowed_units = models.ManyToManyField(Unit)


class PropertyValue(NamedUserCreatedObject):
    """
    Serves to link any abstract property definition (see "Property" class) to a concrete instance
    of any other model with a concrete value. Intended to be related to other models through many-to-many relations.
    """

    property = models.ForeignKey(Property, on_delete=models.PROTECT)
    unit = models.ForeignKey(
        Unit, on_delete=models.PROTECT, default=get_default_unit_pk
    )
    average = models.FloatField()
    standard_deviation = models.FloatField(blank=True, null=True)
    sources = models.ManyToManyField(
        Source,
        blank=True,
        help_text="Sources or references for this property value.",
    )

    class Meta:
        abstract = True
        ordering = ["property__name"]

    def __str__(self):
        name = f"{self.property}: {self.average}"
        if self.standard_deviation:
            name += f" ± {self.standard_deviation}"
        return name
