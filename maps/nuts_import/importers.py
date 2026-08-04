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


def _resolve_parent(data, vintage, report, dry_run):
    """The region's parent in its own vintage, or None at level 0.

    A provider may state ``parent_nuts_id`` where the code does not imply the
    parent, as in NUTS 2016, whose ``UKN0`` holds ``UKN10``-``UKN16``.

    A dry run rolls back, so regions sent in an earlier request of the same load
    are invisible to it and a missing parent is only a warning there.
    """
    if data["levl_code"] and data.get("parent_nuts_id"):
        code = data["parent_nuts_id"]
    else:
        code = parent_code(data["nuts_id"]) if data["levl_code"] else None
    if code is None:
        return None
    parent = NutsRegion.objects.filter(nuts_id=code, version=vintage).first()
    if parent is None:
        message = (
            f"{data['nuts_id']}: parent {code} is not in NUTS {vintage.year}; "
            "send lower levels first"
        )
        (report.warnings if dry_run else report.errors).append(message)
    return parent


def _upsert_region(data, vintage, user, report, dry_run=False):
    if (
        data["levl_code"]
        and not data.get("parent_nuts_id")
        and parent_code(data["nuts_id"]) is None
    ):
        report.errors.append(
            f"{data['nuts_id']}: a level {data['levl_code']} code cannot be "
            f"{len(data['nuts_id'])} characters long"
        )
        return

    parent = _resolve_parent(data, vintage, report, dry_run)
    if parent is None and data["levl_code"] and not dry_run:
        return

    region = NutsRegion.objects.filter(nuts_id=data["nuts_id"], version=vintage).first()
    if region is None:
        region = NutsRegion(
            nuts_id=data["nuts_id"],
            version=vintage,
            owner=user,
            # Vintages are authoritative reference geodata, not a user's draft:
            # a private row would be invisible to every public consumer.
            publication_status=NutsRegion.STATUS_PUBLISHED,
            name=data.get("name_latn") or data["nuts_id"],
            country=data["cntr_code"],
            parent=parent,
            **{name: data.get(name) for name in FIELDS},
        )
        region.borders = (
            GeoPolygon.objects.create(geom=data["geometry"])
            if data.get("geometry")
            else None
        )
        region.save()
        report.created += 1
        return

    # Only fields the provider actually sent are touched; an omitted one keeps
    # what BRIT holds rather than being blanked by a serializer default.
    changed = [
        name for name in FIELDS if name in data and getattr(region, name) != data[name]
    ]
    for name in changed:
        setattr(region, name, data[name])
    if region.parent_id != (parent.pk if parent else None):
        region.parent = parent
        changed.append("parent")
    if data.get("name_latn") and region.name != data["name_latn"]:
        region.name = data["name_latn"]
        changed.append("name")
    if region.publication_status != NutsRegion.STATUS_PUBLISHED:
        region.publication_status = NutsRegion.STATUS_PUBLISHED
        changed.append("publication_status")
    geometry_changed = _upsert_geometry(region, data.get("geometry"))
    if not changed and not geometry_changed:
        report.unchanged += 1
        return
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

            # Parents have to exist before their children, whatever order the
            # provider listed the levels in.
            for data in sorted(payload["regions"], key=lambda r: r["levl_code"]):
                _upsert_region(data, vintage, user, report, dry_run)

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
