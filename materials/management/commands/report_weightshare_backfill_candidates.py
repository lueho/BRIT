from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from materials.models import ComponentMeasurement, Sample
from utils.properties.models import Unit


class Command(BaseCommand):
    help = "Report saved normalized composition rows that may need raw measurement backfill."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sample-id",
            action="append",
            type=int,
            default=[],
            help="Limit the report to one sample id. Can be passed multiple times.",
        )
        parser.add_argument(
            "--summary-only",
            action="store_true",
            help="Only print summary counters.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Create missing raw component measurements. Defaults to dry-run.",
        )
        parser.add_argument(
            "--unit-name",
            default="%",
            help="Unit name to use for created component measurements.",
        )
        parser.add_argument(
            "--fail-on-candidates",
            action="store_true",
            help="Raise a command error when backfill candidates exist.",
        )

    def handle(self, *args, **options):
        sample_ids = options["sample_id"]
        summary_only = options["summary_only"]
        apply_changes = options["apply"]
        unit_name = options["unit_name"]
        fail_on_candidates = options["fail_on_candidates"]
        unit = Unit.objects.filter(name=unit_name).first()
        if unit is None:
            raise CommandError(f'Unit "{unit_name}" does not exist.')

        samples = (
            Sample.objects.filter(compositions__shares__isnull=False)
            .select_related("material")
            .distinct()
            .order_by("pk")
        )
        if sample_ids:
            samples = samples.filter(pk__in=sample_ids)

        stats = {
            "samples_examined": 0,
            "samples_with_backfill_candidates": 0,
            "groups_with_backfill_candidates": 0,
            "saved_weightshares_to_backfill": 0,
            "component_measurements_created": 0,
        }
        candidate_rows = []

        with transaction.atomic():
            for sample in samples.iterator():
                stats["samples_examined"] += 1
                raw_group_ids = set(
                    sample.component_measurements.values_list("group_id", flat=True)
                )
                compositions = (
                    sample.compositions.filter(shares__isnull=False)
                    .exclude(group_id__in=raw_group_ids)
                    .select_related("group")
                    .prefetch_related("shares")
                    .distinct()
                    .order_by("order", "pk")
                )
                sample_has_candidates = False
                for composition in compositions:
                    sample_has_candidates = True
                    shares = list(composition.shares.select_related("component"))
                    share_count = len(shares)
                    stats["groups_with_backfill_candidates"] += 1
                    stats["saved_weightshares_to_backfill"] += share_count
                    candidate_rows.append(
                        self._build_row(
                            sample=sample,
                            composition=composition,
                            share_count=share_count,
                        )
                    )
                    if apply_changes:
                        stats["component_measurements_created"] += (
                            self._create_component_measurements(
                                composition=composition,
                                shares=shares,
                                unit=unit,
                            )
                        )
                if sample_has_candidates:
                    stats["samples_with_backfill_candidates"] += 1

            if not apply_changes:
                transaction.set_rollback(True)

        for key in (
            "samples_examined",
            "samples_with_backfill_candidates",
            "groups_with_backfill_candidates",
            "saved_weightshares_to_backfill",
            "component_measurements_created",
        ):
            self.stdout.write(f"{key}: {stats[key]}")

        if not summary_only:
            self._write_rows(
                "Saved normalized groups without raw measurements:", candidate_rows
            )

        if fail_on_candidates and stats["groups_with_backfill_candidates"]:
            raise CommandError(
                f"{stats['groups_with_backfill_candidates']} composition groups need raw measurement backfill."
            )

    def _build_row(self, *, sample, composition, share_count):
        return (
            f"- sample #{sample.pk} {sample.name}; "
            f"group #{composition.group_id} {composition.group.name}; "
            f"settings #{composition.pk}; saved shares {share_count}"
        )

    def _create_component_measurements(self, *, composition, shares, unit):
        created_count = 0
        for share in shares:
            ComponentMeasurement.objects.create(
                owner=share.owner or composition.owner,
                sample=composition.sample,
                group=composition.group,
                component=share.component,
                basis_component=composition.fractions_of,
                unit=unit,
                average=share.average * 100,
                standard_deviation=share.standard_deviation * 100,
            )
            created_count += 1
        return created_count

    def _write_rows(self, title, rows):
        if not rows:
            return
        self.stdout.write(title)
        for row in rows:
            self.stdout.write(row)
