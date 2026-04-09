from django.core.management.base import BaseCommand, CommandError

from sources.waste_collection.crosswalk import (
    validate_crosswalk_mappings as source_validate_crosswalk_mappings,
)

validate_crosswalk_mappings = source_validate_crosswalk_mappings


class Command(BaseCommand):
    """Validate waste_collection crosswalk CSV assets against the controlled vocabulary."""

    help = (
        "Validate waste_collection crosswalk CSV assets against canonical concept URIs."
    )

    def handle(self, *args, **options):
        errors = validate_crosswalk_mappings()
        if errors:
            raise CommandError("\n".join(errors))

        self.stdout.write(
            self.style.SUCCESS("Waste collection crosswalk validation passed.")
        )
