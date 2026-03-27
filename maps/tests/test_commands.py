import io

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from utils.properties.models import Unit

from ..models import Region, RegionAttributeValue, RegionProperty


class RegionAttributeValueUnitBackfillCommandTests(TestCase):
    def test_dry_run_reports_backfill_without_persisting(self):
        region = Region.objects.create(name="Dry Run Region")
        region_property = RegionProperty.objects.create(
            name="Population density",
            unit="1/km²",
        )
        unit = Unit.objects.create(name="People per square kilometre", symbol="1/km²")
        value = RegionAttributeValue.objects.create(
            region=region,
            property=region_property,
            value=123.321,
        )

        out = io.StringIO()
        call_command("backfill_region_attribute_value_units", dry_run=True, stdout=out)

        value.refresh_from_db()
        self.assertIsNone(value.unit)
        self.assertIn("Dry run: no changes will be written.", out.getvalue())
        self.assertIn("values_examined: 1", out.getvalue())
        self.assertIn("values_backfilled: 1", out.getvalue())
        self.assertIn("units_created: 0", out.getvalue())
        self.assertEqual(Unit.objects.filter(pk=unit.pk).count(), 1)

    def test_command_backfills_existing_matching_unit(self):
        region = Region.objects.create(name="Matched Region")
        region_property = RegionProperty.objects.create(
            name="Population density",
            unit="1/km²",
        )
        unit = Unit.objects.create(name="People per square kilometre", symbol="1/km²")
        value = RegionAttributeValue.objects.create(
            region=region,
            property=region_property,
            value=123.321,
        )

        out = io.StringIO()
        call_command("backfill_region_attribute_value_units", stdout=out)

        value.refresh_from_db()
        self.assertEqual(value.unit, unit)
        self.assertIn("values_backfilled: 1", out.getvalue())
        self.assertIn("values_unresolved: 0", out.getvalue())
        self.assertIn("units_created: 0", out.getvalue())

    def test_command_can_create_missing_units(self):
        region = Region.objects.create(name="Created Unit Region")
        region_property = RegionProperty.objects.create(name="Area", unit="km²")
        value = RegionAttributeValue.objects.create(
            region=region,
            property=region_property,
            value=123.321,
        )

        out = io.StringIO()
        call_command(
            "backfill_region_attribute_value_units",
            create_missing_units=True,
            stdout=out,
        )

        value.refresh_from_db()
        self.assertIsNotNone(value.unit)
        self.assertEqual(value.unit.name, "km²")
        self.assertEqual(value.unit.symbol, "km²")
        self.assertEqual(value.unit.owner, region_property.owner)
        self.assertIn("values_backfilled: 1", out.getvalue())
        self.assertIn("units_created: 1", out.getvalue())

    def test_command_can_fail_when_unresolved_values_remain(self):
        region = Region.objects.create(name="Unresolved Region")
        region_property = RegionProperty.objects.create(name="Area", unit="km²")
        RegionAttributeValue.objects.create(
            region=region,
            property=region_property,
            value=123.321,
        )

        with self.assertRaisesMessage(
            CommandError,
            "1 RegionAttributeValue rows remain unresolved.",
        ):
            call_command(
                "backfill_region_attribute_value_units", fail_on_unresolved=True
            )
