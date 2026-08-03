"""Provider-neutral ingestion for the NUTS vintage import contract.

Takes a validated payload and upserts one vintage's :class:`NutsRegion` rows,
keyed by ``(nuts_id, version)`` so the same code in another vintage is never
touched. Ingestion is all-or-nothing: if any region fails, nothing is persisted
and the failures come back in the report. ``dry_run`` reports without writing.
"""

from dataclasses import dataclass, field

from django.db import transaction

from maps.models import GeoPolygon, NutsRegion, NutsVintage

FIELDS = (
    "levl_code",
    "cntr_code",
    "name_latn",
    "nuts_name",
    "mount_type",
    "urbn_type",
    "coast_type",
)


@dataclass
class NutsImportReport:
    schema_version: str
    dry_run: bool
    committed: bool = False
    vintage_year: int | None = None
    vintage_created: bool = False
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def parent_code(nuts_id):
    """The code of the region one level up, e.g. ``DE21`` -> ``DE2``.

    NUTS codes are positional: every level appends one character to its parent.
    """
    return nuts_id[:-1] if len(nuts_id) > 2 else None


def _set_current(vintage):
    NutsVintage.objects.exclude(pk=vintage.pk).filter(is_current=True).update(
        is_current=False
    )
    if not vintage.is_current:
        vintage.is_current = True
        vintage.save(update_fields=["is_current"])


def _upsert_geometry(region, geometry):
    """Store the borders, returning whether they changed."""
    if geometry is None:
        return False
    if region.borders is None:
        region.borders = GeoPolygon.objects.create(geom=geometry)
        return True
    if region.borders.geom is not None and region.borders.geom.equals_exact(geometry):
        return False
    region.borders.geom = geometry
    region.borders.save(update_fields=["geom"])
    return True


def _resolve_parent(data, vintage, report):
    """The region's parent in its own vintage, or None at level 0."""
    code = parent_code(data["nuts_id"]) if data["levl_code"] else None
    if code is None:
        return None
    parent = NutsRegion.objects.filter(nuts_id=code, version=vintage).first()
    if parent is None:
        report.errors.append(
            f"{data['nuts_id']}: parent {code} is not in NUTS {vintage.year}; "
            "send lower levels first"
        )
    return parent


def _upsert_region(data, vintage, user, report):
    parent = _resolve_parent(data, vintage, report)
    if parent is None and data["levl_code"]:
        return

    region = NutsRegion.objects.filter(nuts_id=data["nuts_id"], version=vintage).first()
    if region is None:
        region = NutsRegion(
            nuts_id=data["nuts_id"],
            version=vintage,
            owner=user,
            name=data["name_latn"] or data["nuts_id"],
            country=data["cntr_code"],
            parent=parent,
            **{name: data[name] for name in FIELDS},
        )
        region.borders = (
            GeoPolygon.objects.create(geom=data["geometry"])
            if data["geometry"]
            else None
        )
        region.save()
        report.created += 1
        return

    changed = [name for name in FIELDS if getattr(region, name) != data[name]]
    if region.parent_id != (parent.pk if parent else None):
        region.parent = parent
        changed.append("parent")
    if data["name_latn"] and region.name != data["name_latn"]:
        region.name = data["name_latn"]
        changed.append("name")
    geometry_changed = _upsert_geometry(region, data["geometry"])
    if not changed and not geometry_changed:
        report.unchanged += 1
        return
    for name in changed:
        if name in FIELDS:
            setattr(region, name, data[name])
    region.save()
    report.updated += 1


def import_nuts_payload(payload, user=None, dry_run=False):
    """Upsert one NUTS vintage from a validated import payload."""
    dry_run = dry_run or payload.get("dry_run", False)
    vintage_data = payload["vintage"]
    report = NutsImportReport(
        schema_version=payload["schema_version"],
        dry_run=dry_run,
        vintage_year=vintage_data["year"],
    )

    try:
        with transaction.atomic():
            vintage, created = NutsVintage.objects.get_or_create(
                year=vintage_data["year"],
                defaults={"source_release": vintage_data["source_release"]},
            )
            report.vintage_created = created
            if not created and vintage_data["source_release"] not in (
                "",
                vintage.source_release,
            ):
                vintage.source_release = vintage_data["source_release"]
                vintage.save(update_fields=["source_release"])

            for data in payload["regions"]:
                _upsert_region(data, vintage, user, report)

            if report.errors:
                raise _Rollback
            if vintage_data["is_current"]:
                _set_current(vintage)
            if dry_run:
                raise _Rollback
            report.committed = True
    except _Rollback:
        pass

    return report


class _Rollback(Exception):
    """Raised to undo a dry run or a failed import inside its transaction."""
