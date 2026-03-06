"""Export Soilcom controlled vocabulary snapshots.

Usage::

    docker compose exec web python manage.py export_soilcom_vocabulary
    docker compose exec web python manage.py export_soilcom_vocabulary \
        --output /app/case_studies/soilcom/ontology/export/controlled_vocabulary.json
    docker compose exec web python manage.py export_soilcom_vocabulary --fail-on-unmapped
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from case_studies.soilcom.vocabulary import get_waste_collection_controlled_vocabulary


class Command(BaseCommand):
    """Write the current controlled vocabulary to a JSON file."""

    help = (
        "Export a JSON snapshot of the Soilcom controlled vocabulary for "
        "ontology and harmonization workflows."
    )

    def add_arguments(self, parser):
        """Register management command arguments."""
        parser.add_argument(
            "--output",
            type=str,
            default="/app/case_studies/soilcom/ontology/export/controlled_vocabulary.json",
            help="Output file path for the JSON snapshot.",
        )
        parser.add_argument(
            "--fail-on-unmapped",
            action="store_true",
            help="Exit with error when country codes without language mappings exist.",
        )

    def handle(self, *args, **options):
        """Execute the export."""
        snapshot = get_waste_collection_controlled_vocabulary()
        output_path = Path(options["output"]).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(snapshot, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        self.stdout.write(self.style.SUCCESS(f"Vocabulary written to {output_path}"))

        unmapped = snapshot.get("unmapped_countries") or []
        if unmapped:
            self.stdout.write(
                self.style.WARNING(
                    "Unmapped country codes in collection data: " + ", ".join(unmapped)
                )
            )
            if options["fail_on_unmapped"]:
                raise CommandError(
                    "Controlled vocabulary export failed because unmapped countries exist."
                )
