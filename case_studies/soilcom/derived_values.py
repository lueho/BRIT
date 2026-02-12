"""Compute and persist derived CollectionPropertyValue records.

When a CPV for *specific waste collected* (property 1, kg/cap/a) exists
but *total waste collected* (property 9, Mg/a) does not (or vice-versa),
the missing value can be derived via population data:

    specific = total_Mg × 1000 / population
    total_Mg = specific × population / 1000

Derived records are stored with ``is_derived=True`` so they can be
distinguished from manually entered data and regenerated at will.
"""

import logging

from django.db import transaction

from maps.models import RegionAttributeValue

from .models import CollectionPropertyValue

logger = logging.getLogger(__name__)

# Property IDs (properties_property table)
SPECIFIC_WASTE_PROPERTY_ID = 1
TOTAL_WASTE_PROPERTY_ID = 9

# Unit IDs (properties_unit table)
SPECIFIC_WASTE_UNIT_ID = 2  # kg/(cap.*a)
TOTAL_WASTE_UNIT_ID = 8  # Mg/a

# Region attribute for population count
POPULATION_ATTRIBUTE_ID = 3

# Conversion factor: 1 Mg = 1000 kg
_MG_TO_KG = 1000

# Mapping from source property → target property/unit
_COUNTERPART = {
    SPECIFIC_WASTE_PROPERTY_ID: (TOTAL_WASTE_PROPERTY_ID, TOTAL_WASTE_UNIT_ID),
    TOTAL_WASTE_PROPERTY_ID: (SPECIFIC_WASTE_PROPERTY_ID, SPECIFIC_WASTE_UNIT_ID),
}


def get_population_for_collection(collection, year=None):
    """Return the population for a collection's catchment region.

    Uses the most recent ``RegionAttributeValue`` with
    ``attribute_id=POPULATION_ATTRIBUTE_ID`` for the catchment's region.
    If *year* is given, prefers the value closest to that year.
    """
    region_id = getattr(collection.catchment, "region_id", None)
    if region_id is None:
        return None

    qs = RegionAttributeValue.objects.filter(
        region_id=region_id,
        attribute_id=POPULATION_ATTRIBUTE_ID,
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
    mapping = _COUNTERPART.get(cpv.property_id)
    if mapping is None:
        return None

    target_property_id, target_unit_id = mapping
    population = get_population_for_collection(cpv.collection, year=cpv.year)
    if not population or population <= 0:
        return None

    if cpv.property_id == SPECIFIC_WASTE_PROPERTY_ID:
        # specific → total: total_Mg = specific_kg * population / 1000
        computed = cpv.average * population / _MG_TO_KG
    else:
        # total → specific: specific_kg = total_Mg * 1000 / population
        computed = cpv.average * _MG_TO_KG / population

    return target_property_id, target_unit_id, round(computed, 2)


def create_or_update_derived_cpv(cpv):
    """Create or update the derived counterpart for a single CPV.

    Skips if the CPV is itself derived (prevents infinite loops) or if
    a non-derived (manually entered) counterpart already exists.

    Returns the derived CPV instance, or ``None`` if skipped.
    """
    if cpv.is_derived:
        return None

    result = compute_counterpart_value(cpv)
    if result is None:
        return None

    target_property_id, target_unit_id, computed_avg = result

    # Check if a manually entered value already exists
    existing = CollectionPropertyValue.objects.filter(
        collection=cpv.collection,
        property_id=target_property_id,
        year=cpv.year,
        is_derived=False,
    ).exists()
    if existing:
        return None

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
            "owner": cpv.owner,
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
    return derived


def delete_derived_cpv(cpv):
    """Delete derived counterparts when a source CPV is deleted.

    Only deletes derived records for the counterpart property, not
    manually entered ones.
    """
    if cpv.is_derived:
        return 0

    mapping = _COUNTERPART.get(cpv.property_id)
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


def backfill_derived_values(dry_run=False):
    """Compute derived counterparts for all existing CPV records.

    Iterates over all non-derived CPV records for properties 1 and 9,
    creating or updating derived counterparts where the counterpart
    does not already exist as a manual entry.

    Returns a dict with counts: ``{created: int, updated: int, skipped: int}``.
    """
    stats = {"created": 0, "updated": 0, "skipped": 0}
    source_qs = (
        CollectionPropertyValue.objects.filter(
            property_id__in=[SPECIFIC_WASTE_PROPERTY_ID, TOTAL_WASTE_PROPERTY_ID],
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
            if result is not None:
                stats["created"] += 1
            else:
                stats["skipped"] += 1
            continue

        with transaction.atomic():
            derived = create_or_update_derived_cpv(cpv)

        if derived is None:
            stats["skipped"] += 1
        elif derived._state.adding is False:
            # Was an update_or_create; check if it was newly created
            stats["created"] += 1

        if i % 1000 == 0:
            logger.info("Processed %d / %d CPV records...", i, total)

    logger.info(
        "Backfill complete: %d created, %d updated, %d skipped",
        stats["created"],
        stats["updated"],
        stats["skipped"],
    )
    return stats
