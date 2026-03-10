import sys

from django.core.management.base import BaseCommand, CommandError

from sources.waste_collection.crosswalk import validate_crosswalk_mappings as source_validate_crosswalk_mappings


validate_crosswalk_mappings = source_validate_crosswalk_mappings


def _compat_validate_crosswalk_mappings():
    legacy_module = sys.modules.get(
        "case_studies.soilcom.management.commands.validate_soilcom_crosswalks"
    )
    if legacy_module is not None and hasattr(legacy_module, "validate_crosswalk_mappings"):
        return getattr(legacy_module, "validate_crosswalk_mappings")
    return validate_crosswalk_mappings


class Command(BaseCommand):
    """Validate Soilcom crosswalk CSV assets against the controlled vocabulary."""

    help = "Validate Soilcom crosswalk CSV assets against canonical concept URIs."

    def handle(self, *args, **options):
        errors = _compat_validate_crosswalk_mappings()()
        if errors:
            raise CommandError("\n".join(errors))

        self.stdout.write(self.style.SUCCESS("Soilcom crosswalk validation passed."))
