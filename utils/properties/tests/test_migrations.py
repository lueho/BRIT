from importlib import import_module

from django.contrib.auth.models import User
from django.test import TestCase

from utils.properties.models import Unit

resolve_or_create_unit = import_module(
    "utils.properties.migrations.0010_remove_property_unit"
).resolve_or_create_unit


class ResolveOrCreateUnitTestCase(TestCase):
    """Legacy free-text unit labels are resolved into ``Unit`` rows before the
    ``unit`` char field is dropped from ``Property`` and ``MaterialProperty``."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create(username="legacy-owner")
        cls.other = User.objects.create(username="other-owner")

    def test_blank_label_resolves_to_nothing(self):
        self.assertIsNone(resolve_or_create_unit(Unit, User, "  ", self.owner.pk))
        self.assertEqual(Unit.objects.filter(owner=self.owner).count(), 0)

    def test_owner_scoped_match_by_symbol_wins_over_foreign_match(self):
        Unit.objects.create(owner=self.other, name="kilogram", symbol="kg")
        own = Unit.objects.create(owner=self.owner, name="Kilogramm", symbol="kg")

        self.assertEqual(resolve_or_create_unit(Unit, User, "kg", self.owner.pk), own)

    def test_falls_back_to_any_owner_match_by_name(self):
        foreign = Unit.objects.create(owner=self.other, name="kilogram", symbol="kg")

        self.assertEqual(
            resolve_or_create_unit(Unit, User, "kilogram", self.owner.pk), foreign
        )

    def test_unresolvable_label_creates_unit_for_property_owner(self):
        unit = resolve_or_create_unit(Unit, User, " kg/m³ ", self.owner.pk)

        self.assertEqual(unit.owner, self.owner)
        self.assertEqual(unit.name, "kg/m³")
        self.assertEqual(unit.symbol, "kg/m³")
        self.assertEqual(
            resolve_or_create_unit(Unit, User, "kg/m³", self.owner.pk), unit
        )
