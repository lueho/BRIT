"""Provider-neutral ingestion for the LAU vintage import contract.

Takes a validated payload and upserts one LAU year's :class:`LauRegion` rows,
keyed by ``(cntr_code, lau_id, year)`` so the same code in another year is
never touched. A payload is one batch of a year, never its complete content,
so rows absent from it are left alone. Ingestion is all-or-nothing: if any
row fails, nothing is persisted and the failures come back in the report.
``dry_run`` reports without writing.
"""

from dataclasses import dataclass, field

from django.db import transaction

from maps.import_common import _Rollback, _upsert_geometry
from maps.models import (
    Catchment,
    LauRegion,
    NutsRegion,
    NutsVintage,
    Region,
)
from maps.signals import deferred_geojson_invalidation

FIELDS = (
    "lau_name",
    "name_en",
)


@dataclass
class LauImportReport:
    schema_version: str
    dry_run: bool
    committed: bool = False
    lau_year: int | None = None
    nuts_year: int | None = None
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    geometry_changed: int = 0
    without_parent: int = 0
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def _referenced_geometry_changes(changed_ids, lau_ids):
    """LAU ids whose new geometry feeds catchments or composite regions."""
    if not changed_ids:
        return []
    referenced = set(
        Catchment.objects.filter(region_id__in=changed_ids).values_list(
            "region_id", flat=True
        )
    ) | set(
        Region.composed_of.through.objects.filter(
            to_region_id__in=changed_ids
        ).values_list("to_region_id", flat=True)
    )
    return [lau_ids[pk] for pk in changed_ids if pk in referenced]


def import_lau_payload(payload, user=None, dry_run=False):
    """Upsert one LAU year from a validated import payload."""
    dry_run = dry_run or payload.get("dry_run", False)
    vintage_data = payload["vintage"]
    report = LauImportReport(
        schema_version=payload["schema_version"],
        dry_run=dry_run,
        lau_year=vintage_data["year"],
        nuts_year=vintage_data["nuts_year"],
    )
    lau_year = vintage_data["year"]

    try:
        with transaction.atomic(), deferred_geojson_invalidation():
            nuts_vintage = NutsVintage.objects.filter(
                year=vintage_data["nuts_year"]
            ).first()
            if nuts_vintage is None:
                report.errors.append(
                    f"NUTS vintage {vintage_data['nuts_year']} does not exist; "
                    "load it before importing LAU rows against it"
                )
                raise _Rollback

            rows = payload["regions"]

            # A duplicate key inside one payload makes the producer's intent
            # ambiguous; fail the batch rather than pick a winner.
            seen = {}
            for index, row in enumerate(rows):
                key = (row["cntr_code"], row["lau_id"])
                if key in seen:
                    report.errors.append(
                        f"duplicate LAU key {row['cntr_code']}/{row['lau_id']} "
                        f"in payload (rows {seen[key] + 1} and {index + 1})"
                    )
                else:
                    seen[key] = index
            if report.errors:
                raise _Rollback

            parent_codes = {
                row["nuts_parent_id"] for row in rows if row["nuts_parent_id"]
            }
            parents = {
                p.nuts_id: p
                for p in NutsRegion.objects.filter(
                    nuts_id__in=parent_codes, version=nuts_vintage
                )
            }

            existing = {
                (e.cntr_code, e.lau_id): e
                for e in LauRegion.objects.filter(
                    year=lau_year,
                    cntr_code__in={row["cntr_code"] for row in rows},
                    lau_id__in={row["lau_id"] for row in rows},
                ).select_related("nuts_parent__version")
            }

            geometry_changed_ids = []
            reparented_ids = {}
            lau_ids = {}
            for row in rows:
                _upsert_lau(
                    row,
                    lau_year,
                    nuts_vintage,
                    parents,
                    existing,
                    user,
                    report,
                    geometry_changed_ids,
                    reparented_ids,
                    lau_ids,
                )

            if report.without_parent:
                report.warnings.append(
                    f"{report.without_parent} row(s) stored without a "
                    "nuts_parent (nuts_parent_id was null)"
                )

            referenced = _referenced_geometry_changes(geometry_changed_ids, lau_ids)
            if referenced:
                report.warnings.append(
                    "Geometry changed on LAU regions referenced by catchments "
                    "or composite regions: " + ", ".join(referenced[:50])
                )

            if reparented_ids:
                with_catchments = set(
                    Catchment.objects.filter(region_id__in=reparented_ids).values_list(
                        "region_id", flat=True
                    )
                )
                affected = [
                    reparented_ids[pk] for pk in reparented_ids if pk in with_catchments
                ]
                if affected:
                    report.warnings.append(
                        "nuts_parent changed for LAU regions with catchments; "
                        "catchment tree parents were not updated: "
                        + ", ".join(affected[:50])
                    )

            if report.errors:
                raise _Rollback
            if dry_run:
                raise _Rollback
            report.committed = True
    except _Rollback:
        pass

    return report


def _upsert_lau(
    row,
    lau_year,
    nuts_vintage,
    parents,
    existing,
    user,
    report,
    geometry_changed_ids,
    reparented_ids,
    lau_ids,
):
    key = (row["cntr_code"], row["lau_id"])
    label = f"{row['cntr_code']}/{row['lau_id']}"

    parent = None
    parent_id = row.get("nuts_parent_id")
    if parent_id is None:
        report.without_parent += 1
    else:
        candidate = parents.get(parent_id)
        if candidate is None:
            report.errors.append(
                f"{label}: nuts_parent_id {parent_id} is not in NUTS "
                f"{nuts_vintage.year}; never substitute another vintage's "
                "region"
            )
            return
        if candidate.levl_code != 3:
            report.errors.append(
                f"{label}: parent {parent_id} is NUTS level "
                f"{candidate.levl_code}, not level 3"
            )
            return
        if candidate.cntr_code != row["cntr_code"]:
            report.errors.append(
                f"{label}: parent {parent_id} belongs to "
                f"{candidate.cntr_code}, not {row['cntr_code']}"
            )
            return
        parent = candidate

    row_existing = existing.get(key)
    if row_existing is not None and row_existing.nuts_parent_id is not None:
        current_parent = row_existing.nuts_parent
        current_year = current_parent.version.year
        if current_year != nuts_vintage.year:
            report.errors.append(
                f"{label}: the existing row's nuts_parent "
                f"{current_parent.nuts_id} is in NUTS {current_year}, not "
                f"the declared NUTS {nuts_vintage.year}; cross-vintage "
                "reparenting is not allowed"
            )
            return

    if row_existing is None:
        if not row.get("geometry"):
            # A boundaryless row still becomes the newest vintage in the merge
            # picker, where a missing border crashes create_region_borders.
            report.errors.append(f"{label}: a new LAU region needs a geometry")
            return
        region = LauRegion(
            lau_id=row["lau_id"],
            cntr_code=row["cntr_code"],
            lau_name=row.get("lau_name"),
            year=lau_year,
            nuts_parent=parent,
            name=row.get("lau_name") or row["lau_id"],
            country=row["cntr_code"],
            owner=user,
            # Vintages are authoritative reference geodata, not a user's
            # draft: a private row would be invisible to every public
            # consumer.
            publication_status=LauRegion.STATUS_PUBLISHED,
            **{name: row[name] for name in ("name_en",) if name in row},
        )
        _upsert_geometry(region, row.get("geometry"))
        region.save()
        report.created += 1
        return

    # Only fields the provider actually sent are touched; an omitted one keeps
    # what BRIT holds rather than being blanked by a serializer default.
    changed = [
        name
        for name in FIELDS
        if name in row and getattr(row_existing, name) != row[name]
    ]
    for name in changed:
        setattr(row_existing, name, row[name])
    if "lau_name" in row:
        name = row["lau_name"] or row["lau_id"]
        if row_existing.name != name:
            row_existing.name = name
            changed.append("name")
    if row_existing.nuts_parent_id != (parent.pk if parent else None):
        row_existing.nuts_parent = parent
        changed.append("nuts_parent")
        reparented_ids[row_existing.pk] = row["lau_id"]
    if row_existing.publication_status != LauRegion.STATUS_PUBLISHED:
        row_existing.publication_status = LauRegion.STATUS_PUBLISHED
        changed.append("publication_status")
    geometry_changed = _upsert_geometry(row_existing, row.get("geometry"))
    if not changed and not geometry_changed:
        report.unchanged += 1
        return
    row_existing.save()
    report.updated += 1
    if geometry_changed:
        report.geometry_changed += 1
        geometry_changed_ids.append(row_existing.pk)
        lau_ids[row_existing.pk] = row["lau_id"]
