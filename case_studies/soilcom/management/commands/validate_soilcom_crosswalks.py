from django.core.management.base import BaseCommand, CommandError

from case_studies.soilcom.crosswalk import validate_crosswalk_mappings


class Command(BaseCommand):
    """Validate Soilcom crosswalk CSV assets against the controlled vocabulary."""

    help = "Validate Soilcom crosswalk CSV assets against canonical concept URIs."

    def handle(self, *args, **options):
        errors = validate_crosswalk_mappings()
        if errors:
            raise CommandError("\n".join(errors))

        self.stdout.write(self.style.SUCCESS("Soilcom crosswalk validation passed."))
