from functools import cached_property

from django.conf import settings
from django.db import models

from bibliography.models import Source
from utils.object_management.models import NamedUserCreatedObject, get_default_owner
from utils.properties.units import (
    UnitConversionError,
    convert_weight_fraction_value,
    get_unit_registry,
)


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
    symbol = models.CharField(
        max_length=63,
        blank=True,
        help_text="Pint-compatible unit symbol (e.g. kg, mg/L, percent).",
    )
    reference_quantity = models.ForeignKey(
        "Property",
        related_name="reference_quantity_in_units",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
    )

    class Meta:
        unique_together = ["owner", "name"]

    @cached_property
    def pint_unit(self):
        """
        Return a pint.Unit for this instance's symbol, or None if unavailable.
        """
        symbol = (self.symbol or "").strip()
        if not symbol:
            return None

        registry = get_unit_registry()
        if registry is None:
            return None

        try:
            return registry.Unit(symbol)
        except Exception:
            return None

    def convert(self, value, target_unit):
        """
        Convert ``value`` from this unit to ``target_unit``.
        """
        if target_unit is None:
            raise UnitConversionError("Target unit is required for conversion.")

        registry = get_unit_registry()
        if (
            registry is not None
            and self.pint_unit is not None
            and target_unit.pint_unit is not None
        ):
            try:
                quantity = registry.Quantity(value, self.pint_unit)
                return quantity.to(target_unit.pint_unit).magnitude
            except Exception as exc:
                raise UnitConversionError(
                    f"Failed to convert from '{self}' to '{target_unit}'."
                ) from exc

        source_token = (self.symbol or self.name or "").strip()
        target_token = (target_unit.symbol or target_unit.name or "").strip()
        try:
            return convert_weight_fraction_value(value, source_token, target_token)
        except UnitConversionError as exc:
            if registry is None:
                raise UnitConversionError(
                    "pint is not installed and no supported fallback conversion was found."
                ) from exc
            raise UnitConversionError(
                f"Cannot convert from '{self}' to '{target_unit}': unmapped unit symbol."
            ) from exc


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
