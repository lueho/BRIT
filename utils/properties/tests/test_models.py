from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from utils.object_management.models import get_default_owner
from utils.properties.models import NumericMeasurementMixin, Unit
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


class UtilsInitialDataTestCase(TestCase):
    def test_no_unit_exists_for_default_owner(self):
        owner = get_default_owner()
        unit = Unit.objects.get(owner=owner, name="No unit")
        self.assertTrue(unit.dimensionless)


class NumericMeasurementMixinTestCase(TestCase):
    class DummyMeasurement(NumericMeasurementMixin):
        def __init__(self, property_obj, average, standard_deviation, unit=None):
            self.property = property_obj
            self.average = average
            self.standard_deviation = standard_deviation
            self.unit = unit

    class DummyAttributeMeasurement(NumericMeasurementMixin):
        measurement_property_field = "attribute"
        measurement_value_field = "value"

        def __init__(self, attribute, value, standard_deviation):
            self.attribute = attribute
            self.value = value
            self.standard_deviation = standard_deviation

    def test_measurement_unit_label_falls_back_to_property_unit(self):
        measurement = self.DummyMeasurement(
            property_obj=SimpleNamespace(name="Dry matter", unit="g/kg"),
            average=Decimal("12.34"),
            standard_deviation=Decimal("0.56"),
        )

        self.assertEqual(measurement.measurement_name, "Dry matter")
        self.assertEqual(measurement.measurement_unit_label, "g/kg")

    def test_display_values_round_for_collection_style_properties(self):
        measurement = self.DummyMeasurement(
            property_obj=SimpleNamespace(name="specific waste collected"),
            average=12.34,
            standard_deviation=0.56,
        )

        self.assertEqual(measurement.display_average, 12.3)
        self.assertEqual(measurement.display_standard_deviation, 0.6)

    def test_custom_field_mapping_supports_attribute_value_patterns(self):
        measurement = self.DummyAttributeMeasurement(
            attribute=SimpleNamespace(name="Population density", unit="1/km²"),
            value=123.321,
            standard_deviation=1.25,
        )

        self.assertEqual(measurement.measurement_name, "Population density")
        self.assertEqual(measurement.measurement_unit_label, "1/km²")
        self.assertEqual(measurement.display_average, 123.321)
        self.assertEqual(measurement.display_standard_deviation, 1.25)
