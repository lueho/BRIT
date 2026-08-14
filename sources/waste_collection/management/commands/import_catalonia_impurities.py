"""Import 2024 Catalonia biowaste impurity rates from the research TSV."""

import csv
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils.encoding import iri_to_uri

from sources.waste_collection.models import (
    Collection,
    CollectionPropertyValue,
    WasteFlyer,
)
from utils.object_management.models import ReviewAction
from utils.properties.models import Property, Unit

User = get_user_model()

PROPERTY_NAME = "biowaste impurity rate"
UNIT_NAME = "%"
WASTE_CATEGORY = "Biowaste"
REQUIRED_COLUMNS = {
    "codi",
    "Catchment",
    "Waste_Category",
    "Collection_system_2024",
    "Impurities_percentage_2024",
    "Sources",
}
COLLECTION_SYSTEM_NAMES = {
    "Bring point": "Bring point",
    "Door-to-door": "Door to door",
    "Mixed Door-to-door and Bring point": "Mixed door-to-door and bring point",
}


@dataclass(frozen=True)
class ImpurityRow:
    line_number: int
    municipality_name: str
    lau_id: str
    collection_system: str
    average: float
    source_urls: tuple[str, ...]
    source_corrections: tuple[str, ...]


def catalan_code_to_lau_id(raw_code: str) -> str:
    """Convert a six-digit Catalan municipality code to its five-digit LAU id."""
    code = raw_code.strip()
    if not code.isdigit() or len(code) > 6:
        raise ValueError(f"invalid Catalan municipality code '{raw_code}'")
    return code.zfill(6)[:-1]


def parse_source_urls(raw_sources: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    urls = []
    corrections = []
    for raw_url in raw_sources.split(", "):
        raw_url = raw_url.strip()
        if not raw_url:
            continue
        if raw_url.startswith("ttps://"):
            corrections.append(f"{raw_url} -> h{raw_url}")
            raw_url = f"h{raw_url}"
        url = iri_to_uri(raw_url)
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError(f"invalid source URL '{raw_url}'")
        urls.append(url)
    return tuple(dict.fromkeys(urls)), tuple(corrections)


def load_impurity_rows(path: Path, year: int) -> list[ImpurityRow]:
    value_column = f"Impurities_percentage_{year}"
    system_column = f"Collection_system_{year}"
    required_columns = REQUIRED_COLUMNS | {value_column, system_column}

    try:
        handle = path.open(encoding="cp1252", newline="")
    except OSError as exc:
        raise CommandError(f"Could not open '{path}': {exc}") from exc

    with handle:
        reader = csv.DictReader(handle, delimiter="\t")
        missing = sorted(required_columns - set(reader.fieldnames or ()))
        if missing:
            raise CommandError(f"Missing required CSV columns: {', '.join(missing)}")

        rows = []
        seen_lau_ids = set()
        for line_number, raw in enumerate(reader, start=2):
            if raw["Waste_Category"].strip() != WASTE_CATEGORY:
                continue
            raw_average = raw[value_column].strip()
            if not raw_average:
                continue

            try:
                lau_id = catalan_code_to_lau_id(raw["codi"])
                average = float(raw_average.replace(",", "."))
                source_urls, source_corrections = parse_source_urls(raw["Sources"])
            except ValueError as exc:
                raise CommandError(f"Line {line_number}: {exc}") from exc

            if not math.isfinite(average) or not 0 <= average <= 100:
                raise CommandError(
                    f"Line {line_number}: impurity percentage must be between 0 and 100."
                )
            if lau_id in seen_lau_ids:
                raise CommandError(
                    f"Line {line_number}: duplicate Biowaste row for LAU id '{lau_id}'."
                )
            seen_lau_ids.add(lau_id)

            raw_system = raw[system_column].strip()
            collection_system = COLLECTION_SYSTEM_NAMES.get(raw_system)
            if collection_system is None:
                raise CommandError(
                    f"Line {line_number}: unsupported collection system '{raw_system}'."
                )

            rows.append(
                ImpurityRow(
                    line_number=line_number,
                    municipality_name=raw["Catchment"].strip(),
                    lau_id=lau_id,
                    collection_system=collection_system,
                    average=average,
                    source_urls=source_urls,
                    source_corrections=source_corrections,
                )
            )
    return rows


def find_collection(row: ImpurityRow, year: int) -> Collection:
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    candidates = list(
        Collection.objects.filter(
            catchment__region__lauregion__lau_id=row.lau_id,
            catchment__region__lauregion__cntr_code="ES",
            waste_category__name=WASTE_CATEGORY,
            valid_from__lte=year_end,
        )
        .filter(Q(valid_until__isnull=True) | Q(valid_until__gte=year_start))
        .select_related("catchment", "collection_system", "owner")
    )
    label = f"{row.municipality_name} (LAU {row.lau_id}, line {row.line_number})"
    if not candidates:
        raise CommandError(f"No active {year} Biowaste collection for {label}.")
    if len(candidates) > 1:
        raise CommandError(
            f"Multiple active {year} Biowaste collections for {label}: "
            f"{', '.join(str(collection.pk) for collection in candidates)}."
        )

    collection = candidates[0]
    if collection.collection_system.name != row.collection_system:
        raise CommandError(
            f"Collection system mismatch for {label}: CSV has '{row.collection_system}', "
            f"BRIT has '{collection.collection_system.name}'."
        )
    return collection


class Command(BaseCommand):
    help = (
        "Import municipality-level Catalonia biowaste impurity rates from a "
        "Windows-1252 tab-separated research CSV."
    )

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=Path)
        parser.add_argument("--year", type=int, default=2024)
        parser.add_argument(
            "--owner",
            help="Username for new values and source records; defaults to each collection owner.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and report all changes, then roll back the transaction.",
        )

    def handle(self, *args, **options):
        path = options["csv_path"]
        year = options["year"]
        dry_run = options["dry_run"]
        owner = self._get_owner(options.get("owner"))
        rows = load_impurity_rows(path, year)

        if dry_run:
            self.stdout.write("DRY RUN — no records will be written.")
        self.stdout.write(f"Loaded {len(rows)} eligible rows.")
        for row in rows:
            for correction in row.source_corrections:
                self.stdout.write(
                    self.style.WARNING(
                        f"Line {row.line_number}: corrected source URL: {correction}"
                    )
                )

        try:
            impurity_property = Property.objects.get(name=PROPERTY_NAME)
        except Property.DoesNotExist:
            raise CommandError(f"Property '{PROPERTY_NAME}' does not exist.") from None
        try:
            unit = Unit.objects.get(name=UNIT_NAME)
        except Unit.DoesNotExist:
            raise CommandError(f"Unit '{UNIT_NAME}' does not exist.") from None
        if not impurity_property.allowed_units.filter(pk=unit.pk).exists():
            raise CommandError(
                f"Unit '{UNIT_NAME}' is not allowed for property '{PROPERTY_NAME}'."
            )

        resolved_rows = [(row, find_collection(row, year)) for row in rows]
        stats = {"created": 0, "updated": 0, "unchanged": 0, "sources_created": 0}

        with transaction.atomic():
            for row, collection in resolved_rows:
                value_owner = owner or collection.owner
                value = (
                    CollectionPropertyValue.objects.filter(
                        collection=collection,
                        property=impurity_property,
                        year=year,
                        is_derived=False,
                    )
                    .order_by("pk")
                    .first()
                )
                if value is None:
                    value = CollectionPropertyValue.objects.create(
                        name=f"{collection.name} {PROPERTY_NAME} {year}",
                        owner=value_owner,
                        publication_status="private",
                        collection=collection,
                        property=impurity_property,
                        unit=unit,
                        year=year,
                        average=row.average,
                    )
                    stats["created"] += 1
                else:
                    if value.publication_status == value.STATUS_PUBLISHED and (
                        value.average != row.average or value.unit_id != unit.pk
                    ):
                        raise CommandError(
                            f"Refusing to modify published impurity value {value.pk} "
                            f"for {row.municipality_name}."
                        )
                    changed_fields = []
                    if value.average != row.average:
                        value.average = row.average
                        changed_fields.append("average")
                    if value.unit_id != unit.pk:
                        value.unit = unit
                        changed_fields.append("unit")
                    if changed_fields:
                        value.save(update_fields=[*changed_fields, "lastmodified_at"])
                        stats["updated"] += 1
                    else:
                        stats["unchanged"] += 1

                self._attach_sources(value, row.source_urls, value_owner, stats)
                if value.publication_status in (
                    value.STATUS_PRIVATE,
                    value.STATUS_DECLINED,
                ):
                    self._submit_for_review(value, value_owner)

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(
            self.style.SUCCESS(
                "Done: "
                f"{stats['created']} created, "
                f"{stats['updated']} updated, "
                f"{stats['unchanged']} unchanged, "
                f"{stats['sources_created']} sources created."
            )
        )

    @staticmethod
    def _get_owner(username):
        if not username:
            return None
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f"User '{username}' does not exist.") from None

    @staticmethod
    def _attach_sources(value, urls, owner, stats):
        for url in urls:
            flyer, created = WasteFlyer.objects.get_or_create_by_url(
                url=url,
                defaults={
                    "owner": owner,
                    "title": (urlparse(url).hostname or url)[:255],
                    "publication_status": "private",
                },
            )
            value.sources.add(flyer)
            if created:
                stats["sources_created"] += 1
                Command._submit_for_review(flyer, owner)

    @staticmethod
    def _submit_for_review(obj, owner):
        obj.submit_for_review()
        ReviewAction.objects.create(
            content_type=ContentType.objects.get_for_model(obj),
            object_id=obj.pk,
            user=owner,
            action=ReviewAction.ACTION_SUBMITTED,
            comment="",
        )
