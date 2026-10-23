"""Compute and persist derived CollectionPropertyValue records.

When a CPV for *specific waste collected* exists
but *total waste collected* does not (or vice-versa),
the missing value can be derived via population data:

    specific = total_Mg x 1000 / population
    total_Mg = specific x population / 1000

Generated records are stored with ``is_derived=True`` and an explicit
``derived_from`` link to their source evidence. The link — never the
collection/property/year key — identifies a source's generated output, so
manually entered counterpart evidence always coexists with generated
projections and is preferred only in purpose-specific read queries.
"""

import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models import Exists, IntegerField, OuterRef, Q, Value
from django.db.models.functions import Coalesce

from maps.models import RegionProperty
from maps.population.models import TemporalBasis
from maps.population.services import resolve_population
from maps.validation import RegionCompositionError
from utils.object_management.models import get_default_owner
from utils.properties.models import Property, Unit

from .models import Collection, CollectionPropertyValue

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
_FROZEN_STATUSES = (
    CollectionPropertyValue.STATUS_PUBLISHED,
    CollectionPropertyValue.STATUS_ARCHIVED,
)


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
    """The generated output explicitly linked to ``cpv`` as its source."""
    return CollectionPropertyValue.objects.filter(
        is_derived=True, derived_from_id=cpv.pk
    )


def create_or_update_derived_cpv(cpv, *, owner=None, publication_status=None):
    """Create or update the generated projection linked to a source CPV.

    Output identity is the explicit ``derived_from`` link — never the
    collection/property/year key — so manual counterpart evidence neither
    blocks nor is overwritten by generated output. When the source is no
    longer convertible, only this source's linked output is removed;
    unlinked legacy rows and other sources' artifacts stay untouched.

    *owner* and *publication_status* override the values copied from the
    source CPV when provided (useful for batch backfills).

    Returns ``(derived_instance, action)`` where action is one of:
    ``"created"``, ``"updated"``, ``"skipped"``.
    """
    if cpv.is_derived or cpv.pk is None:
        return None, "skipped"

    mapping = _counterpart_mapping().get(cpv.property_id)
    if mapping is None:
        return None, "skipped"
    # Serialize generators even before a counterpart exists, and lock existing
    # counterparts so a concurrent publication cannot be overwritten.
    Collection.objects.select_for_update().only("pk").get(pk=cpv.collection_id)
    counterparts = list(
        _derived_counterpart_qs(cpv, mapping[0]).select_for_update().order_by("pk")
    )
    for counterpart in counterparts:
        if counterpart.publication_status in _FROZEN_STATUSES:
            return counterpart, "skipped"

    result = _compute_counterpart_value(cpv)
    if result is None:
        # A source that is no longer convertible invalidates only its own
        # linked artifact — stale generated output is not valid evidence.
        deleted_count, _ = _linked_generated_qs(cpv).delete()
        if deleted_count:
            logger.debug(
                "Removed %d stale generated CPV(s) linked to source id=%s",
                deleted_count,
                cpv.pk,
            )
        return None, "skipped"

    target_property_id, target_unit_id, computed_avg = result

    effective_publication_status = (
        publication_status if publication_status is not None else cpv.publication_status
    )
    submitted_at = cpv.submitted_at
    approved_at = None
    approved_by = None
    if effective_publication_status in (
        CollectionPropertyValue.STATUS_PUBLISHED,
        CollectionPropertyValue.STATUS_ARCHIVED,
    ):
        approved_at = cpv.approved_at
        approved_by = cpv.approved_by
    elif effective_publication_status not in (
        CollectionPropertyValue.STATUS_REVIEW,
        CollectionPropertyValue.STATUS_PUBLISHED,
        CollectionPropertyValue.STATUS_ARCHIVED,
    ):
        submitted_at = None

    # Create or update the generated record bound to this source. The copied
    # fields are compatibility metadata; the source governs authorization
    # and lifecycle through the shared policy.
    derived, created = CollectionPropertyValue.objects.update_or_create(
        derived_from=cpv,
        is_derived=True,
        defaults={
            "collection": cpv.collection,
            "property_id": target_property_id,
            "year": cpv.year,
            "name": f"derived from {cpv.property.name}",
            "average": computed_avg,
            "description": _calculation_description(
                cpv,
                population,
                from_specific=cpv.property_id
                == get_derived_value_config().specific_property_id,
            ),
            "unit_id": target_unit_id,
            "owner": owner if owner is not None else cpv.owner,
            "publication_status": effective_publication_status,
            "submitted_at": submitted_at,
            "approved_at": approved_at,
            "approved_by": approved_by,
        },
    )
    action = "Created" if created else "Updated"
    logger.debug(
        "%s derived CPV id=%s (property=%s, year=%s) for collection id=%s",
        action,
        derived.pk,
        target_property_id,
        cpv.year,
        cpv.collection_id,
    )
    return derived, "created" if created else "updated"


def delete_derived_cpv(cpv):
    """Delete the generated output linked to a deleted source CPV.

    Only ``is_derived`` rows explicitly bound to ``cpv`` are removed — never
    another source's output or manual evidence. The FK cascade may already
    have removed the row, in which case ``0`` is returned.
    """
    if cpv.is_derived or cpv.pk is None:
        return 0

    count, _ = _linked_generated_qs(cpv).delete()
    if count:
        logger.debug(
            "Deleted %d generated CPV(s) linked to source id=%s",
            count,
            cpv.pk,
        )
    return count


def preferred_measurement_queryset(qs):
    """Narrow an authorized CPV queryset to preferred measurements.

    Every visible raw measurement is kept; a generated row is excluded only
    when a raw row with the same collection/property/year/unit exists
    within the *same* input queryset. Private or otherwise inaccessible
    manual evidence outside the input queryset never suppresses a
    projection. This is a purpose-specific read preference — it neither
    widens nor narrows general authorization, and direct detail access is
    unaffected.
    """
    normalized = qs.annotate(
        _measurement_year=Coalesce("year", Value(-1), output_field=IntegerField()),
        _measurement_unit=Coalesce("unit_id", Value(-1), output_field=IntegerField()),
    )
    manual = normalized.filter(
        is_derived=False,
        collection_id=OuterRef("collection_id"),
        property_id=OuterRef("property_id"),
        _measurement_year=OuterRef("_measurement_year"),
        _measurement_unit=OuterRef("_measurement_unit"),
    )
    return normalized.annotate(_has_visible_manual=Exists(manual)).filter(
        Q(is_derived=False) | Q(is_derived=True, _has_visible_manual=False)
    )


def backfill_derived_values(dry_run=False, owner=None, publication_status=None):
    """Compute generated counterparts for all existing raw CPV records.

    Iterates over all non-derived CPV records for the configured
    specific and total waste properties, creating or updating the
    generated output explicitly linked to each source via
    ``derived_from``. Manual counterpart rows and legacy unlinked
    generated rows never affect the outcome for a source.

    *owner* and *publication_status* are forwarded to
    ``create_or_update_derived_cpv`` to override the values that would
    otherwise be copied from each source CPV.

    Returns a dict with counts: ``{created: int, updated: int, skipped: int}``
    keyed to the source-bound generator outcome.
    """
    stats = {"created": 0, "updated": 0, "skipped": 0}
    cfg = get_derived_value_config()
    source_qs = CollectionPropertyValue.objects.filter(
        property_id__in=[cfg.specific_property_id, cfg.total_property_id],
        is_derived=False,
    ).select_related("collection__catchment", "property", "unit")

    total = source_qs.count()
    logger.info("Backfilling derived values for %d source CPV records...", total)

    for i, cpv in enumerate(source_qs.iterator(), 1):
        if dry_run:
            result = compute_counterpart_value(cpv)
            if result is None:
                stats["skipped"] += 1
                continue

            if _linked_generated_qs(cpv).exists():
                stats["updated"] += 1
            else:
                stats["created"] += 1
            continue

        with transaction.atomic():
            _derived, action = create_or_update_derived_cpv(
                cpv, owner=owner, publication_status=publication_status
            )
        stats[action] += 1

        if i % 1000 == 0:
            logger.info("Processed %d / %d CPV records...", i, total)

    logger.info(
        "Backfill complete: %d created, %d updated, %d skipped",
        stats["created"],
        stats["updated"],
        stats["skipped"],
    )
    return stats
