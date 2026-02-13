"""Management command to backfill derived CollectionPropertyValue records.

Creates the counterpart (specific ↔ total waste collected) for every
existing non-derived CPV where the counterpart does not yet exist as a
manual entry.

Usage::

    docker compose exec web python manage.py backfill_derived_cpv
    docker compose exec web python manage.py backfill_derived_cpv --dry-run
    docker compose exec web python manage.py backfill_derived_cpv --owner admin --publication-status published
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from case_studies.soilcom.derived_values import backfill_derived_values

User = get_user_model()

_VALID_STATUSES = ("private", "review", "published", "declined", "archived")


class Command(BaseCommand):
    help = "Backfill derived CollectionPropertyValue records (specific ↔ total waste collected)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created/updated without writing to the database.",
        )
        parser.add_argument(
            "--owner",
            type=str,
            default=None,
            help="Username to set as owner of created/updated derived records. "
            "Defaults to the source CPV's owner.",
        )
        parser.add_argument(
            "--publication-status",
            type=str,
            default=None,
            choices=_VALID_STATUSES,
            help="Publication status for created/updated derived records. "
            "Defaults to the source CPV's publication status.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        owner_username = options["owner"]
        publication_status = options["publication_status"]

        owner = None
        if owner_username:
            try:
                owner = User.objects.get(username=owner_username)
            except User.DoesNotExist:
                raise CommandError(f"User '{owner_username}' does not exist.") from None

        if dry_run:
            self.stdout.write("DRY RUN — no records will be written.\n")

        stats = backfill_derived_values(
            dry_run=dry_run,
            owner=owner,
            publication_status=publication_status,
        )

        self.stdout.write(
            f"Done: {stats['created']} created, "
            f"{stats['updated']} updated, "
            f"{stats['skipped']} skipped.\n"
        )
