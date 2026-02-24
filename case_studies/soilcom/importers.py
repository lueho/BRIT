"""Collection import logic shared by the management command and the API endpoint."""

from __future__ import annotations

import re
from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from case_studies.soilcom.models import (
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
    WasteStream,
)
from materials.models import Material
from utils.object_management.models import ReviewAction
from utils.properties.models import Property, Unit

# Regex: capture the first integer followed by "per year" anywhere in the string.
_PER_YEAR_RE = re.compile(r"\b(\d+)\s+per\s+year\b", re.IGNORECASE)

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
        self.owner = owner
        self.publication_status = publication_status
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
        self._load_lookups()

        stats = {
            "created": 0,
            "skipped": 0,
            "predecessor_links": 0,
            "cpv_created": 0,
            "cpv_skipped": 0,
            "flyers_created": 0,
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
        self._fee_systems: dict[str, FeeSystem] = {
            o.name: o for o in FeeSystem.objects.all()
        }
        self._frequencies: dict[str, CollectionFrequency] = {
            o.name: o for o in CollectionFrequency.objects.all()
        }
        self._collectors: dict[str, Collector] = {
            o.name: o for o in Collector.objects.all()
        }
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

        catchment = self._resolve_catchment(record, label, stats)
        if catchment is None:
            stats["skipped"] += 1
            return

        collection_system = self._resolve_collection_system(record, label, stats)
        if collection_system is None:
            stats["skipped"] += 1
            return

        waste_category = self._resolve_waste_category(record, label, stats)
        if waste_category is None:
            stats["skipped"] += 1
            return

        collector = self._resolve_collector(record, label, stats)
        fee_system = self._resolve_fee_system(record, label, stats)
        frequency = self._resolve_frequency(record, label, stats)
        connection_type = self._resolve_connection_type(record, label, stats)
        bin_cap_ref = self._resolve_bin_capacity_reference(record)
        allowed_materials, forbidden_materials = self._resolve_material_lists(
            record, label, stats
        )

        waste_stream = self._get_or_create_waste_stream(
            waste_category,
            allowed_materials,
            forbidden_materials,
            label,
            stats,
        )
        if waste_stream is None:
            stats["skipped"] += 1
            return

        valid_from = record.get("valid_from")
        if valid_from is None:
            stats["warnings"].append(f"{label}: No valid_from date — record skipped.")
            stats["skipped"] += 1
            return
        valid_until = record.get("valid_until")
        description = record.get("description") or ""
        min_bin_size = record.get("min_bin_size")
        required_bin_capacity = record.get("required_bin_capacity")

        # Check for existing collection with same identity
        existing = Collection.objects.filter(
            catchment=catchment,
            collection_system=collection_system,
            waste_stream=waste_stream,
            valid_from=valid_from,
        ).first()

        # Legacy backfill path for collections imported before material lists
        # were mapped into WasteStreams.
        if existing is None and (allowed_materials or forbidden_materials):
            legacy_candidates = list(
                Collection.objects.filter(
                    catchment=catchment,
                    collection_system=collection_system,
                    waste_stream__category=waste_category,
                    valid_from=valid_from,
                    owner=self.owner,
                    publication_status=self.publication_status,
                )[:2]
            )
            if len(legacy_candidates) == 1:
                legacy = legacy_candidates[0]
                if (
                    legacy.waste_stream
                    and not legacy.waste_stream.allowed_materials.exists()
                    and not legacy.waste_stream.forbidden_materials.exists()
                ):
                    legacy.waste_stream = waste_stream
                    legacy.save(update_fields=["waste_stream", "lastmodified_at"])
                    existing = legacy

        if existing:
            stats["skipped"] += 1
            collection = existing
            update_fields = []
            if collection.collector_id is None and collector is not None:
                collection.collector = collector
                update_fields.append("collector")
            if collection.fee_system_id is None and fee_system is not None:
                collection.fee_system = fee_system
                update_fields.append("fee_system")
            if collection.frequency_id is None and frequency is not None:
                collection.frequency = frequency
                update_fields.append("frequency")
            if collection.connection_type is None and connection_type is not None:
                collection.connection_type = connection_type
                update_fields.append("connection_type")
            if (
                collection.required_bin_capacity is None
                and required_bin_capacity is not None
            ):
                collection.required_bin_capacity = required_bin_capacity
                update_fields.append("required_bin_capacity")
            if (
                collection.required_bin_capacity_reference in (None, "")
                and bin_cap_ref is not None
            ):
                collection.required_bin_capacity_reference = bin_cap_ref
                update_fields.append("required_bin_capacity_reference")
            if update_fields:
                collection.save(update_fields=[*update_fields, "lastmodified_at"])
        else:
            predecessor = self._find_predecessor(
                catchment, waste_stream, collection_system, valid_from
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
                waste_stream=waste_stream,
                frequency=frequency,
                fee_system=fee_system,
                valid_from=valid_from,
                valid_until=valid_until,
                connection_type=connection_type,
                description=description,
            )
            if min_bin_size is not None:
                collection.min_bin_size = min_bin_size
            if required_bin_capacity is not None:
                collection.required_bin_capacity = required_bin_capacity
            if bin_cap_ref:
                collection.required_bin_capacity_reference = bin_cap_ref
            collection.save()

            if self.publication_status == "review":
                self._submit_for_review(collection)

            if predecessor:
                collection.predecessors.add(predecessor)
                if not predecessor.valid_until:
                    predecessor.valid_until = valid_from - timedelta(days=1)
                    predecessor.save(update_fields=["valid_until", "lastmodified_at"])
                stats["predecessor_links"] += 1

            stats["created"] += 1

        # Flyers — skip URLs that exceed the DB column limit (2083 chars)
        for url in record.get("flyer_urls") or []:
            if len(url) > 2083:
                stats["warnings"].append(
                    f"{label}: Flyer URL too long ({len(url)} chars), skipped."
                )
                continue
            flyer, created = WasteFlyer.objects.get_or_create(
                url=url,
                defaults={
                    "owner": self.owner,
                    "title": self._flyer_title(url),
                    "publication_status": "private",
                },
            )
            collection.flyers.add(flyer)
            if created:
                stats["flyers_created"] += 1
                if self.publication_status == "review":
                    self._submit_for_review(flyer)

        # Property values
        for pv in record.get("property_values") or []:
            self._import_property_value(collection, pv, stats)

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
        if CollectionPropertyValue.objects.filter(
            collection=collection, property=prop, unit=unit, year=year
        ).exists():
            stats["cpv_skipped"] += 1
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

        if self.publication_status == "review":
            # Submit the derived counterpart first (created by the post_save signal
            # during .create() above).  We must do this before calling
            # submit_for_review() on the source CPV, because that triggers the
            # signal a second time and would overwrite the derived CPV's
            # publication_status to 'review' without setting submitted_at.
            derived = CollectionPropertyValue.objects.filter(
                collection=collection,
                year=year,
                is_derived=True,
                submitted_at__isnull=True,
            ).first()
            if derived is not None:
                self._submit_cpv_for_review(derived)
            self._submit_cpv_for_review(cpv)

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------

    def _resolve_catchment(
        self, record: dict, label: str, stats: dict
    ) -> CollectionCatchment | None:
        nuts_lau_id = record.get("nuts_or_lau_id") or ""
        catchment_name = record.get("catchment_name") or ""

        if nuts_lau_id:
            catchment = self._nuts_catchments.get(nuts_lau_id)
            if catchment is None:
                catchment = self._lau_catchments.get(nuts_lau_id)
            if catchment is None:
                stats["warnings"].append(
                    f"{label}: No catchment for NUTS/LAU id '{nuts_lau_id}'."
                )
            return catchment

        if catchment_name:
            catchment = CollectionCatchment.objects.filter(name=catchment_name).first()
            if catchment is None:
                stats["warnings"].append(
                    f"{label}: No catchment named '{catchment_name}'."
                )
            return catchment

        stats["warnings"].append(
            f"{label}: nuts_or_lau_id and catchment_name both empty."
        )
        return None

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

    def _resolve_collector(
        self, record: dict, label: str, stats: dict
    ) -> Collector | None:
        name = record.get("collector_name") or ""
        if not name:
            return None
        collector = self._collectors.get(name)
        if collector is None:
            stats["warnings"].append(
                f"{label}: Collector '{name}' not found — field left empty."
            )
        return collector

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

        # 1. Exact name match against the loaded cache.
        freq = self._frequencies.get(name)
        if freq is not None:
            return freq

        # 2. Fallback: extract the first "N per year" from the raw string and
        #    look up / create a canonical "Fixed; N per year" frequency.
        match = _PER_YEAR_RE.search(name)
        if match:
            count = int(match.group(1))
            canonical_name = f"Fixed; {count} per year"
            freq = self._frequencies.get(canonical_name)
            if freq is None:
                freq = self._get_or_create_fixed_frequency(count, canonical_name)
                # Cache so subsequent records reuse the same object.
                self._frequencies[canonical_name] = freq
            stats["warnings"].append(
                f"{label}: CollectionFrequency '{name}' not found — "
                f"mapped to '{canonical_name}' ({count} per year)."
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
    def _flyer_title(url: str) -> str:
        """Return a short title derived from the URL hostname (max 255 chars)."""
        from urllib.parse import urlparse

        try:
            hostname = urlparse(url).hostname or url
        except Exception:
            hostname = url
        return hostname[:255]

    def _get_or_create_waste_stream(
        self,
        waste_category: WasteCategory,
        allowed_materials: list[Material],
        forbidden_materials: list[Material],
        label: str,
        stats: dict,
    ) -> WasteStream | None:
        """Return an exact material-aware waste stream for the imported record."""
        try:
            ws, created = WasteStream.objects.get_or_create(
                category=waste_category,
                allowed_materials=allowed_materials,
                forbidden_materials=forbidden_materials,
                defaults={
                    "name": f"{waste_category.name} {len(allowed_materials)} {len(forbidden_materials)}",
                    "owner": self.owner,
                    "publication_status": "private",
                },
            )
        except WasteStream.MultipleObjectsReturned:
            stats["warnings"].append(
                f"{label}: Multiple exact WasteStreams found for '{waste_category.name}' with empty materials — record skipped."
            )
            return None
        if created and self.publication_status == "review":
            self._submit_for_review(ws)
        return ws

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

    @staticmethod
    def _find_predecessor(
        catchment: CollectionCatchment,
        waste_stream: WasteStream,
        collection_system: CollectionSystem,
        valid_from,
    ) -> Collection | None:
        qs = Collection.objects.filter(
            catchment=catchment,
            collection_system=collection_system,
            waste_stream=waste_stream,
        )
        if valid_from:
            qs = qs.filter(valid_from__lt=valid_from)
        return qs.order_by("-valid_from").first()
