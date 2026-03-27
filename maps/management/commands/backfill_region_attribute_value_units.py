from collections import Counter

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from maps.models import RegionAttributeValue
from utils.object_management.models import get_default_owner
from utils.properties.models import Unit


class Command(BaseCommand):
    help = "Backfill RegionAttributeValue.unit from RegionProperty.unit labels."

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
        parser.add_argument(
            "--treat-blank-property-unit-as-no-unit",
            action="append",
            default=[],
            help="Treat blank RegionProperty.unit as the canonical 'No unit' for the given property name. Can be passed multiple times.",
        )

    def _resolve_canonical_no_unit(self, dry_run):
        owner = get_default_owner()
        unit_name = getattr(settings, "DEFAULT_NO_UNIT_NAME", "No unit")
        unit = Unit.objects.filter(owner=owner, name=unit_name).first()
        if unit is not None:
            return unit, False
        if dry_run:
            return Unit(owner=owner, name=unit_name, dimensionless=True), False
        return Unit.objects.get_or_create(
            owner=owner,
            name=unit_name,
            defaults={"dimensionless": True},
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        create_missing_units = options["create_missing_units"]
        fail_on_unresolved = options["fail_on_unresolved"]
        blank_property_unit_as_no_unit = {
            name.strip().casefold()
            for name in options["treat_blank_property_unit_as_no_unit"]
            if name and name.strip()
        }
        stats = {
            "values_examined": 0,
            "values_backfilled": 0,
            "values_unresolved": 0,
            "blank_property_unit": 0,
            "blank_property_unit_backfilled": 0,
            "units_created": 0,
        }
        blank_property_names = Counter()
        unresolved_labels = Counter()
        resolved_units = {}
        values = (
            RegionAttributeValue.objects.select_related("property")
            .filter(unit__isnull=True)
            .order_by("pk")
        )

        if dry_run:
            self.stdout.write("Dry run: no changes will be written.")

        for value in values.iterator():
            stats["values_examined"] += 1
            property_obj = value.property
            property_name = (
                property_obj.name or ""
            ).strip() or f"RegionProperty #{property_obj.pk}"
            unit_label = (property_obj.unit or "").strip()
            if not unit_label:
                stats["blank_property_unit"] += 1
                blank_property_names[property_name] += 1
                if property_name.casefold() not in blank_property_unit_as_no_unit:
                    continue

                cache_key = ("__canonical_no_unit__",)
                cache_entry = resolved_units.get(cache_key)
                if cache_entry is None:
                    cache_entry = self._resolve_canonical_no_unit(dry_run=dry_run)
                    resolved_units[cache_key] = cache_entry
                    if cache_entry[1]:
                        stats["units_created"] += 1
            else:
                cache_key = (property_obj.owner_id, unit_label)
                cache_entry = resolved_units.get(cache_key)
                if cache_entry is None:
                    unit = Unit.resolve_legacy_label(
                        unit_label, owner=property_obj.owner_id
                    )
                    created = False
                    if unit is None and create_missing_units:
                        if dry_run:
                            unit = Unit(
                                owner_id=property_obj.owner_id,
                                name=unit_label,
                                symbol=unit_label if len(unit_label) <= 63 else "",
                            )
                            created = True
                        else:
                            unit, created = Unit.objects.get_or_create(
                                owner_id=property_obj.owner_id,
                                name=unit_label,
                                defaults={
                                    "symbol": unit_label
                                    if len(unit_label) <= 63
                                    else "",
                                    "publication_status": property_obj.publication_status,
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
            if not unit_label:
                stats["blank_property_unit_backfilled"] += 1
            if not dry_run:
                value.unit_id = unit.pk
                value.save(update_fields=["unit"])

        for key in (
            "values_examined",
            "values_backfilled",
            "values_unresolved",
            "blank_property_unit",
            "blank_property_unit_backfilled",
            "units_created",
        ):
            self.stdout.write(f"{key}: {stats[key]}")

        if blank_property_names:
            self.stdout.write("Blank property units:")
            for property_name, count in blank_property_names.items():
                self.stdout.write(f"- {property_name}: {count}")

        if unresolved_labels:
            self.stdout.write("Unresolved labels:")
            for label, count in unresolved_labels.items():
                self.stdout.write(f"- {label}: {count}")

        remaining_blank_property_unit = (
            stats["blank_property_unit"] - stats["blank_property_unit_backfilled"]
        )
        remaining_unresolved = (
            stats["values_unresolved"] + remaining_blank_property_unit
        )
        if fail_on_unresolved and remaining_unresolved:
            raise CommandError(
                f"{remaining_unresolved} RegionAttributeValue rows remain unresolved."
            )
