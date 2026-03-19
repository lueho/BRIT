from collections import Counter
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from sources.waste_collection.importers import CollectionImporter
from sources.waste_collection.management.commands.import_de_2024_improved_standalone import (
    _load_records,
)
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
