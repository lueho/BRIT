from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from sources.waste_collection.importers import CollectionImporter
from sources.waste_collection.management.commands.import_bw_2024_collections import (
    _BATCH_SIZE,
    _VALID_STATUSES,
    _load_records,
)
from sources.waste_collection.serializers import CollectionImportRecordSerializer

User = get_user_model()

_IMPORT_STAT_KEYS = (
    "created",
    "updated",
    "unchanged",
    "skipped",
    "predecessor_links",
    "cpv_created",
    "cpv_unchanged",
    "cpv_skipped",
    "flyers_created",
    "sources_created",
)


def _format_validation_errors(errors: list, records_raw: list[dict]) -> list[str]:
    messages = []
    for index, error in enumerate(errors):
        if not error:
            continue
        excel_row = records_raw[index].get("_excel_row")
        label = f"Row {excel_row}" if excel_row else f"Record {index + 1}"
        messages.append(f"{label}: {error}")
    return messages


class Command(BaseCommand):
    help = "Repair Baden-Württemberg 2024 waste collection imports locally."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default=None,
            help=(
                "Path to the Baden-Württemberg workbook "
                "(default: BRIT_Deutschland_Baden-Württemberg_2024_SW1.xlsx)."
            ),
        )
        parser.add_argument(
            "--owner",
            required=True,
            help="Username to use as owner for created and updated imported objects.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and simulate the repair without committing database changes.",
        )
        parser.add_argument(
            "--publication-status",
            type=str,
            default="private",
            choices=_VALID_STATUSES,
            help="Publication status for created records (default: private).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=_BATCH_SIZE,
            help=f"Number of records per importer batch (default: {_BATCH_SIZE}).",
        )
        parser.add_argument(
            "--excel-row",
            action="append",
            type=int,
            default=[],
            help=(
                "Optional 1-indexed Excel row number to repair. "
                "Repeat this option to target multiple rows."
            ),
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        publication_status = options["publication_status"]
        batch_size = options["batch_size"]
        file_path = options["file"]
        owner_username = options["owner"]
        excel_rows = set(options["excel_row"] or [])

        if batch_size < 1:
            raise CommandError("--batch-size must be at least 1.")
        invalid_rows = sorted(row for row in excel_rows if row < 2)
        if invalid_rows:
            raise CommandError(
                "Excel row numbers must be >= 2 (row 1 is the header): "
                f"{', '.join(str(row) for row in invalid_rows)}"
            )

        try:
            owner = User.objects.get(username=owner_username)
        except User.DoesNotExist as err:
            raise CommandError(f"User '{owner_username}' does not exist.") from err

        if file_path is None:
            file_path = Path("BRIT_Deutschland_Baden-Württemberg_2024_SW1.xlsx")
        else:
            file_path = Path(file_path)

        if not file_path.exists():
            raise CommandError(f"Excel file not found: {file_path}")

        if dry_run:
            self.stdout.write("DRY RUN — no records will be written.\n")
        if excel_rows:
            self.stdout.write(
                "Targeting Excel row(s): "
                f"{', '.join(str(row) for row in sorted(excel_rows))}\n"
            )

        records_raw, local_warnings, row_count = _load_records(
            file_path,
            excel_rows=excel_rows or None,
        )
        self.stdout.write(
            f"Loaded {len(records_raw)} valid record(s) from {file_path.name} "
            f"({row_count} data row(s)).\n"
        )

        invalid_rows = sorted(row for row in excel_rows if row > row_count + 1)
        if invalid_rows:
            raise CommandError(
                "Excel row number(s) out of range for workbook: "
                f"{', '.join(str(row) for row in invalid_rows)}"
            )

        if local_warnings:
            self.stdout.write(
                f"Pre-flight: skipping {len(local_warnings)} invalid row(s).\n"
            )

        serializer_input = [
            {key: value for key, value in record.items() if not key.startswith("_")}
            for record in records_raw
        ]
        serializer = CollectionImportRecordSerializer(data=serializer_input, many=True)
        if not serializer.is_valid():
            raise CommandError(
                "\n".join(_format_validation_errors(serializer.errors, records_raw))
            )
        records = list(serializer.validated_data)

        totals = dict.fromkeys(_IMPORT_STAT_KEYS, 0)
        totals["warnings"] = []
        totals["skipped"] += len(local_warnings)

        importer = CollectionImporter(
            owner=owner,
            publication_status=publication_status,
        )
        batches = [
            records[i : i + batch_size] for i in range(0, len(records), batch_size)
        ]

        for index, batch in enumerate(batches, start=1):
            self.stdout.write(
                f"  Repair batch {index}/{len(batches)} ({len(batch)} records)…"
            )
            stats = importer.run(batch, dry_run=dry_run)
            for key in _IMPORT_STAT_KEYS:
                totals[key] += stats.get(key, 0)
            totals["warnings"].extend(stats.get("warnings", []))
            self.stdout.write(
                " "
                f"created={stats.get('created', 0)} "
                f"updated={stats.get('updated', 0)} "
                f"unchanged={stats.get('unchanged', 0)} "
                f"skipped={stats.get('skipped', 0)}\n"
            )

        self.stdout.write("\n=== BW Repair Summary ===\n")
        self.stdout.write(f"  Collections created:  {totals['created']}\n")
        self.stdout.write(f"  Collections updated:  {totals['updated']}\n")
        self.stdout.write(f"  Collections unchanged:{totals['unchanged']:>4}\n")
        self.stdout.write(f"  Collections skipped:  {totals['skipped']}\n")
        self.stdout.write(f"  Predecessor links:    {totals['predecessor_links']}\n")
        self.stdout.write(f"  CPVs created:         {totals['cpv_created']}\n")
        self.stdout.write(f"  CPVs unchanged:       {totals['cpv_unchanged']}\n")
        self.stdout.write(f"  CPVs skipped:         {totals['cpv_skipped']}\n")
        self.stdout.write(f"  Flyers created:       {totals['flyers_created']}\n")
        self.stdout.write(f"  Sources created:      {totals['sources_created']}\n")

        all_warnings = local_warnings + totals["warnings"]
        if all_warnings:
            self.stdout.write(f"\n  Warnings ({len(all_warnings)}):\n")
            for warning in all_warnings:
                self.stdout.write(f"    {warning}\n")
