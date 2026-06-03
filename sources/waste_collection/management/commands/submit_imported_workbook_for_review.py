from collections import Counter
from datetime import date, datetime
from pathlib import Path

import openpyxl
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from sources.waste_collection.importers import CollectionImporter
from sources.waste_collection.models import (
    AggregatedCollectionPropertyValue,
    Collection,
    CollectionPropertyValue,
)
from sources.waste_collection.serializers import CollectionImportRecordSerializer
from utils.object_management.models import UserCreatedObject

User = get_user_model()


def _normalize_url(url) -> str | None:
    normalized = " ".join(str(url).split())
    if not normalized or len(normalized) > 2083:
        return None
    return normalized


def _resolve_date(value) -> date | None:
    """Convert various date formats to date object."""
    if value is None:
        return None
    if isinstance(value, date):
        # If it's already a date but not a datetime, return it
        if not isinstance(value, datetime):
            return value
        # If it's a datetime, convert to date
        return value.date()
    # Try to parse string
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        # Try common formats
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d"):
            try:
                parsed = datetime.strptime(value, fmt)
                return parsed.date()
            except ValueError:
                continue
    return None


def _split_source_cell(raw: str) -> tuple[list[str], list[str]]:
    """Split a source cell into URLs and notes."""
    if not raw:
        return [], []
    urls = []
    notes = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        if item.startswith("http"):
            urls.append(item)
        else:
            notes.append(item)
    return urls, notes


def _load_records(file_path: Path) -> tuple[list[dict], list[str], int]:
    """Load a generic workbook into importer-compatible records.

    Returns:
        Tuple of (valid_records, preflight_warnings, total_data_row_count).
    """
    workbook = openpyxl.load_workbook(str(file_path), read_only=True, data_only=True)
    rows = workbook.active.iter_rows(values_only=True)
    headers = next(rows, None)

    if not headers:
        return [], ["No headers found"], 0

    records: list[dict] = []
    warnings: list[str] = []
    row_count = 0

    for row_number, row in enumerate(rows, start=2):
        row_count += 1
        row_data = dict(zip(headers, row, strict=True))

        # Check for required fields (try common header names)
        collection_system = None
        for header in ["Collection System", "collection_system", "Collection system"]:
            if row_data.get(header):
                collection_system = row_data[header]
                break

        valid_from_raw = None
        for header in ["Valid from", "valid_from", "Valid From"]:
            if row_data.get(header):
                valid_from_raw = row_data[header]
                break
        valid_from = _resolve_date(valid_from_raw)

        missing = []
        if not collection_system:
            missing.append("collection_system")
        if not valid_from:
            missing.append("valid_from")

        if missing:
            catchment = (
                row_data.get("Catchment") or row_data.get("catchment") or "unknown"
            )
            warnings.append(
                f"Row {row_number} ({catchment!r}): "
                f"skipped — missing required field(s): {', '.join(missing)}"
            )
            continue

        # Convert to API payload format
        sources_raw = row_data.get("Sources_new") or row_data.get("sources_new") or ""
        sources_urls, sources_notes = _split_source_cell(sources_raw)
        weblinks_raw = row_data.get("Weblinks") or row_data.get("weblinks") or ""
        weblinks_urls, weblinks_notes = _split_source_cell(weblinks_raw)
        sources = sources_urls + sources_notes
        weblinks = weblinks_urls + weblinks_notes

        record = {
            "catchment": row_data.get("Catchment") or row_data.get("catchment"),
            "collection_system": collection_system,
            "waste_category": row_data.get("Waste Category")
            or row_data.get("waste_category"),
            "valid_from": valid_from,
            "allowed_materials": row_data.get("Allowed Materials")
            or row_data.get("allowed_materials")
            or "",
            "forbidden_materials": row_data.get("Forbidden Materials")
            or row_data.get("forbidden_materials")
            or "",
            "weblinks": weblinks,
            "sources": sources,
        }

        # Add property values if present
        for header in headers:
            if header and (
                "Specific Waste Collected" in str(header)
                or "Specific waste collected" in str(header)
            ):
                year_match = str(header).split()[-1]  # e.g., "2020"
                if year_match.isdigit():
                    year = int(year_match)
                    unit_header = f"{header} Unit"
                    unit = row_data.get(unit_header)
                    value = row_data.get(header)
                    if value is not None:
                        record[f"property_{year}"] = value
                        if unit:
                            record[f"property_{year}_unit"] = unit

        records.append(record)

    return records, warnings, row_count


class Command(BaseCommand):
    help = "Submit existing workbook-matched imports for a given owner to review."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            required=True,
            help="Path to the Excel workbook used for the import.",
        )
        parser.add_argument(
            "--owner",
            required=True,
            help="Username owning the imported objects to submit.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be submitted without writing to the database.",
        )

    def handle(self, *args, **options):
        file_path = Path(options["file"])
        if not file_path.exists():
            raise CommandError(f"Excel file not found: {file_path}")

        try:
            owner = User.objects.get(username=options["owner"])
        except User.DoesNotExist as err:
            raise CommandError(f"User '{options['owner']}' does not exist.") from err

        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write("DRY RUN — no records will be written.\n")

        records_raw, local_warnings, row_count = _load_records(file_path)
        self.stdout.write(
            f"Loaded {len(records_raw)} valid record(s) from {file_path.name} "
            f"({row_count} data row(s))."
        )
        if local_warnings:
            raise CommandError("\n".join(local_warnings))

        serializer = CollectionImportRecordSerializer(data=records_raw, many=True)
        serializer.is_valid(raise_exception=True)
        records = list(serializer.validated_data)

        matcher = CollectionImporter(owner=owner, publication_status="private")
        matcher._load_lookups()
        submitter = CollectionImporter(owner=owner, publication_status="review")

        matched_collections: dict[int, dict[str, set[str]]] = {}
        matching_errors = []

        for index, record in enumerate(records, start=1):
            label = f"{file_path.name} record {index}"
            stats = {"warnings": []}
            collection_system = matcher._resolve_collection_system(record, label, stats)
            waste_category = matcher._resolve_waste_category(record, label, stats)
            valid_from = record.get("valid_from")
            allowed_materials, forbidden_materials = matcher._resolve_material_lists(
                record,
                label,
                stats,
            )
            allowed_material_ids = matcher._material_ids(allowed_materials)
            forbidden_material_ids = matcher._material_ids(forbidden_materials)
            catchment = matcher._resolve_catchment(
                record,
                label,
                stats,
                collector=matcher._lookup_known_collector(record),
                collection_system=collection_system,
                waste_category=waste_category,
                allowed_material_ids=allowed_material_ids,
                forbidden_material_ids=forbidden_material_ids,
                valid_from=valid_from,
            )

            if stats["warnings"]:
                matching_errors.extend(stats["warnings"])
                continue

            collection = (
                Collection.objects.filter(
                    owner=owner,
                    catchment=catchment,
                    collection_system=collection_system,
                    valid_from=valid_from,
                    waste_category=waste_category,
                )
                .match_materials(
                    allowed_materials=allowed_material_ids,
                    forbidden_materials=forbidden_material_ids,
                )
                .order_by("-id")
                .first()
            )
            if collection is None:
                matching_errors.append(
                    f"{label}: no matching collection owned by '{owner.username}' found."
                )
                continue

            expected = matched_collections.setdefault(
                collection.pk,
                {"source_titles": set(), "flyer_urls": set()},
            )
            expected["source_titles"].update(
                title for title in (record.get("sources") or []) if title
            )
            expected["flyer_urls"].update(
                filter(
                    None,
                    (_normalize_url(url) for url in (record.get("flyer_urls") or [])),
                )
            )

        if matching_errors:
            raise CommandError("\n".join(matching_errors))

        stats = Counter()
        seen_collection_ids: set[int] = set()
        seen_cpv_ids: set[int] = set()
        seen_acpv_ids: set[int] = set()
        seen_source_ids: set[int] = set()
        seen_flyer_ids: set[int] = set()

        with transaction.atomic():
            for collection_id, expected_refs in matched_collections.items():
                collection = Collection.objects.get(pk=collection_id)
                self._process_object(
                    submitter,
                    collection,
                    "collections",
                    seen_collection_ids,
                    stats,
                    dry_run=dry_run,
                )

                versions = collection.all_versions()
                cpvs = (
                    CollectionPropertyValue.objects.filter(collection__in=versions)
                    .filter(Q(owner=owner) | Q(collection__owner=owner))
                    .select_related("collection")
                    .distinct()
                )
                for cpv in cpvs:
                    self._process_object(
                        submitter,
                        cpv,
                        "cpvs",
                        seen_cpv_ids,
                        stats,
                        dry_run=dry_run,
                    )

                acpvs = (
                    AggregatedCollectionPropertyValue.objects.filter(
                        collections__in=versions
                    )
                    .filter(owner=owner)
                    .distinct()
                )
                for acpv in acpvs:
                    self._process_object(
                        submitter,
                        acpv,
                        "acpvs",
                        seen_acpv_ids,
                        stats,
                        dry_run=dry_run,
                    )

                if expected_refs["source_titles"]:
                    for source in collection.sources.filter(
                        owner=owner,
                        title__in=expected_refs["source_titles"],
                    ):
                        self._process_object(
                            submitter,
                            source,
                            "sources",
                            seen_source_ids,
                            stats,
                            dry_run=dry_run,
                        )

                if expected_refs["flyer_urls"]:
                    for flyer in collection.flyers.filter(
                        owner=owner,
                        url__in=expected_refs["flyer_urls"],
                    ):
                        self._process_object(
                            submitter,
                            flyer,
                            "flyers",
                            seen_flyer_ids,
                            stats,
                            dry_run=dry_run,
                        )

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write("\n=== Review Submission Summary ===")
        self.stdout.write(f"  Collections matched:      {len(matched_collections)}")
        for prefix, label in (
            ("collections", "Collections"),
            ("cpvs", "CPVs"),
            ("acpvs", "ACPVs"),
            ("sources", "Sources"),
            ("flyers", "Flyers"),
        ):
            self.stdout.write(
                f"  {label} targeted:         {stats.get(f'{prefix}_targeted', 0)}"
            )
            self.stdout.write(
                f"  {label} submitted:        {stats.get(f'{prefix}_submitted', 0)}"
            )
            self.stdout.write(
                f"  {label} already review:   {stats.get(f'{prefix}_already_review', 0)}"
            )
            self.stdout.write(
                f"  {label} already published:{stats.get(f'{prefix}_already_published', 0):>4}"
            )
            self.stdout.write(
                f"  {label} other status:     {stats.get(f'{prefix}_other_status', 0)}"
            )

    @staticmethod
    def _process_object(
        submitter: CollectionImporter,
        obj,
        prefix: str,
        seen_ids: set[int],
        stats: Counter,
        *,
        dry_run: bool,
    ) -> None:
        if obj.pk in seen_ids:
            return

        seen_ids.add(obj.pk)
        stats[f"{prefix}_targeted"] += 1

        if obj.publication_status in (
            UserCreatedObject.STATUS_PRIVATE,
            UserCreatedObject.STATUS_DECLINED,
        ):
            stats[f"{prefix}_submitted"] += 1
            if not dry_run:
                submitter._submit_for_review(obj)
            return

        if obj.publication_status == UserCreatedObject.STATUS_REVIEW:
            stats[f"{prefix}_already_review"] += 1
            return

        if obj.publication_status == UserCreatedObject.STATUS_PUBLISHED:
            stats[f"{prefix}_already_published"] += 1
            return

        stats[f"{prefix}_other_status"] += 1
