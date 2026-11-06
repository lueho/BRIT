"""Maintain source-bound generated collection measurements.

Each eligible raw value owns one read-only projection. Conversion arithmetic
and population resolution remain unchanged. Manual evidence and legacy
generated rows without verified source linkage are never reused or deleted.
"""

import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models import Q

from maps.models import RegionProperty
from maps.population.models import TemporalBasis
from maps.population.services import resolve_population
from maps.validation import RegionCompositionError
from utils.object_management.models import get_default_owner
from utils.properties.models import Property, Unit

from .models import CollectionPropertyValue
from .projection_queries import (
    preferred_measurement_queryset as preferred_measurement_queryset,
)

logger = logging.getLogger(__name__)

_SETTING_NOT_SET = object()

# Names of the canonical records used for derivation.
# Optional settings can override these when projects use different naming:
# - WASTE_COLLECTION_SPECIFIC_WASTE_PROPERTY_NAME
# - WASTE_COLLECTION_TOTAL_WASTE_PROPERTY_NAME
# - WASTE_COLLECTION_SPECIFIC_WASTE_UNIT_NAME
# - WASTE_COLLECTION_TOTAL_WASTE_UNIT_NAME
# - WASTE_COLLECTION_POPULATION_ATTRIBUTE_NAME
# Legacy SOILCOM_* aliases remain supported for backward compatibility.

_DEFAULT_SPECIFIC_WASTE_PROPERTY_NAME = "specific waste collected"
_DEFAULT_TOTAL_WASTE_PROPERTY_NAME = "total waste collected"
_DEFAULT_SPECIFIC_WASTE_UNIT_NAME = "kg/(cap·a)"
_DEFAULT_TOTAL_WASTE_UNIT_NAME = "Mg/a"
_DEFAULT_POPULATION_ATTRIBUTE_NAME = "Population"

# Optional settings can pin explicit IDs when desired:
# - WASTE_COLLECTION_SPECIFIC_WASTE_PROPERTY_ID
# - WASTE_COLLECTION_TOTAL_WASTE_PROPERTY_ID
# - WASTE_COLLECTION_SPECIFIC_WASTE_UNIT_ID
# - WASTE_COLLECTION_TOTAL_WASTE_UNIT_ID
# - WASTE_COLLECTION_POPULATION_ATTRIBUTE_ID
# Legacy SOILCOM_* aliases remain supported for backward compatibility.

# Conversion factor: 1 Mg = 1000 kg
_MG_TO_KG = 1000


def convert_specific_to_total_mg(value, population, ndigits=2):
    """Convert specific waste (kg/cap/a) to total waste (Mg/a)."""
    if not population or population <= 0:
        return None
    total_mg = Decimal(str(value)) * Decimal(str(population)) / _MG_TO_KG
    if ndigits is None:
        return total_mg
    return round(total_mg, ndigits)


def convert_total_to_specific(value, population, ndigits=2):
    """Convert total waste (Mg/a) to specific waste (kg/cap/a)."""
    if not population or population <= 0:
        return None
    specific = Decimal(str(value)) * _MG_TO_KG / Decimal(str(population))
    if ndigits is None:
        return specific
    return round(specific, ndigits)


@dataclass(frozen=True)
class DerivedPropertyConfig:
    specific_property_id: int
    total_property_id: int
    population_attribute_id: int


@dataclass(frozen=True)
class DerivedValueConfig(DerivedPropertyConfig):
    specific_unit_id: int
    total_unit_id: int


def _get_configured_setting(*setting_names: str):
    """Return the first explicitly configured setting value and its name."""
    for setting_name in setting_names:
        value = getattr(settings, setting_name, _SETTING_NOT_SET)
        if value is not _SETTING_NOT_SET:
            return setting_name, value
    return setting_names[0], None


def _resolve_named_record_id(
    *,
    model,
    id_settings: tuple[str, ...],
    name_settings: tuple[str, ...],
    default_name: str,
    label: str,
):
    configured_id_setting, configured_id = _get_configured_setting(*id_settings)
    if configured_id is not None:
        if not model.objects.filter(pk=configured_id).exists():
            raise ImproperlyConfigured(
                f"{configured_id_setting}={configured_id} does not exist for {label}."
            )
        return configured_id

    _, target_name = _get_configured_setting(*name_settings)
    if target_name is None:
        target_name = default_name
    qs = model.objects.filter(name=target_name)
    if qs.count() == 1:
        return qs.values_list("pk", flat=True).first()

    default_owner = None
    if hasattr(model, "owner"):
        try:
            default_owner = get_default_owner()
        except Exception:
            default_owner = None

    if hasattr(model, "publication_status"):
        published_value = getattr(model, "STATUS_PUBLISHED", "published")
        published_qs = qs.filter(publication_status=published_value)
        if published_qs.count() == 1:
            return published_qs.values_list("pk", flat=True).first()
        if default_owner is not None:
            pub_owner_qs = published_qs.filter(owner=default_owner)
            if pub_owner_qs.count() == 1:
                return pub_owner_qs.values_list("pk", flat=True).first()

    if default_owner is not None:
        owner_qs = qs.filter(owner=default_owner)
        if owner_qs.count() == 1:
            return owner_qs.values_list("pk", flat=True).first()

    raise ImproperlyConfigured(
        f"Could not unambiguously resolve {label} named '{target_name}'. "
        f"Configure {id_settings[0]} to disambiguate."
    )


@lru_cache(maxsize=1)
def get_derived_property_config():
    """Resolve and cache property/attribute IDs required for derivation."""
    specific_property_id = _resolve_named_record_id(
        model=Property,
        id_settings=(
            "WASTE_COLLECTION_SPECIFIC_WASTE_PROPERTY_ID",
            "SOILCOM_SPECIFIC_WASTE_PROPERTY_ID",
        ),
        name_settings=(
            "WASTE_COLLECTION_SPECIFIC_WASTE_PROPERTY_NAME",
            "SOILCOM_SPECIFIC_WASTE_PROPERTY_NAME",
        ),
        default_name=_DEFAULT_SPECIFIC_WASTE_PROPERTY_NAME,
        label="specific waste property",
    )
    total_property_id = _resolve_named_record_id(
        model=Property,
        id_settings=(
            "WASTE_COLLECTION_TOTAL_WASTE_PROPERTY_ID",
            "SOILCOM_TOTAL_WASTE_PROPERTY_ID",
        ),
        name_settings=(
            "WASTE_COLLECTION_TOTAL_WASTE_PROPERTY_NAME",
            "SOILCOM_TOTAL_WASTE_PROPERTY_NAME",
        ),
        default_name=_DEFAULT_TOTAL_WASTE_PROPERTY_NAME,
        label="total waste property",
    )
    population_attribute_id = _resolve_named_record_id(
        model=RegionProperty,
        id_settings=(
            "WASTE_COLLECTION_POPULATION_ATTRIBUTE_ID",
            "SOILCOM_POPULATION_ATTRIBUTE_ID",
        ),
        name_settings=(
            "WASTE_COLLECTION_POPULATION_ATTRIBUTE_NAME",
            "SOILCOM_POPULATION_ATTRIBUTE_NAME",
        ),
        default_name=_DEFAULT_POPULATION_ATTRIBUTE_NAME,
        label="population attribute",
    )

    if specific_property_id == total_property_id:
        raise ImproperlyConfigured(
            "Specific and total waste property IDs must not be identical."
        )

    return DerivedPropertyConfig(
        specific_property_id=specific_property_id,
        total_property_id=total_property_id,
        population_attribute_id=population_attribute_id,
    )


@lru_cache(maxsize=1)
def get_derived_value_config():
    """Resolve and cache full IDs required for derived value computation."""
    prop_cfg = get_derived_property_config()
    specific_unit_id = _resolve_named_record_id(
        model=Unit,
        id_settings=(
            "WASTE_COLLECTION_SPECIFIC_WASTE_UNIT_ID",
            "SOILCOM_SPECIFIC_WASTE_UNIT_ID",
        ),
        name_settings=(
            "WASTE_COLLECTION_SPECIFIC_WASTE_UNIT_NAME",
            "SOILCOM_SPECIFIC_WASTE_UNIT_NAME",
        ),
        default_name=_DEFAULT_SPECIFIC_WASTE_UNIT_NAME,
        label="specific waste unit",
    )
    total_unit_id = _resolve_named_record_id(
        model=Unit,
        id_settings=(
            "WASTE_COLLECTION_TOTAL_WASTE_UNIT_ID",
            "SOILCOM_TOTAL_WASTE_UNIT_ID",
        ),
        name_settings=(
            "WASTE_COLLECTION_TOTAL_WASTE_UNIT_NAME",
            "SOILCOM_TOTAL_WASTE_UNIT_NAME",
        ),
        default_name=_DEFAULT_TOTAL_WASTE_UNIT_NAME,
        label="total waste unit",
    )
    if specific_unit_id == total_unit_id:
        raise ImproperlyConfigured(
            "Specific and total waste unit IDs must not be identical."
        )

    return DerivedValueConfig(
        specific_property_id=prop_cfg.specific_property_id,
        total_property_id=prop_cfg.total_property_id,
        population_attribute_id=prop_cfg.population_attribute_id,
        specific_unit_id=specific_unit_id,
        total_unit_id=total_unit_id,
    )


def clear_derived_value_config_cache():
    """Clear cached derived-value configuration (useful for tests)."""
    get_derived_property_config.cache_clear()
    get_derived_value_config.cache_clear()
    _counterpart_mapping.cache_clear()


@lru_cache(maxsize=1)
def _counterpart_mapping():
    cfg = get_derived_value_config()
    return {
        cfg.specific_property_id: (cfg.total_property_id, cfg.total_unit_id),
        cfg.total_property_id: (cfg.specific_property_id, cfg.specific_unit_id),
    }


def get_convertible_property_ids():
    """Return property IDs for CPVs that can be converted to counterparts."""
    cfg = get_derived_property_config()
    return frozenset({cfg.specific_property_id, cfg.total_property_id})


def is_convertible_property(property_id):
    """Return whether the given property ID has a derived counterpart mapping."""
    return property_id in get_convertible_property_ids()


def _population_for_collection(collection, year=None):
    """Resolve an exact-year annual average, retaining its input provenance.

    Stocks and legacy attributes of unknown basis cannot silently substitute.
    """
    if not year:
        return None

    region = getattr(collection.catchment, "region", None)
    if region is None:
        return None

    try:
        result = resolve_population(
            region, year, temporal_basis=TemporalBasis.CALENDAR_YEAR_AVERAGE
        )
    except RegionCompositionError:
        logger.warning(
            "Invalid region composition for region id=%s; no population resolved.",
            region.pk,
        )
        return None
    return result


def get_population_for_collection(collection, year=None):
    """Return the exact-year annual-average population, or ``None``."""
    result = _population_for_collection(collection, year)
    return result.value if result is not None else None


def _compute_counterpart_value(cpv):
    cfg = get_derived_value_config()
    mapping = _counterpart_mapping().get(cpv.property_id)
    if mapping is None:
        return None

    target_property_id, target_unit_id = mapping
    expected_unit = (
        cfg.specific_unit_id
        if cpv.property_id == cfg.specific_property_id
        else cfg.total_unit_id
    )
    if cpv.unit_id != expected_unit:
        return None
    population_result = _population_for_collection(cpv.collection, year=cpv.year)
    if population_result is None:
        return None
    population = population_result.value
    if not population or population <= 0:
        return None

    if cpv.property_id == cfg.specific_property_id:
        # specific → total: total_Mg = specific_kg * population / 1000
        computed = convert_specific_to_total_mg(cpv.average, population, ndigits=2)
    else:
        # total → specific: specific_kg = total_Mg * 1000 / population
        computed = convert_total_to_specific(cpv.average, population, ndigits=2)

    return target_property_id, target_unit_id, computed, population_result


def compute_counterpart_value(cpv):
    """Return ``(property_id, unit_id, average)`` or ``None`` if unsuitable."""
    result = _compute_counterpart_value(cpv)
    return result[:3] if result is not None else None


def _calculation_description(cpv, population, *, from_specific):
    """Snapshot the inputs rather than relying on revisable observation rows."""
    observations = []
    for observation in population.observations:
        dataset = observation.dataset
        run = observation.import_run
        observations.append(
            {
                "id": observation.pk,
                "region_id": observation.region_id,
                "year": observation.year,
                "value": str(observation.value),
                "dataset": dataset.slug,
                "provider": dataset.provider,
                "source_code": dataset.source_code,
                "classification_version": dataset.classification_version,
                "import_run_id": observation.import_run_id,
                "release": run.structure_version if run is not None else None,
                "checksum": run.checksum if run is not None else None,
                "source_status": observation.source_status,
                "flags": observation.flags,
            }
        )
    return json.dumps(
        {
            "formula": (
                "specific_kg * population / 1000"
                if from_specific
                else "total_Mg * 1000 / population"
            ),
            "source_cpv": {
                "id": cpv.pk,
                "average": str(cpv.average),
                "unit_id": cpv.unit_id,
            },
            "population": {
                "value": str(population.value),
                "year": population.year,
                "temporal_basis": population.temporal_basis,
                "method": population.method,
                "is_provisional": population.is_provisional,
                "is_mixed_provenance": population.is_mixed_provenance,
                "observations": observations,
            },
        },
        sort_keys=True,
    )


def _linked_generated_qs(cpv):
    """Select only generated outputs explicitly bound to this source."""
    return CollectionPropertyValue.objects.filter(
        is_derived=True, derived_from_id=cpv.pk
    )


def _write_locked_projection(source, *, owner, publication_status):
    """Compute and persist using a source already locked by the caller."""
    result = _compute_counterpart_value(source)
    if result is None:
        _linked_generated_qs(source).delete()
        return None, "skipped"

    target_property_id, target_unit_id, computed_avg, population = result
    effective_status = (
        source.publication_status if publication_status is None else publication_status
    )
    submitted_at = source.submitted_at
    approved_at = None
    approved_by = None
    if effective_status in (
        CollectionPropertyValue.STATUS_PUBLISHED,
        CollectionPropertyValue.STATUS_ARCHIVED,
    ):
        approved_at = source.approved_at
        approved_by = source.approved_by
    elif effective_status != CollectionPropertyValue.STATUS_REVIEW:
        submitted_at = None

    derived, created = CollectionPropertyValue.objects.update_or_create(
        derived_from=source,
        is_derived=True,
        defaults={
            "collection_id": source.collection_id,
            "property_id": target_property_id,
            "year": source.year,
            "name": f"derived from {source.property.name}",
            "average": computed_avg,
            "standard_deviation": None,
            "description": _calculation_description(
                source,
                population,
                from_specific=source.property_id
                == get_derived_value_config().specific_property_id,
            ),
            "unit_id": target_unit_id,
            "owner_id": source.owner_id if owner is None else owner.pk,
            "publication_status": effective_status,
            "submitted_at": submitted_at,
            "approved_at": approved_at,
            "approved_by": approved_by,
        },
    )
    return derived, "created" if created else "updated"


def create_or_update_derived_cpv(cpv, *, owner=None, publication_status=None):
    """Maintain one output from the freshly locked raw source.

    Metadata overrides are compatibility copies, never independent governance.
    Manual evidence and unlinked legacy outputs are not cleanup candidates.
    """
    if not isinstance(cpv, CollectionPropertyValue) or cpv.pk is None:
        return None, "skipped"

    failure = None
    outcome = (None, "skipped")
    with transaction.atomic():
        source = (
            CollectionPropertyValue.objects.select_for_update(no_key=True)
            .filter(pk=cpv.pk)
            .first()
        )
        if source is None or source.is_derived:
            return None, "skipped"
        try:
            with transaction.atomic():
                outcome = _write_locked_projection(
                    source,
                    owner=owner,
                    publication_status=publication_status,
                )
        except Exception as exc:
            # Roll back partial output writes, then invalidate under the same
            # raw lock. Late cleanup must not delete a newer worker's output.
            _linked_generated_qs(source).delete()
            failure = exc
    if failure is not None:
        raise failure
    return outcome


def delete_derived_cpv(cpv):
    """Remove only this raw source's explicitly linked generated output."""
    if not isinstance(cpv, CollectionPropertyValue) or cpv.is_derived or cpv.pk is None:
        return 0
    count, _ = _linked_generated_qs(cpv).delete()
    return count


def backfill_derived_values(dry_run=False, owner=None, publication_status=None):
    """Maintain explicit per-source output identities, never infer legacy links.

    Dry runs lock each source and change no records. Ineligible sources are
    skipped; a real run also removes their stale linked outputs. Counts describe
    source outcomes, not unique data keys or individual deleted rows.
    """
    stats = {"created": 0, "updated": 0, "skipped": 0}
    cfg = get_derived_value_config()
    source_qs = (
        CollectionPropertyValue.objects.filter(is_derived=False)
        .filter(
            Q(property_id__in=[cfg.specific_property_id, cfg.total_property_id])
            | Q(generated_values__is_derived=True)
        )
        .distinct()
        .order_by("pk")
    )
    for source_id in source_qs.values_list("pk", flat=True).iterator():
        if dry_run:
            with transaction.atomic():
                source = (
                    CollectionPropertyValue.objects.select_for_update(no_key=True)
                    .filter(pk=source_id, is_derived=False)
                    .first()
                )
                if source is None or _compute_counterpart_value(source) is None:
                    action = "skipped"
                else:
                    action = (
                        "updated"
                        if _linked_generated_qs(source).exists()
                        else "created"
                    )
        else:
            source = (
                CollectionPropertyValue.objects.only("pk").filter(pk=source_id).first()
            )
            if source is None:
                action = "skipped"
            else:
                # The generator owns its lock and invalidation commit. An
                # additional outer transaction would undo cleanup on error.
                _derived, action = create_or_update_derived_cpv(
                    source, owner=owner, publication_status=publication_status
                )
        stats[action] += 1
    logger.info(
        "Backfill complete: %d created, %d updated, %d skipped",
        stats["created"],
        stats["updated"],
        stats["skipped"],
    )
    return stats
