"""Collection import logic shared by the management command and the API endpoint."""

from __future__ import annotations

import re
from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from bibliography.models import Source
from materials.models import Material
from sources.waste_collection.models import (
    BinConfiguration,
    Collection,
    CollectionCatchment,
    CollectionCountOptions,
    CollectionFrequency,
    CollectionPropertyValue,
    CollectionSeason,
    CollectionSystem,
    Collector,
    FeeSystem,
    WasteCategory,
    WasteFlyer,
)
from utils.object_management.models import ReviewAction
from utils.properties.models import Property, Unit

# ---------------------------------------------------------------------------
# Value mappings
# ---------------------------------------------------------------------------

_CONNECTION_TYPE_MAP = {
    "mandatory": "MANDATORY",
    "mandatory with exception": "MANDATORY_WITH_HOME_COMPOSTER_EXCEPTION",
    "mandatory with exception for home composters": "MANDATORY_WITH_HOME_COMPOSTER_EXCEPTION",
    "voluntary": "VOLUNTARY",
    "not specified": "not_specified",
}

_COLLECTION_SYSTEM_ALIAS = {
    "on demand": "On demand kerbside collection",
}

_BIN_CAPACITY_REF_MAP = {
    "per person": "person",
    "person": "person",
    "persons": "person",
    "per household": "household",
    "household": "household",
    "households": "household",
    "per property": "property",
    "property": "property",
    "properties": "property",
    "non": "not_specified",
    "not specified": "not_specified",
    "not_specified": "not_specified",
}

_KNOWN_UNRESOLVED_BW_FREQUENCIES = set()
_FREQUENCY_NAME_TRANSLATIONS = {
    "Fixed-Seasonal; 39 per year (1 per 2 weeks from March - November)": (
        "Seasonal; 19 per year (1 per 2 weeks from March - November, 0 from "
        "December - February)"
    ),
}
_FREQUENCY_TYPE_CANONICAL_NAMES = {
    "fixed": "Fixed",
    "fixed-flexible": "Fixed-Flexible",
    "fixed-seasonal": "Fixed-Seasonal",
    "seasonal": "Seasonal",
}
_FREQUENCY_COUNT_FRAGMENT_RE = re.compile(
    r"\d+\s+per\s+year(?:\s*\([^)]*\))?",
    re.IGNORECASE,
)
_IMPORTED_REFERENCE_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_IMPORTED_REVIEW_COMMENT_PREFIX = "Import review note:"


def _normalize_collector_lookup_key(value: str) -> str:
    text = (value or "").replace("\xa0", " ")
    return " ".join(text.split()).casefold()


def _should_warn_on_frequency_normalization(
    raw_name: str,
    resolved_name: str,
) -> bool:
    canonical_fixed_name = _canonicalize_fixed_frequency_name(raw_name)
    if canonical_fixed_name is not None and canonical_fixed_name == resolved_name:
        return False
    return raw_name != resolved_name


def _normalize_frequency_display_text(value: str) -> str:
    normalized = re.sub(r"\s+", " ", (value or "").strip())
    normalized = normalized.replace("Fixed:", "Fixed;")
    normalized = re.sub(r"\s*;\s*", "; ", normalized)
    normalized = re.sub(r"\s*,\s*", ", ", normalized)
    normalized = re.sub(r"\(\s+", "(", normalized)
    normalized = re.sub(r"\s+\)", ")", normalized)
    normalized = re.sub(r"\bMay\b", "Mai", normalized, flags=re.IGNORECASE)
    type_match = re.match(
        r"^(fixed(?:-seasonal|-flexible)?|seasonal)\b",
        normalized,
        flags=re.IGNORECASE,
    )
    if type_match:
        canonical_type = _FREQUENCY_TYPE_CANONICAL_NAMES.get(
            type_match.group(1).lower(), type_match.group(1)
        )
        normalized = canonical_type + normalized[type_match.end() :]
    return normalized.strip()


def _normalize_frequency_lookup_key(value: str) -> str:
    return _normalize_frequency_display_text(value).casefold()


def _canonicalize_fixed_frequency_name(value: str) -> str | None:
    normalized = _normalize_frequency_display_text(value)
    match = re.fullmatch(
        r"Fixed;\s*(\d+)\s+per\s+year(?:\s*\([^)]*\))?",
        normalized,
    )
    if match is None:
        return None
    return f"Fixed; {int(match.group(1))} per year"


def _split_imported_reference_entry(value: str) -> tuple[list[str], list[str]]:
    text = " ".join(str(value).split())
    if not text:
        return [], []

    urls = [
        match.group(0).strip(" ,;")
        for match in _IMPORTED_REFERENCE_URL_RE.finditer(text)
    ]
    notes_text = _IMPORTED_REFERENCE_URL_RE.sub(" ", text)
    notes_text = re.sub(r"\s*,\s*,+\s*", ", ", notes_text)
    notes_text = re.sub(r"\s{2,}", " ", notes_text).strip(" ,;")
    notes = [notes_text] if notes_text else []
    return urls, notes


def _parse_whole_year_fixed_flexible_frequency(value: str) -> dict | None:
    normalized = _normalize_frequency_display_text(value)
    if not normalized.lower().startswith("fixed-flexible;"):
        return None
    if " from " in normalized.lower():
        return None

    fragments = _FREQUENCY_COUNT_FRAGMENT_RE.findall(normalized)
    if len(fragments) < 2:
        return None
    counts = [int(re.search(r"(\d+)", fragment).group(1)) for fragment in fragments]
    option_counts = counts[1:]
    if len(option_counts) > 3:
        return None
    return {
        "canonical_name": (
            f"Fixed-Flexible; Standard: {fragments[0]}; Optional: "
            f"{', '.join(fragments[1:])}"
        ),
        "signature": (counts[0], tuple(sorted(option_counts))),
        "standard_count": counts[0],
        "option_counts": option_counts,
    }


class CollectionImporter:
    """
    Import waste collection records from validated data dicts.

    Usage::

        importer = CollectionImporter(owner=user, publication_status="private")
        result = importer.run(records)  # list of dicts from serializer.validated_data
        # result = {"created": N, "skipped": N, "predecessor_links": N,
        #           "cpv_created": N, "cpv_skipped": N, "flyers_created": N,
        #           "warnings": [...]}
    """

    def __init__(self, owner, publication_status: str = "private"):
        if owner is None or not getattr(owner, "is_authenticated", False):
            raise ValueError("owner must be an authenticated user")
        self.owner = owner
        self.publication_status = publication_status
        self.dry_run = False
        self._lookups_loaded = False

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, records: list[dict], dry_run: bool = False) -> dict:
        """Import *records* inside a single atomic transaction.

        Args:
            records: List of validated data dicts (CollectionImportRecordSerializer).
            dry_run: If True the transaction is rolled back at the end.

        Returns:
            Statistics dict.
        """
        self.dry_run = dry_run
        self._load_lookups()

        stats = {
            "created": 0,
            "unchanged": 0,
            "skipped": 0,
            "predecessor_links": 0,
            "cpv_created": 0,
            "cpv_unchanged": 0,
            "cpv_skipped": 0,
            "flyers_created": 0,
            "review_comments_created": 0,
            "sources_created": 0,
            "warnings": [],
        }

        with transaction.atomic():
            for i, record in enumerate(records):
                self._import_record(record, i, stats)
            if dry_run:
                transaction.set_rollback(True)

        return stats

    # ------------------------------------------------------------------
    # Lookup tables
    # ------------------------------------------------------------------

    def _load_lookups(self):
        if self._lookups_loaded:
            return

        self._waste_categories: dict[str, WasteCategory] = {
            o.name: o for o in WasteCategory.objects.all()
        }
        self._collection_systems: dict[str, CollectionSystem] = {
            o.name: o for o in CollectionSystem.objects.all()
        }
        self._bin_configurations: dict[str, BinConfiguration] = {
            o.name: o for o in BinConfiguration.objects.all()
        }
        self._fee_systems: dict[str, FeeSystem] = {
            o.name: o for o in FeeSystem.objects.all()
        }
        frequency_objects = list(CollectionFrequency.objects.all())
        self._frequencies: dict[str, CollectionFrequency] = {
            o.name: o for o in frequency_objects
        }
        self._normalized_frequencies: dict[str, CollectionFrequency] = {
            _normalize_frequency_lookup_key(o.name): o for o in frequency_objects
        }
        self._whole_year_fixed_flexible_frequencies: dict[
            tuple[int, tuple[int, ...]], CollectionFrequency
        ] = {}
        for frequency in frequency_objects:
            parsed_flexible = _parse_whole_year_fixed_flexible_frequency(frequency.name)
            if parsed_flexible is not None:
                self._whole_year_fixed_flexible_frequencies.setdefault(
                    parsed_flexible["signature"],
                    frequency,
                )
        self._collectors: dict[str, Collector] = {
            o.name: o for o in Collector.objects.all()
        }
        self._normalized_collectors: dict[str, Collector] = {}
        for collector in self._collectors.values():
            self._normalized_collectors.setdefault(
                _normalize_collector_lookup_key(collector.name),
                collector,
            )
        self._materials: dict[str, Material] = {
            o.name: o for o in Material.objects.all()
        }
        self._properties: dict[int, Property] = {
            o.id: o for o in Property.objects.all()
        }
        self._units: dict[str, Unit] = {o.name: o for o in Unit.objects.all()}

        # NUTS id → CollectionCatchment  (single JOIN, no per-row queries)
        nuts_rows = (
            CollectionCatchment.objects.filter(region__nutsregion__isnull=False)
            .select_related("region__nutsregion")
            .values_list("region__nutsregion__nuts_id", "id")
        )
        catchment_pks = {pk for _, pk in nuts_rows}
        _catchment_objs = {
            c.pk: c for c in CollectionCatchment.objects.filter(pk__in=catchment_pks)
        }
        self._nuts_catchments: dict[str, CollectionCatchment] = {
            nuts_id: _catchment_objs[pk] for nuts_id, pk in nuts_rows if nuts_id
        }

        # LAU id → CollectionCatchment  (single JOIN, no per-row queries)
        lau_rows = (
            CollectionCatchment.objects.filter(region__lauregion__isnull=False)
            .select_related("region__lauregion")
            .values_list("region__lauregion__lau_id", "id")
        )
        catchment_pks = {pk for _, pk in lau_rows}
        _catchment_objs = {
            c.pk: c for c in CollectionCatchment.objects.filter(pk__in=catchment_pks)
        }
        self._lau_catchments: dict[str, CollectionCatchment] = {
            lau_id: _catchment_objs[pk] for lau_id, pk in lau_rows if lau_id
        }

        self._lookups_loaded = True

    # ------------------------------------------------------------------
    # Record processing
    # ------------------------------------------------------------------

    def _import_record(self, record: dict, index: int, stats: dict) -> None:
        label = f"record[{index}]"

        collection_system = self._resolve_collection_system(record, label, stats)
        if collection_system is None:
            stats["skipped"] += 1
            return

        waste_category = self._resolve_waste_category(record, label, stats)
        if waste_category is None:
            stats["skipped"] += 1
            return

        valid_from = record.get("valid_from")
        if valid_from is None:
            stats["warnings"].append(f"{label}: No valid_from date — record skipped.")
            stats["skipped"] += 1
            return

        allowed_materials, forbidden_materials = self._resolve_material_lists(
            record, label, stats
        )
        allowed_material_ids = self._material_ids(allowed_materials)
        forbidden_material_ids = self._material_ids(forbidden_materials)

        catchment = self._resolve_catchment(
            record,
            label,
            stats,
            collector=self._lookup_known_collector(record),
            collection_system=collection_system,
            waste_category=waste_category,
            allowed_material_ids=allowed_material_ids,
            forbidden_material_ids=forbidden_material_ids,
            valid_from=valid_from,
        )
        if catchment is None:
            stats["skipped"] += 1
            return

        collector = self._resolve_collector(record, label, stats)
        fee_system = self._resolve_fee_system(record, label, stats)
        frequency = self._resolve_frequency(record, label, stats)
        connection_type = self._resolve_connection_type(record, label, stats)
        bin_configuration = self._resolve_bin_configuration(record, label, stats)
        established = record.get("established")
        bin_cap_ref = self._resolve_bin_capacity_reference(record)

        valid_until = record.get("valid_until")
        description = record.get("description") or ""
        review_comment = str(record.get("review_comment") or "").strip()
        raw_frequency_name = record.get("frequency") or ""
        min_bin_size = record.get("min_bin_size")
        required_bin_capacity = record.get("required_bin_capacity")

        # Check for existing collection with same identity
        existing = self._find_existing_collection(
            catchment=catchment,
            collection_system=collection_system,
            waste_category=waste_category,
            valid_from=valid_from,
            allowed_material_ids=allowed_material_ids,
            forbidden_material_ids=forbidden_material_ids,
        )

        if existing:
            collection = existing
            update_fields = []
            changes = []
            manual_review_note = self._manual_review_note_for_frequency(
                raw_frequency_name, frequency
            )
            if manual_review_note and manual_review_note not in description:
                description = (
                    f"{description}\n\n{manual_review_note}"
                    if description
                    else manual_review_note
                )
                stats["warnings"].append(
                    f"{label}: Added manual-review note to description for unresolved frequency '{raw_frequency_name}'."
                )

            # Update collector if different
            if collector and collection.collector_id != (
                collector.pk if collector else None
            ):
                changes.append(
                    f"collector: {collection.collector or 'None'} → {collector}"
                )
                collection.collector = collector
                update_fields.append("collector")

            # Update fee_system if different
            if fee_system and collection.fee_system_id != (
                fee_system.pk if fee_system else None
            ):
                changes.append(
                    f"fee_system: {collection.fee_system or 'None'} → {fee_system}"
                )
                collection.fee_system = fee_system
                update_fields.append("fee_system")

            # Update frequency if different
            if frequency and collection.frequency_id != (
                frequency.pk if frequency else None
            ):
                changes.append(
                    f"frequency: {collection.frequency or 'None'} → {frequency}"
                )
                collection.frequency = frequency
                update_fields.append("frequency")

            # Update connection_type if different
            if connection_type and collection.connection_type != connection_type:
                changes.append(
                    f"connection_type: {collection.connection_type or 'None'} → {connection_type}"
                )
                collection.connection_type = connection_type
                update_fields.append("connection_type")

            # Update bin_configuration if different
            if bin_configuration and collection.bin_configuration_id != (
                bin_configuration.pk if bin_configuration else None
            ):
                changes.append(
                    f"bin_configuration: {collection.bin_configuration or 'None'} → {bin_configuration}"
                )
                collection.bin_configuration = bin_configuration
                update_fields.append("bin_configuration")

            # Update established if different
            if established is not None and collection.established != established:
                changes.append(f"established: {collection.established} → {established}")
                collection.established = established
                update_fields.append("established")

            if min_bin_size is not None and collection.min_bin_size != min_bin_size:
                changes.append(
                    f"min_bin_size: {collection.min_bin_size} → {min_bin_size}"
                )
                collection.min_bin_size = min_bin_size
                update_fields.append("min_bin_size")

            # Update required_bin_capacity if different
            if (
                required_bin_capacity is not None
                and collection.required_bin_capacity != required_bin_capacity
            ):
                changes.append(
                    f"required_bin_capacity: {collection.required_bin_capacity} → {required_bin_capacity}"
                )
                collection.required_bin_capacity = required_bin_capacity
                update_fields.append("required_bin_capacity")

            # Update required_bin_capacity_reference if different
            if (
                bin_cap_ref is not None
                and collection.required_bin_capacity_reference != bin_cap_ref
            ):
                changes.append(
                    f"required_bin_capacity_reference: {collection.required_bin_capacity_reference or 'None'} → {bin_cap_ref}"
                )
                collection.required_bin_capacity_reference = bin_cap_ref
                update_fields.append("required_bin_capacity_reference")

            # Update description if different
            if description and collection.description != description:
                changes.append("description updated")
                collection.description = description
                update_fields.append("description")

            # Update valid_until if different
            if valid_until != collection.valid_until:
                changes.append(f"valid_until: {collection.valid_until} → {valid_until}")
                collection.valid_until = valid_until
                update_fields.append("valid_until")

            # Ensure inline waste fields stay in sync with imported payload.
            if collection.waste_category_id != waste_category.id:
                changes.append(
                    f"waste_category: {collection.effective_waste_category or 'None'} → {waste_category}"
                )
                collection.waste_category = waste_category
                update_fields.append("waste_category")

            current_allowed_ids, current_forbidden_ids = (
                self._effective_material_ids_for_collection(collection)
            )
            update_allowed_materials = current_allowed_ids != allowed_material_ids
            update_forbidden_materials = current_forbidden_ids != forbidden_material_ids

            if update_allowed_materials:
                changes.append("allowed_materials updated")
            if update_forbidden_materials:
                changes.append("forbidden_materials updated")

            if not self.dry_run:
                if update_fields:
                    collection.save(update_fields=[*update_fields, "lastmodified_at"])
                if update_allowed_materials:
                    collection.allowed_materials.set(allowed_materials)
                if update_forbidden_materials:
                    collection.forbidden_materials.set(forbidden_materials)

            source_urls, update_sources = self._attach_collection_sources(
                collection, record.get("sources") or [], stats
            )
            update_flyers = self._attach_collection_flyers(
                collection,
                [*source_urls, *(record.get("flyer_urls") or [])],
                stats,
            )
            if update_sources:
                changes.append("sources updated")
            if update_flyers:
                changes.append("flyers updated")

            if (
                update_fields
                or update_allowed_materials
                or update_forbidden_materials
                or update_sources
                or update_flyers
            ):
                stats["updated"] = stats.get("updated", 0) + 1
                stats["changes"] = stats.get("changes", [])
                stats["changes"].append(f"{label}: {', '.join(changes)}")
            else:
                stats["unchanged"] += 1

            if (
                self.publication_status == "review"
                and collection.publication_status
                in (collection.STATUS_PRIVATE, collection.STATUS_DECLINED)
                and not self.dry_run
            ):
                self._submit_for_review(collection)

            review_comment_changed = self._sync_import_review_comment(
                collection, review_comment, stats
            )
            if review_comment_changed:
                changes.append("review comment updated")
        else:
            predecessor = self._find_predecessor(
                catchment,
                waste_category,
                collection_system,
                valid_from,
            )

            collection_name = (
                f"{catchment.name} {waste_category.name} "
                f"{collection_system.name} {valid_from.year}"
            )
            collection = Collection(
                name=collection_name,
                owner=self.owner,
                publication_status="private",
                catchment=catchment,
                collector=collector,
                collection_system=collection_system,
                waste_category=waste_category,
                frequency=frequency,
                fee_system=fee_system,
                valid_from=valid_from,
                valid_until=valid_until,
                connection_type=connection_type,
                bin_configuration=bin_configuration,
                established=established,
                description=description,
            )
            if min_bin_size is not None:
                collection.min_bin_size = min_bin_size
            if required_bin_capacity is not None:
                collection.required_bin_capacity = required_bin_capacity
            if bin_cap_ref:
                collection.required_bin_capacity_reference = bin_cap_ref
            collection.save()
            collection.allowed_materials.set(allowed_materials)
            collection.forbidden_materials.set(forbidden_materials)

            if predecessor:
                collection.predecessors.add(predecessor)
                if not predecessor.valid_until:
                    predecessor.valid_until = valid_from - timedelta(days=1)
                    predecessor.save(update_fields=["valid_until", "lastmodified_at"])
                stats["predecessor_links"] += 1

            stats["created"] += 1

            source_urls, _ = self._attach_collection_sources(
                collection, record.get("sources") or [], stats
            )

            self._attach_collection_flyers(
                collection,
                [*source_urls, *(record.get("flyer_urls") or [])],
                stats,
            )
            if self.publication_status == "review":
                self._submit_for_review(collection)

            self._sync_import_review_comment(collection, review_comment, stats)

        # Property values
        for pv in record.get("property_values") or []:
            self._import_property_value(collection, pv, stats)

    def _attach_collection_flyers(
        self, collection: Collection, urls: list[str], stats: dict
    ) -> bool:
        desired_flyers = []
        desired_urls = set()
        for url in urls:
            normalized_url = " ".join(str(url).split())
            if not normalized_url or normalized_url in desired_urls:
                continue
            if len(normalized_url) > 2083:
                stats["warnings"].append(
                    f"{collection}: Flyer URL too long ({len(normalized_url)} chars), skipped."
                )
                continue
            flyer, created = WasteFlyer.objects.get_or_create_by_url(
                url=normalized_url,
                defaults={
                    "owner": self.owner,
                    "title": self._flyer_title(normalized_url),
                    "publication_status": "private",
                },
            )
            desired_flyers.append(flyer)
            desired_urls.add(normalized_url)
            if created:
                stats["flyers_created"] += 1
                if self.publication_status == "review":
                    self._submit_for_review(flyer)
        current_ids = set(collection.flyers.values_list("id", flat=True))
        desired_ids = {flyer.id for flyer in desired_flyers}
        if current_ids == desired_ids:
            return False
        collection.flyers.set(desired_flyers)
        return True

    def _attach_collection_sources(
        self, collection: Collection, source_titles: list[str], stats: dict
    ) -> tuple[list[str], bool]:
        existing_titles = set(collection.sources.values_list("title", flat=True))
        desired_sources = []
        desired_titles = set()
        reclassified_urls = []
        for raw_title in source_titles:
            urls, notes = _split_imported_reference_entry(raw_title)
            reclassified_urls.extend(urls)
            for title in notes:
                title = title[:500]
                if not title or title in desired_titles:
                    continue
                source, created = Source.objects.get_or_create_custom_by_title(
                    owner=self.owner,
                    title=title,
                    defaults={"publication_status": "private"},
                )
                desired_sources.append(source)
                desired_titles.add(title)
                if created:
                    stats["sources_created"] += 1
                if (
                    title not in existing_titles
                    and self.publication_status == "review"
                    and source.publication_status
                    in (
                        source.STATUS_PRIVATE,
                        source.STATUS_DECLINED,
                    )
                ):
                    self._submit_for_review(source)

        current_ids = set(collection.sources.values_list("id", flat=True))
        desired_ids = {source.id for source in desired_sources}
        if current_ids == desired_ids:
            return reclassified_urls, False
        collection.sources.set(desired_sources)
        return reclassified_urls, True

    def _attach_cpv_sources(
        self, cpv: CollectionPropertyValue, urls: list[str], stats: dict
    ) -> None:
        """Attach WasteFlyer sources to a CollectionPropertyValue.

        Only adds flyers not already linked.  Creates new WasteFlyer objects
        as needed and submits them for review when the importer is in review
        mode.
        """
        existing_urls = set(cpv.sources.values_list("url", flat=True))
        for url in urls:
            if url in existing_urls:
                continue
            if len(url) > 2083:
                stats["warnings"].append(
                    f"CPV source URL too long ({len(url)} chars), skipped."
                )
                continue
            flyer, created = WasteFlyer.objects.get_or_create_by_url(
                url=url,
                defaults={
                    "owner": self.owner,
                    "title": self._flyer_title(url),
                    "publication_status": "private",
                },
            )
            cpv.sources.add(flyer)
            if created:
                stats["flyers_created"] += 1
                if self.publication_status == "review":
                    self._submit_for_review(flyer)

    def _import_property_value(
        self, collection: Collection, pv: dict, stats: dict
    ) -> None:
        prop = self._properties.get(pv["property_id"])
        unit = self._units.get(pv["unit_name"])

        if prop is None:
            stats["cpv_skipped"] += 1
            stats["warnings"].append(
                f"Property id={pv['property_id']} not found — CPV skipped."
            )
            return
        if unit is None:
            stats["cpv_skipped"] += 1
            stats["warnings"].append(
                f"Unit '{pv['unit_name']}' not found — CPV skipped."
            )
            return

        year = pv["year"]
        existing_cpv = CollectionPropertyValue.objects.filter(
            collection=collection, property=prop, unit=unit, year=year
        ).first()
        if existing_cpv is not None:
            flyer_urls = pv.get("flyer_urls") or []
            self._attach_cpv_sources(existing_cpv, flyer_urls, stats)
            derived = CollectionPropertyValue.objects.filter(
                collection=collection, year=year, is_derived=True
            ).first()
            if derived is not None:
                self._attach_cpv_sources(derived, flyer_urls, stats)
            if self.publication_status == "review" and not self.dry_run:
                if derived is not None and derived.publication_status in (
                    derived.STATUS_PRIVATE,
                    derived.STATUS_DECLINED,
                ):
                    self._submit_cpv_for_review(derived)
                if existing_cpv.publication_status in (
                    existing_cpv.STATUS_PRIVATE,
                    existing_cpv.STATUS_DECLINED,
                ):
                    self._submit_cpv_for_review(existing_cpv)
            stats["cpv_unchanged"] += 1
            return

        cpv_name = f"{collection.name} {prop.name} {year}"
        cpv = CollectionPropertyValue.objects.create(
            name=cpv_name,
            owner=self.owner,
            publication_status="private",
            collection=collection,
            property=prop,
            unit=unit,
            year=year,
            average=pv["average"],
            standard_deviation=pv.get("standard_deviation"),
        )
        stats["cpv_created"] += 1
        self._attach_cpv_sources(cpv, pv.get("flyer_urls") or [], stats)

        flyer_urls = pv.get("flyer_urls") or []
        derived = CollectionPropertyValue.objects.filter(
            collection=collection,
            year=year,
            is_derived=True,
        ).first()
        if derived is not None:
            self._attach_cpv_sources(derived, flyer_urls, stats)

        if self.publication_status == "review":
            # Submit the derived counterpart first (created by the post_save signal
            # during .create() above).  We must do this before calling
            # submit_for_review() on the source CPV, because that triggers the
            # signal a second time and would overwrite the derived CPV's
            # publication_status to 'review' without setting submitted_at.
            if derived is not None and derived.submitted_at is None:
                self._submit_cpv_for_review(derived)
            self._submit_cpv_for_review(cpv)

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------

    def _resolve_catchment(
        self,
        record: dict,
        label: str,
        stats: dict,
        *,
        collector: Collector | None = None,
        collection_system: CollectionSystem | None = None,
        waste_category: WasteCategory | None = None,
        allowed_material_ids: set[int] | None = None,
        forbidden_material_ids: set[int] | None = None,
        valid_from=None,
    ) -> CollectionCatchment | None:
        nuts_lau_id = (record.get("nuts_or_lau_id") or "").strip()
        catchment_name = (record.get("catchment_name") or "").strip()

        if nuts_lau_id:
            catchment = self._nuts_catchments.get(nuts_lau_id)
            if catchment is None:
                catchment = self._lau_catchments.get(nuts_lau_id)
            if catchment is not None:
                return catchment
            if self._has_combined_lookup_codes(nuts_lau_id):
                catchment = self._resolve_combined_lookup_catchment(
                    nuts_lau_id,
                    label,
                    stats,
                    collector=collector,
                    collection_system=collection_system,
                    waste_category=waste_category,
                    valid_from=valid_from,
                )
                if catchment is not None:
                    return catchment
            stats["warnings"].append(
                f"{label}: No catchment for NUTS/LAU id '{nuts_lau_id}'."
            )
            return None

        if catchment_name:
            catchment = self._resolve_named_catchment(catchment_name)
            if catchment is not None:
                return catchment

            catchment = self._resolve_import_catchment_fallback(
                collector=collector,
                collection_system=collection_system,
                waste_category=waste_category,
                valid_from=valid_from,
            )
            if catchment is not None:
                return catchment

            stats["warnings"].append(f"{label}: No catchment named '{catchment_name}'.")
            return None

        stats["warnings"].append(
            f"{label}: nuts_or_lau_id and catchment_name both empty."
        )
        return None

    @staticmethod
    def _resolve_named_catchment(catchment_name: str) -> CollectionCatchment | None:
        catchment = CollectionCatchment.objects.filter(name=catchment_name).first()
        if catchment is not None:
            return catchment
        return CollectionCatchment.objects.filter(name__iexact=catchment_name).first()

    @staticmethod
    def _resolve_import_catchment_fallback(
        *,
        collector: Collector | None,
        collection_system: CollectionSystem | None,
        waste_category: WasteCategory | None,
        valid_from,
    ) -> CollectionCatchment | None:
        if collector and collector.catchment_id:
            return collector.catchment

        predecessor = CollectionImporter._find_predecessor_for_catchment_fallback(
            collector=collector,
            waste_category=waste_category,
            collection_system=collection_system,
            valid_from=valid_from,
        )
        if predecessor and predecessor.catchment_id:
            return predecessor.catchment

        return None

    @staticmethod
    def _has_combined_lookup_codes(value: str) -> bool:
        return bool(re.search(r"\s*[,;/]\s*", (value or "").strip()))

    def _resolve_combined_lookup_catchment(
        self,
        nuts_lau_id: str,
        label: str,
        stats: dict,
        *,
        collector: Collector | None,
        collection_system: CollectionSystem | None,
        waste_category: WasteCategory | None,
        valid_from,
    ) -> CollectionCatchment | None:
        return self._resolve_import_catchment_fallback(
            collector=collector,
            collection_system=collection_system,
            waste_category=waste_category,
            valid_from=valid_from,
        )

    def _resolve_collection_system(
        self, record: dict, label: str, stats: dict
    ) -> CollectionSystem | None:
        name = record.get("collection_system") or ""
        normalized = _COLLECTION_SYSTEM_ALIAS.get(name.lower(), name)
        system = self._collection_systems.get(normalized)
        if system is None:
            stats["warnings"].append(
                f"{label}: CollectionSystem '{name}' not found — record skipped."
            )
        return system

    def _resolve_bin_configuration(
        self, record: dict, label: str, stats: dict
    ) -> BinConfiguration | None:
        name = record.get("bin_configuration") or ""
        if not name:
            return None
        method = self._bin_configurations.get(name)
        if method is None:
            stats["warnings"].append(
                f"{label}: BinConfiguration '{name}' not found — field left empty."
            )
        return method

    def _resolve_waste_category(
        self, record: dict, label: str, stats: dict
    ) -> WasteCategory | None:
        name = record.get("waste_category") or ""
        cat = self._waste_categories.get(name)
        if cat is None:
            stats["warnings"].append(
                f"{label}: WasteCategory '{name}' not found — record skipped."
            )
        return cat

    def _lookup_known_collector(self, record: dict) -> Collector | None:
        name = record.get("collector_name") or ""
        website = record.get("collector_website") or ""

        if name:
            collector = self._collectors.get(name)
            if collector is not None:
                return collector

            collector = self._normalized_collectors.get(
                _normalize_collector_lookup_key(name)
            )
            if collector is not None:
                return collector

        if website:
            return next(
                (
                    candidate
                    for candidate in self._collectors.values()
                    if candidate.website == website
                ),
                None,
            )

        return None

    def _resolve_collector(
        self, record: dict, label: str, stats: dict
    ) -> Collector | None:
        name = record.get("collector_name") or ""
        website = record.get("collector_website") or ""

        if not name and not website:
            return None

        collector = self._lookup_known_collector(record)
        if collector is not None:
            return collector

        # Secondary: look up by website URL
        if website:
            # Auto-create a Collector keyed by website domain
            from urllib.parse import urlparse  # noqa: PLC0415

            domain = urlparse(website).netloc or website
            new_name = name or domain
            collector, created = Collector.objects.get_or_create(
                website=website,
                defaults={"name": new_name, "owner": self.owner},
            )
            if created:
                stats.setdefault("collectors_created", 0)
                stats["collectors_created"] += 1
            self._collectors[collector.name] = collector
            self._normalized_collectors[
                _normalize_collector_lookup_key(collector.name)
            ] = collector
            return collector

        stats["warnings"].append(
            f"{label}: Collector '{name}' not found — field left empty."
        )
        return None

    def _resolve_fee_system(
        self, record: dict, label: str, stats: dict
    ) -> FeeSystem | None:
        name = record.get("fee_system") or ""
        if not name:
            return None
        fee = self._fee_systems.get(name)
        if fee is None:
            stats["warnings"].append(
                f"{label}: FeeSystem '{name}' not found — field left empty."
            )
        return fee

    def _resolve_frequency(
        self, record: dict, label: str, stats: dict
    ) -> CollectionFrequency | None:
        name = record.get("frequency") or ""
        if not name:
            return None

        translated_name = _FREQUENCY_NAME_TRANSLATIONS.get(name)
        if translated_name is not None:
            freq = self._frequencies.get(translated_name)
            if freq is not None:
                if _should_warn_on_frequency_normalization(name, freq.name):
                    stats["warnings"].append(
                        f"{label}: CollectionFrequency '{name}' not found — "
                        f"normalized to '{freq.name}'."
                    )
                return freq

        exact_match = self._frequencies.get(name)
        if exact_match is not None:
            return exact_match

        normalized_name = _normalize_frequency_lookup_key(name)
        freq = self._normalized_frequencies.get(normalized_name)
        if freq is not None:
            if _should_warn_on_frequency_normalization(name, freq.name):
                stats["warnings"].append(
                    f"{label}: CollectionFrequency '{name}' not found — "
                    f"normalized to '{freq.name}'."
                )
            return freq

        parsed_flexible = _parse_whole_year_fixed_flexible_frequency(name)
        if parsed_flexible is not None:
            freq = self._whole_year_fixed_flexible_frequencies.get(
                parsed_flexible["signature"]
            )
            if freq is not None:
                if _should_warn_on_frequency_normalization(name, freq.name):
                    stats["warnings"].append(
                        f"{label}: CollectionFrequency '{name}' not found — "
                        f"normalized to '{freq.name}'."
                    )
                return freq

        for canonical_name in filter(
            None,
            (_canonicalize_fixed_frequency_name(name),),
        ):
            freq = self._normalized_frequencies.get(
                _normalize_frequency_lookup_key(canonical_name)
            )
            if freq is not None:
                if _should_warn_on_frequency_normalization(name, freq.name):
                    stats["warnings"].append(
                        f"{label}: CollectionFrequency '{name}' not found — "
                        f"normalized to '{freq.name}'."
                    )
                return freq

        if parsed_flexible is not None:
            canonical_name = parsed_flexible["canonical_name"]
            freq = self._frequencies.get(canonical_name)
            if freq is None:
                freq = self._get_or_create_fixed_flexible_frequency(
                    parsed_flexible["standard_count"],
                    parsed_flexible["option_counts"],
                    canonical_name,
                )
                self._frequencies[canonical_name] = freq
                self._normalized_frequencies[
                    _normalize_frequency_lookup_key(canonical_name)
                ] = freq
                self._whole_year_fixed_flexible_frequencies[
                    parsed_flexible["signature"]
                ] = freq
            if _should_warn_on_frequency_normalization(name, freq.name):
                stats["warnings"].append(
                    f"{label}: CollectionFrequency '{name}' not found — "
                    f"normalized to '{freq.name}'."
                )
            return freq

        canonical_name = _canonicalize_fixed_frequency_name(name)
        if canonical_name is not None:
            count = int(re.search(r"(\d+)", canonical_name).group(1))
            freq = self._frequencies.get(canonical_name)
            if freq is None:
                freq = self._get_or_create_fixed_frequency(count, canonical_name)
                self._frequencies[canonical_name] = freq
                self._normalized_frequencies[
                    _normalize_frequency_lookup_key(canonical_name)
                ] = freq
            if _should_warn_on_frequency_normalization(name, canonical_name):
                stats["warnings"].append(
                    f"{label}: CollectionFrequency '{name}' not found — "
                    f"normalized to '{canonical_name}'."
                )
            return freq

        stats["warnings"].append(
            f"{label}: CollectionFrequency '{name}' not found — field left empty."
        )
        return None

    def _get_or_create_fixed_frequency(
        self, count: int, canonical_name: str
    ) -> CollectionFrequency:
        """Return (or create) a Fixed CollectionFrequency for *count* per year.

        Uses the whole-year season (January–December).  If that season does not
        exist for some reason the frequency is still created but without a
        CollectionCountOptions row.
        """
        freq, created = CollectionFrequency.objects.get_or_create(
            name=canonical_name,
            defaults={
                "type": "Fixed",
                "owner": self.owner,
                "publication_status": "private",
            },
        )
        if created:
            whole_year = CollectionSeason.objects.filter(
                first_timestep__name="January",
                last_timestep__name="December",
            ).first()
            if whole_year:
                cco = CollectionCountOptions.objects.create(
                    frequency=freq,
                    season=whole_year,
                    standard=count,
                    owner=self.owner,
                    publication_status="private",
                )
                if self.publication_status == "review":
                    self._submit_for_review(cco)
            if self.publication_status == "review":
                self._submit_for_review(freq)
        return freq

    def _get_or_create_fixed_flexible_frequency(
        self,
        standard_count: int,
        option_counts: list[int],
        canonical_name: str,
    ) -> CollectionFrequency:
        freq, created = CollectionFrequency.objects.get_or_create(
            name=canonical_name,
            defaults={
                "type": "Fixed-Flexible",
                "owner": self.owner,
                "publication_status": "private",
            },
        )
        if created:
            whole_year = CollectionSeason.objects.filter(
                first_timestep__name="January",
                last_timestep__name="December",
            ).first()
            if whole_year:
                cco_kwargs = {
                    "frequency": freq,
                    "season": whole_year,
                    "standard": standard_count,
                    "owner": self.owner,
                    "publication_status": "private",
                }
                for index, count in enumerate(option_counts[:3], start=1):
                    cco_kwargs[f"option_{index}"] = count
                cco = CollectionCountOptions.objects.create(**cco_kwargs)
                if self.publication_status == "review":
                    self._submit_for_review(cco)
            if self.publication_status == "review":
                self._submit_for_review(freq)
        return freq

    def _resolve_connection_type(
        self, record: dict, label: str, stats: dict
    ) -> str | None:
        value = record.get("connection_type") or ""
        if not value:
            return None
        mapped = _CONNECTION_TYPE_MAP.get(value.lower())
        if mapped is None:
            stats["warnings"].append(
                f"{label}: Unknown connection_type '{value}' — field left empty."
            )
        return mapped

    @staticmethod
    def _resolve_bin_capacity_reference(record: dict) -> str | None:
        raw = str(record.get("required_bin_capacity_reference") or "").lower().strip()
        if not raw:
            return None
        mapped = _BIN_CAPACITY_REF_MAP.get(raw)
        if mapped:
            return mapped
        if "inh" in raw:
            return "person"
        if "person" in raw:
            return "person"
        if "household" in raw:
            return "household"
        if "propert" in raw:
            return "property"
        return None

    def _resolve_material_lists(
        self,
        record: dict,
        label: str,
        stats: dict,
    ) -> tuple[list[Material], list[Material]]:
        def _normalise(value) -> list[str]:
            if not value:
                return []
            if isinstance(value, str):
                parts = [p.strip() for p in re.split(r"[,;\n]+", value) if p.strip()]
                return [
                    p for p in parts if p.lower() not in {"none", "nan", "null", "-"}
                ]
            if isinstance(value, list):
                return [str(v).strip() for v in value if str(v).strip()]
            return [str(value).strip()]

        allowed_names = _normalise(record.get("allowed_materials"))
        forbidden_names = _normalise(record.get("forbidden_materials"))

        def _resolve(names: list[str], side: str) -> list[Material]:
            resolved = []
            seen_ids: set[int] = set()
            for name in names:
                material = self._materials.get(name)
                if material is None:
                    stats["warnings"].append(
                        f"{label}: {side} material '{name}' not found — ignored."
                    )
                    continue
                if material.id not in seen_ids:
                    resolved.append(material)
                    seen_ids.add(material.id)
            return resolved

        return _resolve(allowed_names, "Allowed"), _resolve(
            forbidden_names, "Forbidden"
        )

    @staticmethod
    def _material_ids(materials: list[Material]) -> set[int]:
        return {material.id for material in materials if material and material.id}

    @staticmethod
    def _effective_material_ids_for_collection(
        collection: Collection,
    ) -> tuple[set[int], set[int]]:
        allowed_ids = set(collection.allowed_materials.values_list("id", flat=True))
        forbidden_ids = set(collection.forbidden_materials.values_list("id", flat=True))
        return allowed_ids, forbidden_ids

    def _find_existing_collection(
        self,
        *,
        catchment: CollectionCatchment,
        collection_system: CollectionSystem,
        waste_category: WasteCategory,
        valid_from,
        allowed_material_ids: set[int],
        forbidden_material_ids: set[int],
    ) -> Collection | None:
        return (
            Collection.objects.filter(
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

    @staticmethod
    def _flyer_title(url: str) -> str:
        """Return a short title derived from the URL hostname (max 255 chars)."""
        from urllib.parse import urlparse

        try:
            hostname = urlparse(url).hostname or url
        except Exception:
            hostname = url
        return hostname[:255]

    def _submit_for_review(self, obj) -> None:
        """Submit any UserCreatedObject for review and create the ReviewAction."""
        obj.submit_for_review()
        ReviewAction.objects.create(
            content_type=ContentType.objects.get_for_model(obj.__class__),
            object_id=obj.pk,
            user=self.owner,
            action=ReviewAction.ACTION_SUBMITTED,
            comment="",
        )

    def _submit_cpv_for_review(self, cpv: CollectionPropertyValue) -> None:
        """Submit a CPV for review and create the corresponding ReviewAction."""
        self._submit_for_review(cpv)

    def _sync_import_review_comment(
        self, obj, review_comment: str, stats: dict
    ) -> bool:
        normalized = self._normalize_import_review_comment(review_comment)
        existing_comments = list(
            ReviewAction.for_object(obj)
            .filter(
                action=ReviewAction.ACTION_COMMENT,
                user=self.owner,
                comment__startswith=_IMPORTED_REVIEW_COMMENT_PREFIX,
            )
            .order_by("id")
        )
        if len(existing_comments) == 1 and existing_comments[0].comment == normalized:
            return False
        if self.dry_run:
            if normalized:
                stats["review_comments_created"] += 1
            return bool(normalized) or bool(existing_comments)
        if existing_comments:
            ReviewAction.objects.filter(
                id__in=[comment.id for comment in existing_comments]
            ).delete()
        if not normalized:
            return bool(existing_comments)
        ReviewAction.objects.create(
            content_type=ContentType.objects.get_for_model(obj.__class__),
            object_id=obj.pk,
            action=ReviewAction.ACTION_COMMENT,
            comment=normalized,
            user=self.owner,
        )
        stats["review_comments_created"] += 1
        return True

    @staticmethod
    def _normalize_import_review_comment(review_comment: str) -> str:
        review_comment = (review_comment or "").strip()
        if not review_comment:
            return ""
        if review_comment.startswith(_IMPORTED_REVIEW_COMMENT_PREFIX):
            return review_comment
        return f"{_IMPORTED_REVIEW_COMMENT_PREFIX} {review_comment}"

    @staticmethod
    def _manual_review_note_for_frequency(
        raw_frequency_name: str,
        resolved_frequency: CollectionFrequency | None,
    ) -> str | None:
        if resolved_frequency is not None or not raw_frequency_name:
            return None
        if _normalize_frequency_lookup_key(raw_frequency_name) not in {
            _normalize_frequency_lookup_key(value)
            for value in _KNOWN_UNRESOLVED_BW_FREQUENCIES
        }:
            return None
        return (
            "SYNC NOTE (BW 2024 SW1 one-off import): "
            f"Frequency '{raw_frequency_name}' requires manual review."
        )

    @staticmethod
    def _find_predecessor(
        catchment: CollectionCatchment,
        waste_category: WasteCategory,
        collection_system: CollectionSystem,
        valid_from,
    ) -> Collection | None:
        qs = Collection.objects.filter(
            catchment=catchment,
            collection_system=collection_system,
        ).filter(waste_category=waste_category)
        if valid_from:
            qs = qs.filter(valid_from__lt=valid_from)
        return qs.order_by("-valid_from").first()

    @staticmethod
    def _find_predecessor_for_catchment_fallback(
        *,
        collector: Collector | None,
        waste_category: WasteCategory | None,
        collection_system: CollectionSystem | None,
        valid_from,
    ) -> Collection | None:
        if collector is None or collection_system is None or waste_category is None:
            return None
        qs = Collection.objects.filter(
            collector=collector,
            collection_system=collection_system,
            waste_category=waste_category,
        )
        if valid_from:
            qs = qs.filter(valid_from__lt=valid_from)
        return qs.order_by("-valid_from").first()
