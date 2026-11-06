"""Refresh source-linked, read-only collection projections.

Each convertible raw CPV owns its generated counterpart. Manual evidence and
unlinked legacy generated rows are never adopted or deleted by resemblance.
Owner/status overrides copy compatibility metadata only; source evidence
still governs access and review.

Usage::

    docker compose exec web python manage.py backfill_derived_cpv
    docker compose exec web python manage.py backfill_derived_cpv --dry-run
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from sources.waste_collection.derived_values import backfill_derived_values

User = get_user_model()

_VALID_STATUSES = ("private", "review", "published", "declined", "archived")


class Command(BaseCommand):
    help = "Backfill source-linked, read-only collection projections."

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
            help="Copy this username into projection compatibility metadata. "
            "Defaults to the source owner; does not grant access.",
        )
        parser.add_argument(
            "--publication-status",
            type=str,
            default=None,
            choices=_VALID_STATUSES,
            help="Copy this status into projection compatibility metadata. "
            "Defaults to the source status; does not publish or approve evidence.",
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
