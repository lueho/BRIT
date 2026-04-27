from django.core.management.base import BaseCommand, CommandError

from materials.composition_normalization import (
    WARNING_RAW_PERSISTED_MISMATCH,
    WARNING_RAW_UNNORMALIZABLE_FALLBACK,
    get_sample_normalized_compositions,
)
from materials.models import Sample


class Command(BaseCommand):
    help = "Report differences between raw-derived and saved normalized compositions."

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
            "--fail-on-mismatch",
            action="store_true",
            help="Raise a command error when raw-derived and saved compositions differ.",
        )

    def handle(self, *args, **options):
        sample_ids = options["sample_id"]
        summary_only = options["summary_only"]
        fail_on_mismatch = options["fail_on_mismatch"]

        samples = (
            Sample.objects.filter(
                component_measurements__isnull=False,
                compositions__shares__isnull=False,
            )
            .select_related("material")
            .distinct()
            .order_by("pk")
        )
        if sample_ids:
            samples = samples.filter(pk__in=sample_ids)

        stats = {
            "samples_examined": 0,
            "samples_with_mismatches": 0,
            "groups_with_mismatches": 0,
            "raw_unnormalizable_fallback_groups": 0,
        }
        mismatch_rows = []
        fallback_rows = []

        for sample in samples.iterator():
            stats["samples_examined"] += 1
            sample_has_mismatch = False
            for composition in get_sample_normalized_compositions(sample):
                warning_codes = set(composition.get("warning_codes", []))
                if WARNING_RAW_PERSISTED_MISMATCH in warning_codes:
                    sample_has_mismatch = True
                    stats["groups_with_mismatches"] += 1
                    mismatch_rows.append(self._build_row(sample, composition))
                if WARNING_RAW_UNNORMALIZABLE_FALLBACK in warning_codes:
                    stats["raw_unnormalizable_fallback_groups"] += 1
                    fallback_rows.append(self._build_row(sample, composition))
            if sample_has_mismatch:
                stats["samples_with_mismatches"] += 1

        for key in (
            "samples_examined",
            "samples_with_mismatches",
            "groups_with_mismatches",
            "raw_unnormalizable_fallback_groups",
        ):
            self.stdout.write(f"{key}: {stats[key]}")

        if not summary_only:
            self._write_rows("Mismatched raw-derived groups:", mismatch_rows)
            self._write_rows("Raw groups using saved fallback:", fallback_rows)

        if fail_on_mismatch and stats["groups_with_mismatches"]:
            raise CommandError(
                f"{stats['groups_with_mismatches']} composition groups differ from saved normalized values."
            )

    def _build_row(self, sample, composition):
        settings_pk = composition.get("settings_pk") or "none"
        return (
            f"- sample #{sample.pk} {sample.name}; "
            f"group #{composition['group']} {composition['group_name']}; "
            f"settings #{settings_pk}"
        )

    def _write_rows(self, title, rows):
        if not rows:
            return
        self.stdout.write(title)
        for row in rows:
            self.stdout.write(row)
