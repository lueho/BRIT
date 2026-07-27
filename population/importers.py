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

from maps.models import LauRegion, NutsRegion

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
    import_run_id: int | None = None


def _value_in_persons(raw_value, unit):
    return (Decimal(raw_value) * UNIT_TO_PERSONS[unit]).quantize(Decimal("0.001"))


def _match_region(scheme, code):
    if scheme == "NUTS":
        qs = NutsRegion.objects.filter(nuts_id=code)
    else:
        qs = LauRegion.objects.filter(lau_id=code)
    regions = list(qs[:2])
    if len(regions) == 1:
        return regions[0], None
    if not regions:
        return None, "no matching region"
    return None, "ambiguous region code (multiple matches)"


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

        for index, observation in enumerate(payload["observations"]):
            region, error = _match_region(
                observation["region_scheme"], observation["region_code"]
            )
            if error is not None:
                report.errors.append(
                    {
                        "index": index,
                        "region_scheme": observation["region_scheme"],
                        "region_code": observation["region_code"],
                        "reason": error,
                    }
                )
                continue

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
