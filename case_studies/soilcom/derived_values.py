"""Compute and persist derived CollectionPropertyValue records.

When a CPV for *specific waste collected* exists
but *total waste collected* does not (or vice-versa),
the missing value can be derived via population data:

    specific = total_Mg × 1000 / population
    total_Mg = specific × population / 1000

Derived records are stored with ``is_derived=True`` so they can be
distinguished from manually entered data and regenerated at will.
"""

import logging
from dataclasses import dataclass
from functools import lru_cache

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction

from maps.models import Attribute, RegionAttributeValue
from utils.object_management.models import get_default_owner
from utils.properties.models import Property, Unit

from .models import CollectionPropertyValue

logger = logging.getLogger(__name__)

# Names of the canonical records used for derivation.
# Optional settings can override these when projects use different naming:
# - SOILCOM_SPECIFIC_WASTE_PROPERTY_NAME
# - SOILCOM_TOTAL_WASTE_PROPERTY_NAME
# - SOILCOM_SPECIFIC_WASTE_UNIT_NAME
# - SOILCOM_TOTAL_WASTE_UNIT_NAME
# - SOILCOM_POPULATION_ATTRIBUTE_NAME

_DEFAULT_SPECIFIC_WASTE_PROPERTY_NAME = "specific waste collected"
_DEFAULT_TOTAL_WASTE_PROPERTY_NAME = "total waste collected"
_DEFAULT_SPECIFIC_WASTE_UNIT_NAME = "kg/(cap.*a)"
_DEFAULT_TOTAL_WASTE_UNIT_NAME = "Mg/a"
_DEFAULT_POPULATION_ATTRIBUTE_NAME = "Population"

# Optional settings can pin explicit IDs when desired:
# - SOILCOM_SPECIFIC_WASTE_PROPERTY_ID
# - SOILCOM_TOTAL_WASTE_PROPERTY_ID
# - SOILCOM_SPECIFIC_WASTE_UNIT_ID
# - SOILCOM_TOTAL_WASTE_UNIT_ID
# - SOILCOM_POPULATION_ATTRIBUTE_ID

# Conversion factor: 1 Mg = 1000 kg
_MG_TO_KG = 1000


def convert_specific_to_total_mg(value, population, ndigits=2):
    """Convert specific waste (kg/cap/a) to total waste (Mg/a)."""
    if not population or population <= 0:
        return None
    total_mg = value * population / _MG_TO_KG
    if ndigits is None:
        return total_mg
    return round(total_mg, ndigits)


def convert_total_to_specific(value, population, ndigits=2):
    """Convert total waste (Mg/a) to specific waste (kg/cap/a)."""
    if not population or population <= 0:
        return None
    specific = value * _MG_TO_KG / population
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


def _resolve_named_record_id(
    *,
    model,
    id_setting: str,
    name_setting: str,
    default_name: str,
    label: str,
):
    configured_id = getattr(settings, id_setting, None)
    if configured_id is not None:
        if not model.objects.filter(pk=configured_id).exists():
            raise ImproperlyConfigured(
                f"{id_setting}={configured_id} does not exist for {label}."
            )
        return configured_id

    target_name = getattr(settings, name_setting, default_name)
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
        f"Configure {id_setting} to disambiguate."
    )


@lru_cache(maxsize=1)
def get_derived_property_config():
    """Resolve and cache property/attribute IDs required for derivation."""
    specific_property_id = _resolve_named_record_id(
        model=Property,
        id_setting="SOILCOM_SPECIFIC_WASTE_PROPERTY_ID",
        name_setting="SOILCOM_SPECIFIC_WASTE_PROPERTY_NAME",
        default_name=_DEFAULT_SPECIFIC_WASTE_PROPERTY_NAME,
        label="specific waste property",
    )
    total_property_id = _resolve_named_record_id(
        model=Property,
        id_setting="SOILCOM_TOTAL_WASTE_PROPERTY_ID",
        name_setting="SOILCOM_TOTAL_WASTE_PROPERTY_NAME",
        default_name=_DEFAULT_TOTAL_WASTE_PROPERTY_NAME,
        label="total waste property",
    )
    population_attribute_id = _resolve_named_record_id(
        model=Attribute,
        id_setting="SOILCOM_POPULATION_ATTRIBUTE_ID",
        name_setting="SOILCOM_POPULATION_ATTRIBUTE_NAME",
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
        id_setting="SOILCOM_SPECIFIC_WASTE_UNIT_ID",
        name_setting="SOILCOM_SPECIFIC_WASTE_UNIT_NAME",
        default_name=_DEFAULT_SPECIFIC_WASTE_UNIT_NAME,
        label="specific waste unit",
    )
    total_unit_id = _resolve_named_record_id(
        model=Unit,
        id_setting="SOILCOM_TOTAL_WASTE_UNIT_ID",
        name_setting="SOILCOM_TOTAL_WASTE_UNIT_NAME",
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


def get_convertible_property_ids():
    """Return property IDs for CPVs that can be converted to counterparts."""
    cfg = get_derived_property_config()
    return frozenset({cfg.specific_property_id, cfg.total_property_id})


def is_convertible_property(property_id):
    """Return whether the given property ID has a derived counterpart mapping."""
    return property_id in get_convertible_property_ids()


@lru_cache(maxsize=1)
def _counterpart_mapping():
    cfg = get_derived_value_config()
    return {
        cfg.specific_property_id: (cfg.total_property_id, cfg.total_unit_id),
        cfg.total_property_id: (cfg.specific_property_id, cfg.specific_unit_id),
    }


def get_population_for_collection(collection, year=None):
    """Return the population for a collection's catchment region.

    Uses the most recent ``RegionAttributeValue`` with
    ``attribute_id=SOILCOM_POPULATION_ATTRIBUTE_*`` for the catchment's region.
    If *year* is given, prefers the value closest to that year.
    """
    cfg = get_derived_property_config()
    region_id = getattr(collection.catchment, "region_id", None)
    if region_id is None:
        return None

    qs = RegionAttributeValue.objects.filter(
        region_id=region_id,
        attribute_id=cfg.population_attribute_id,
    )
    if not qs.exists():
        return None

    if year:
        # Prefer value for the exact year, fall back to most recent
        exact = qs.filter(date__year=year).first()
        if exact:
            return exact.value

    return qs.order_by("-date").values_list("value", flat=True).first()


def compute_counterpart_value(cpv):
    """Compute the counterpart amount for a single CPV record.

    Returns ``(target_property_id, target_unit_id, computed_average)``
    or ``None`` if the conversion is not applicable.
    """
    cfg = get_derived_value_config()
    mapping = _counterpart_mapping().get(cpv.property_id)
    if mapping is None:
        return None

    target_property_id, target_unit_id = mapping
    population = get_population_for_collection(cpv.collection, year=cpv.year)
    if not population or population <= 0:
        return None

    if cpv.property_id == cfg.specific_property_id:
        # specific → total: total_Mg = specific_kg * population / 1000
        computed = convert_specific_to_total_mg(cpv.average, population, ndigits=2)
    else:
        # total → specific: specific_kg = total_Mg * 1000 / population
        computed = convert_total_to_specific(cpv.average, population, ndigits=2)

    return target_property_id, target_unit_id, computed


def _derived_counterpart_qs(cpv, target_property_id):
    return CollectionPropertyValue.objects.filter(
        collection=cpv.collection,
        property_id=target_property_id,
        year=cpv.year,
        is_derived=True,
    )


def _prune_duplicate_derived_rows(cpv, target_property_id):
    """Keep a single derived counterpart row and delete older duplicates."""
    derived_qs = _derived_counterpart_qs(cpv, target_property_id).order_by(
        "-lastmodified_at", "-pk"
    )
    keep_id = derived_qs.values_list("pk", flat=True).first()
    if keep_id is None:
        return 0
    deleted_count, _ = derived_qs.exclude(pk=keep_id).delete()
    if deleted_count:
        logger.warning(
            "Deleted %d duplicate derived CPV(s) for collection id=%s, property=%s, year=%s",
            deleted_count,
            cpv.collection_id,
            target_property_id,
            cpv.year,
        )
    return deleted_count


def create_or_update_derived_cpv(cpv, *, owner=None, publication_status=None):
    """Create or update the derived counterpart for a single CPV.

    Skips if the CPV is itself derived (prevents infinite loops) or if
    a non-derived (manually entered) counterpart already exists.

    *owner* and *publication_status* override the values copied from the
    source CPV when provided (useful for batch backfills).

    Returns ``(derived_instance, action)`` where action is one of:
    ``"created"``, ``"updated"``, ``"skipped"``.
    """
    if cpv.is_derived:
        return None, "skipped"

    result = compute_counterpart_value(cpv)
    if result is None:
        return None, "skipped"

    target_property_id, target_unit_id, computed_avg = result

    # Check if a manually entered value already exists
    existing = CollectionPropertyValue.objects.filter(
        collection=cpv.collection,
        property_id=target_property_id,
        year=cpv.year,
        is_derived=False,
    ).exists()
    if existing:
        # Manual counterpart takes precedence: remove stale derived values.
        deleted_count, _ = _derived_counterpart_qs(cpv, target_property_id).delete()
        if deleted_count:
            logger.debug(
                "Deleted %d stale derived CPV(s) due to manual counterpart "
                "(property=%s, year=%s, collection id=%s)",
                deleted_count,
                target_property_id,
                cpv.year,
                cpv.collection_id,
            )
        return None, "skipped"

    # Defensive cleanup for pre-constraint duplicates.
    derived_qs = _derived_counterpart_qs(cpv, target_property_id)
    if derived_qs.count() > 1:
        _prune_duplicate_derived_rows(cpv, target_property_id)

    # Create or update the derived record
    derived, created = CollectionPropertyValue.objects.update_or_create(
        collection=cpv.collection,
        property_id=target_property_id,
        year=cpv.year,
        is_derived=True,
        defaults={
            "name": f"derived from {cpv.property.name}",
            "average": computed_avg,
            "unit_id": target_unit_id,
            "owner": owner if owner is not None else cpv.owner,
            "publication_status": (
                publication_status
                if publication_status is not None
                else cpv.publication_status
            ),
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
    """Delete derived counterparts when a source CPV is deleted.

    Only deletes derived records for the counterpart property, not
    manually entered ones.
    """
    if cpv.is_derived:
        return 0

    mapping = _counterpart_mapping().get(cpv.property_id)
    if mapping is None:
        return 0

    target_property_id, _ = mapping
    count, _ = CollectionPropertyValue.objects.filter(
        collection=cpv.collection,
        property_id=target_property_id,
        year=cpv.year,
        is_derived=True,
    ).delete()
    if count:
        logger.debug(
            "Deleted %d derived CPV(s) (property=%s, year=%s) for collection id=%s",
            count,
            target_property_id,
            cpv.year,
            cpv.collection_id,
        )
    return count


def backfill_derived_values(dry_run=False, owner=None, publication_status=None):
    """Compute derived counterparts for all existing CPV records.

    Iterates over all non-derived CPV records for the configured
    specific and total waste properties,
    creating or updating derived counterparts where the counterpart
    does not already exist as a manual entry.

    *owner* and *publication_status* are forwarded to
    ``create_or_update_derived_cpv`` to override the values that would
    otherwise be copied from each source CPV.

    Returns a dict with counts: ``{created: int, updated: int, skipped: int}``.
    """
    stats = {"created": 0, "updated": 0, "skipped": 0}
    cfg = get_derived_value_config()
    source_qs = (
        CollectionPropertyValue.objects.filter(
            property_id__in=[cfg.specific_property_id, cfg.total_property_id],
            is_derived=False,
        )
        .exclude(average=0)
        .select_related("collection__catchment", "property", "unit")
    )

    total = source_qs.count()
    logger.info("Backfilling derived values for %d source CPV records...", total)

    for i, cpv in enumerate(source_qs.iterator(), 1):
        if dry_run:
            result = compute_counterpart_value(cpv)
            if result is None:
                stats["skipped"] += 1
                continue

            target_property_id, _, _ = result
            manual_exists = CollectionPropertyValue.objects.filter(
                collection=cpv.collection,
                property_id=target_property_id,
                year=cpv.year,
                is_derived=False,
            ).exists()
            if manual_exists:
                stats["skipped"] += 1
                continue

            derived_exists = _derived_counterpart_qs(cpv, target_property_id).exists()
            if derived_exists:
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
