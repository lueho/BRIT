"""Provider-neutral ingestion for the population bulk-import contract.

Takes a validated import payload, matches provider region codes to BRIT
``maps.Region`` rows, and upserts :class:`PopulationObservation` rows under a
:class:`PopulationImportRun`. Ingestion is all-or-nothing: if any observation
fails to match or convert, nothing is persisted and the failures are returned
in the report. ``dry_run`` validates and reports without persisting.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from maps.models import LauRegion, NutsRegion, NutsVintage

from .contracts import UNIT_TO_PERSONS
from .models import PopulationDataset, PopulationImportRun, PopulationObservation


@dataclass
class ImportReport:
    schema_version: str
    dry_run: bool
    committed: bool = False
    dataset_slug: str | None = None
    dataset_created: bool = False
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    resolutions: dict = field(default_factory=dict)
    import_run_id: int | None = None


def _value_in_persons(raw_value, unit):
    return (Decimal(raw_value) * UNIT_TO_PERSONS[unit]).quantize(Decimal("0.001"))


@dataclass
class RegionMatch:
    region: object | None
    resolution: str
    error: str | None = None
    matched_version: str = ""


def _resolve_vintage(region_version, classification_version):
    """Select the NUTS vintage a provider code refers to.

    ``region_version`` (per observation) wins over the dataset's
    ``classification_version``; without either, the current vintage applies.
    """
    for label, resolution in (
        (region_version, "exact"),
        (classification_version, "exact"),
    ):
        if label:
            return NutsVintage.resolve(label), resolution
    return NutsVintage.current(), "current_vintage"


def _unique_or_error(regions, resolution, matched_version=""):
    if len(regions) == 1:
        return RegionMatch(regions[0], resolution, matched_version=matched_version)
    if not regions:
        return RegionMatch(None, resolution, error="no matching region")
    return RegionMatch(
        None, resolution, error="ambiguous region code (multiple matches)"
    )


def _match_region(scheme, code, region_version="", classification_version=""):
    """Match a provider region code, scoped to the requested NUTS vintage.

    Codes are only unique within a vintage, so an unscoped lookup would report
    every code carried by more than one vintage as ambiguous. When BRIT does not
    hold the requested vintage but the code exists in exactly one held vintage,
    that row is matched and the fallback is reported.
    """
    if scheme != "NUTS":
        return _unique_or_error(
            list(LauRegion.objects.filter(lau_id=code)[:2]), "exact"
        )

    vintage, resolution = _resolve_vintage(region_version, classification_version)
    if vintage is not None:
        regions = list(NutsRegion.objects.filter(nuts_id=code, version=vintage)[:2])
        if regions:
            return _unique_or_error(
                regions, resolution, matched_version=str(vintage.year)
            )

    regions = list(
        NutsRegion.objects.filter(nuts_id=code).select_related("version")[:2]
    )
    match = _unique_or_error(regions, "fallback_vintage")
    if match.region is not None:
        match.matched_version = (
            str(match.region.version.year) if match.region.version_id else ""
        )
    return match


def _upsert_dataset(data):
    slug = data["slug"]
    defaults = {
        "name": data["name"],
        "provider": data["provider"],
        "source_code": data.get("external_id", ""),
        "geographic_scope": data["geographic_scope"],
        "temporal_basis": data["temporal_basis"],
        "source_unit": data.get("source_unit", ""),
        "classification_version": data.get("classification_version", ""),
        "is_canonical": data.get("is_canonical", False),
    }
    dataset, created = PopulationDataset.objects.get_or_create(
        slug=slug, defaults=defaults
    )
    if not created:
        for field_name, value in defaults.items():
            setattr(dataset, field_name, value)
        dataset.save()
    return dataset, created


def import_population_payload(payload, *, user=None, dry_run=False):
    """Import a validated payload. Returns an :class:`ImportReport`.

    ``payload`` must be the ``validated_data`` from
    :class:`population.serializers.PopulationImportSerializer`.
    """
    dry_run = bool(dry_run or payload.get("dry_run"))
    report = ImportReport(schema_version=payload["schema_version"], dry_run=dry_run)

    with transaction.atomic():
        dataset, dataset_created = _upsert_dataset(payload["dataset"])
        report.dataset_slug = dataset.slug
        report.dataset_created = dataset_created

        run = PopulationImportRun.objects.create(
            dataset=dataset,
            extracted_at=payload.get("extracted_at") or timezone.now(),
            upstream_updated_at=payload.get("upstream_updated_at"),
            checksum=payload.get("checksum", ""),
            structure_version=payload["dataset"].get("release", ""),
        )

        classification_version = payload["dataset"].get("classification_version", "")

        for index, observation in enumerate(payload["observations"]):
            requested_version = observation.get("region_version", "")
            match = _match_region(
                observation["region_scheme"],
                observation["region_code"],
                region_version=requested_version,
                classification_version=classification_version,
            )
            if match.error is not None:
                report.errors.append(
                    {
                        "index": index,
                        "region_scheme": observation["region_scheme"],
                        "region_code": observation["region_code"],
                        "reason": match.error,
                    }
                )
                continue

            region = match.region
            report.resolutions[match.resolution] = (
                report.resolutions.get(match.resolution, 0) + 1
            )
            if match.resolution == "fallback_vintage":
                report.warnings.append(
                    {
                        "index": index,
                        "region_scheme": observation["region_scheme"],
                        "region_code": observation["region_code"],
                        "requested_version": requested_version
                        or classification_version,
                        "matched_version": match.matched_version,
                        "resolution": "fallback_vintage",
                    }
                )

            value = _value_in_persons(observation["value"], observation["unit"])
            year = observation["reference_period"]
            defaults = {
                "value": value,
                "source_status": observation["source_status"],
                "flags": observation.get("flags", ""),
                "import_run": run,
            }
            existing = PopulationObservation.objects.filter(
                dataset=dataset, region=region, year=year
            ).first()
            if existing is None:
                PopulationObservation.objects.create(
                    dataset=dataset, region=region, year=year, **defaults
                )
                report.created += 1
            elif (
                existing.value == value
                and existing.source_status == observation["source_status"]
                and existing.flags == observation.get("flags", "")
            ):
                report.unchanged += 1
            else:
                for field_name, field_value in defaults.items():
                    setattr(existing, field_name, field_value)
                existing.save()
                report.updated += 1

        has_errors = bool(report.errors)
        if dry_run or has_errors:
            transaction.set_rollback(True)
            report.committed = False
            report.import_run_id = None
        else:
            run.created_count = report.created
            run.updated_count = report.updated
            run.unchanged_count = report.unchanged
            run.save(
                update_fields=[
                    "created_count",
                    "updated_count",
                    "unchanged_count",
                ]
            )
            report.committed = True
            report.import_run_id = run.pk

    return report
