"""Management command to backfill derived CollectionPropertyValue records.

Creates the counterpart (specific ↔ total waste collected) for every
existing non-derived CPV where the counterpart does not yet exist as a
manual entry.

Usage::

    docker compose exec web python manage.py backfill_derived_cpv
    docker compose exec web python manage.py backfill_derived_cpv --dry-run
"""

from django.core.management.base import BaseCommand

from case_studies.soilcom.derived_values import backfill_derived_values


class Command(BaseCommand):
    help = "Backfill derived CollectionPropertyValue records (specific ↔ total waste collected)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created/updated without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write("DRY RUN — no records will be written.\n")

        stats = backfill_derived_values(dry_run=dry_run)

        self.stdout.write(
            f"Done: {stats['created']} created, "
            f"{stats['updated']} updated, "
            f"{stats['skipped']} skipped.\n"
        )
