from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from utils.object_management.models import get_default_owner
from utils.properties.models import NumericMeasurementMixin, Property, Unit
from utils.properties.units import UnitConversionError
from utils.properties.utils import format_measurement_display


class ModelLabelMetadataTestCase(TestCase):
    def test_property_plural_label_is_explicit(self):
        self.assertEqual(Property._meta.verbose_name_plural, "properties")


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

    def test_resolve_legacy_label_matches_symbol(self):
        expected_unit = Unit.objects.create(
            name="People per square kilometre", symbol="1/km²"
        )

        resolved_unit = Unit.resolve_legacy_label("1/km²")

        self.assertEqual(resolved_unit, expected_unit)

    def test_resolve_legacy_label_prefers_owner_scoped_match(self):
        owner = get_user_model().objects.create_user(username="unit-owner")
        Unit.objects.create(name="Global unit", symbol="kg")
        expected_unit = Unit.objects.create(
            owner=owner,
            name="Owner kilogram",
            symbol="kg",
        )

        resolved_unit = Unit.resolve_legacy_label("kg", owner=owner)

        self.assertEqual(resolved_unit, expected_unit)

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


class MeasurementFormattingUtilsTestCase(TestCase):
    def test_format_measurement_display_includes_unit_and_year(self):
        self.assertEqual(
            format_measurement_display(123.321, unit_label="1/km²", year=2019),
            "123.321 1/km² (2019)",
        )

    def test_format_measurement_display_omits_empty_parts(self):
        self.assertEqual(format_measurement_display(123321, year=2021), "123321 (2021)")
        self.assertEqual(format_measurement_display(12.3, unit_label="kg"), "12.3 kg")


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

    def test_measurement_unit_label_hides_canonical_no_unit(self):
        measurement = self.DummyMeasurement(
            property_obj=SimpleNamespace(name="Population", unit=""),
            average=Decimal("12.34"),
            standard_deviation=Decimal("0.56"),
            unit=Unit.objects.get(owner=get_default_owner(), name="No unit"),
        )

        self.assertIsNone(measurement.measurement_unit_label)

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
