from django.core.management.base import BaseCommand

from materials.models import Sample


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

    def handle(self, *args, **options):
        sample_ids = options["sample_id"]
        summary_only = options["summary_only"]

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
        }
        candidate_rows = []

        for sample in samples.iterator():
            stats["samples_examined"] += 1
            raw_group_ids = set(
                sample.component_measurements.values_list("group_id", flat=True)
            )
            compositions = (
                sample.compositions.filter(shares__isnull=False)
                .exclude(group_id__in=raw_group_ids)
                .select_related("group")
                .distinct()
                .order_by("order", "pk")
            )
            sample_has_candidates = False
            for composition in compositions:
                sample_has_candidates = True
                share_count = composition.shares.count()
                stats["groups_with_backfill_candidates"] += 1
                stats["saved_weightshares_to_backfill"] += share_count
                candidate_rows.append(
                    self._build_row(
                        sample=sample,
                        composition=composition,
                        share_count=share_count,
                    )
                )
            if sample_has_candidates:
                stats["samples_with_backfill_candidates"] += 1

        for key in (
            "samples_examined",
            "samples_with_backfill_candidates",
            "groups_with_backfill_candidates",
            "saved_weightshares_to_backfill",
        ):
            self.stdout.write(f"{key}: {stats[key]}")

        if not summary_only:
            self._write_rows(
                "Saved normalized groups without raw measurements:", candidate_rows
            )

    def _build_row(self, *, sample, composition, share_count):
        return (
            f"- sample #{sample.pk} {sample.name}; "
            f"group #{composition.group_id} {composition.group.name}; "
            f"settings #{composition.pk}; saved shares {share_count}"
        )

    def _write_rows(self, title, rows):
        if not rows:
            return
        self.stdout.write(title)
        for row in rows:
            self.stdout.write(row)
