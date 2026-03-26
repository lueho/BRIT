from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from maps.models import RegionAttributeValue
from utils.properties.models import Unit


class Command(BaseCommand):
    help = "Backfill RegionAttributeValue.unit from Attribute.unit labels."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing database updates.",
        )
        parser.add_argument(
            "--create-missing-units",
            action="store_true",
            help="Create owner-scoped Unit rows when no matching unit can be resolved.",
        )
        parser.add_argument(
            "--fail-on-unresolved",
            action="store_true",
            help="Raise a command error when unresolved labels remain after processing.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        create_missing_units = options["create_missing_units"]
        fail_on_unresolved = options["fail_on_unresolved"]
        stats = {
            "values_examined": 0,
            "values_backfilled": 0,
            "values_unresolved": 0,
            "blank_attribute_unit": 0,
            "units_created": 0,
        }
        unresolved_labels = Counter()
        resolved_units = {}
        values = (
            RegionAttributeValue.objects.select_related("attribute")
            .filter(unit__isnull=True)
            .order_by("pk")
        )

        if dry_run:
            self.stdout.write("Dry run: no changes will be written.")

        for value in values.iterator():
            stats["values_examined"] += 1
            attribute = value.attribute
            unit_label = (attribute.unit or "").strip()
            if not unit_label:
                stats["blank_attribute_unit"] += 1
                continue

            cache_key = (attribute.owner_id, unit_label)
            cache_entry = resolved_units.get(cache_key)
            if cache_entry is None:
                unit = Unit.resolve_legacy_label(unit_label, owner=attribute.owner_id)
                created = False
                if unit is None and create_missing_units:
                    if dry_run:
                        unit = Unit(
                            owner_id=attribute.owner_id,
                            name=unit_label,
                            symbol=unit_label if len(unit_label) <= 63 else "",
                        )
                        created = True
                    else:
                        unit, created = Unit.objects.get_or_create(
                            owner_id=attribute.owner_id,
                            name=unit_label,
                            defaults={
                                "symbol": unit_label if len(unit_label) <= 63 else "",
                                "publication_status": attribute.publication_status,
                            },
                        )
                cache_entry = (unit, created)
                resolved_units[cache_key] = cache_entry
                if created:
                    stats["units_created"] += 1

            unit, _ = cache_entry
            if unit is None:
                stats["values_unresolved"] += 1
                unresolved_labels[unit_label] += 1
                continue

            stats["values_backfilled"] += 1
            if not dry_run:
                value.unit_id = unit.pk
                value.save(update_fields=["unit"])

        for key in (
            "values_examined",
            "values_backfilled",
            "values_unresolved",
            "blank_attribute_unit",
            "units_created",
        ):
            self.stdout.write(f"{key}: {stats[key]}")

        if unresolved_labels:
            self.stdout.write("Unresolved labels:")
            for label, count in unresolved_labels.items():
                self.stdout.write(f"- {label}: {count}")

        if fail_on_unresolved and stats["values_unresolved"]:
            raise CommandError(
                f"{stats['values_unresolved']} RegionAttributeValue rows remain unresolved."
            )
