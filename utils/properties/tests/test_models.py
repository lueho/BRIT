from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from utils.properties.models import Unit
from utils.properties.units import UnitConversionError


class _FakeConvertedQuantity:
    def __init__(self, magnitude):
        self.magnitude = magnitude


class _FakeQuantity:
    FACTORS = {
        ("kg", "g"): 1000,
        ("g", "kg"): 0.001,
    }

    def __init__(self, magnitude, unit):
        self.magnitude = float(magnitude)
        self.unit = unit

    def to(self, target_unit):
        factor = self.FACTORS.get((self.unit, target_unit))
        if factor is None:
            raise ValueError("Unsupported conversion")
        return _FakeConvertedQuantity(self.magnitude * factor)


class _FakeRegistry:
    VALID_UNITS = {"kg", "g"}

    def Unit(self, symbol):
        if symbol not in self.VALID_UNITS:
            raise ValueError("Invalid unit")
        return symbol

    def Quantity(self, magnitude, unit):
        return _FakeQuantity(magnitude, unit)


class UnitModelConversionTestCase(TestCase):
    def test_pint_unit_is_none_when_symbol_is_blank(self):
        unit = Unit.objects.create(name="No symbol", symbol="")
        self.assertIsNone(unit.pint_unit)

    def test_convert_raises_when_pint_registry_is_unavailable(self):
        source = Unit.objects.create(name="Kilogram", symbol="kg")
        target = Unit.objects.create(name="Gram", symbol="g")

        with patch("utils.properties.models.get_unit_registry", return_value=None):
            with self.assertRaises(UnitConversionError):
                source.convert(Decimal("2"), target)

    def test_convert_raises_when_symbol_cannot_be_mapped(self):
        source = Unit.objects.create(name="Invalid", symbol="invalid-symbol")
        target = Unit.objects.create(name="Gram", symbol="g")

        with patch(
            "utils.properties.models.get_unit_registry", return_value=_FakeRegistry()
        ):
            with self.assertRaises(UnitConversionError):
                source.convert(Decimal("2"), target)

    def test_convert_uses_registry_conversion(self):
        source = Unit.objects.create(name="Kilogram", symbol="kg")
        target = Unit.objects.create(name="Gram", symbol="g")

        with patch(
            "utils.properties.models.get_unit_registry", return_value=_FakeRegistry()
        ):
            result = source.convert(Decimal("2"), target)

        self.assertEqual(result, 2000)
