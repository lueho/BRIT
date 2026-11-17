"""Maintain source-bound generated aggregate collection measurements.

Each eligible raw aggregate owns one read-only projection. The population
denominator is the deduplicated, non-overlapping combination of the member
collections' catchment regions resolved at the exact-year annual average.
Manual evidence and legacy generated rows without verified source linkage
are never reused or deleted.
"""

import logging

from django.db import router, transaction
from django.db.models import Q

from maps.population.models import TemporalBasis
from maps.population.services import resolve_regions_population
from maps.validation import RegionCompositionError

from .derived_values import (
    _calculation_description,
    _projection_metadata,
    convert_specific_to_total_mg,
    convert_total_to_specific,
    get_derived_value_config,
)
from .models import AggregatedCollectionPropertyValue


def _get_aggregate_value_config():
    """Aggregate derivation never uses the legacy per-collection attribute."""
    return get_derived_value_config(with_population_attribute=False)


def _aggregate_counterpart_mapping():
    cfg = _get_aggregate_value_config()
    return {
        cfg.specific_property_id: (cfg.total_property_id, cfg.total_unit_id),
        cfg.total_property_id: (cfg.specific_property_id, cfg.specific_unit_id),
    }


logger = logging.getLogger(__name__)


def _population_for_acpv(acpv, year=None):
    """Resolve the combined exact-year annual average across member catchments.

    Parallel services on the same region count once. Overlapping or
    unverifiable geography and missing inputs fail closed: stocks and legacy
    attributes of unknown basis can never silently substitute.
    """
    if not year:
        return None

    regions = []
    has_members = False
    for collection in acpv.collections.select_related("catchment__region"):
        has_members = True
        region = getattr(collection.catchment, "region", None)
        if region is None:
            return None
        regions.append(region)
    if not has_members or not regions:
        return None

    try:
        return resolve_regions_population(
            regions, year, temporal_basis=TemporalBasis.CALENDAR_YEAR_AVERAGE
        )
    except RegionCompositionError:
        logger.warning(
            "Invalid region combination for aggregate value id=%s; "
            "no population resolved.",
            acpv.pk,
        )
        return None


def _compute_counterpart_value(acpv):
    cfg = _get_aggregate_value_config()
    mapping = _aggregate_counterpart_mapping().get(acpv.property_id)
    if mapping is None:
        return None

    target_property_id, target_unit_id = mapping
    expected_unit = (
        cfg.specific_unit_id
        if acpv.property_id == cfg.specific_property_id
        else cfg.total_unit_id
    )
    if acpv.unit_id != expected_unit:
        return None
    population_result = _population_for_acpv(acpv, year=acpv.year)
    if population_result is None:
        return None
    population = population_result.value
    if not population or population <= 0:
        return None

    if acpv.property_id == cfg.specific_property_id:
        # specific → total: total_Mg = specific_kg * population / 1000
        computed = convert_specific_to_total_mg(acpv.average, population, ndigits=2)
    else:
        # total → specific: specific_kg = total_Mg * 1000 / population
        computed = convert_total_to_specific(acpv.average, population, ndigits=2)

    return target_property_id, target_unit_id, computed, population_result


def _linked_generated_qs(acpv, *, using=None):
    """Select only generated outputs explicitly bound to this source."""
    if using is None:
        using = acpv._state.db or router.db_for_write(
            AggregatedCollectionPropertyValue, instance=acpv
        )
    return AggregatedCollectionPropertyValue.objects.using(using).filter(
        is_derived=True, derived_from_id=acpv.pk
    )


def _write_locked_projection(source, *, owner, publication_status, using=None):
    """Compute and persist using a source already locked by the caller."""
    result = _compute_counterpart_value(source)
    if result is None:
        _linked_generated_qs(source, using=using).delete()
        return None, "skipped"

    target_property_id, target_unit_id, computed_avg, population = result
    metadata = _projection_metadata(
        source, owner=owner, publication_status=publication_status
    )

    derived, created = AggregatedCollectionPropertyValue.objects.using(
        using
    ).update_or_create(
        derived_from=source,
        is_derived=True,
        defaults={
            "property_id": target_property_id,
            "year": source.year,
            "name": f"derived from {source.property.name}",
            "average": computed_avg,
            "standard_deviation": None,
            "description": _calculation_description(
                source,
                population,
                from_specific=source.property_id
                == _get_aggregate_value_config().specific_property_id,
                source_key="source_acpv",
            ),
            "unit_id": target_unit_id,
            **metadata,
        },
    )
    derived.collections.set(source.collections.values_list("pk", flat=True))
    return derived, "created" if created else "updated"


def create_or_update_derived_acpv(
    acpv, *, owner=None, publication_status=None, previous_inputs=None
):
    """Maintain one output from the freshly locked raw source.

    Metadata overrides are compatibility copies, never independent
    governance. Manual evidence and unlinked legacy outputs are not cleanup
    candidates. When ``previous_inputs`` is supplied by the source save
    signal and the persisted scalar input fields are unchanged, only the
    copied lifecycle metadata on an explicitly linked output is refreshed;
    the stored number, provenance and citations are preserved without
    recomputation.
    """
    if not isinstance(acpv, AggregatedCollectionPropertyValue) or acpv.pk is None:
        return None, "skipped"

    using = acpv._state.db or router.db_for_write(
        AggregatedCollectionPropertyValue, instance=acpv
    )
    failure = None
    outcome = (None, "skipped")
    with transaction.atomic(using=using):
        source = (
            AggregatedCollectionPropertyValue.objects.using(using)
            .select_for_update(no_key=True)
            .filter(pk=acpv.pk)
            .first()
        )
        if source is None or source.is_derived:
            return None, "skipped"
        if previous_inputs is not None and tuple(
            getattr(source, field)
            for field in AggregatedCollectionPropertyValue._DERIVED_INPUT_FIELDS
        ) == tuple(
            previous_inputs[field]
            for field in AggregatedCollectionPropertyValue._DERIVED_INPUT_FIELDS
        ):
            linked = _linked_generated_qs(source, using=using).first()
            if linked is not None:
                AggregatedCollectionPropertyValue.objects.using(using).filter(
                    pk=linked.pk
                ).update(
                    **_projection_metadata(
                        source,
                        owner=owner,
                        publication_status=publication_status,
                    )
                )
                linked.refresh_from_db(using=using)
                return linked, "updated"
        try:
            with transaction.atomic(using=using):
                outcome = _write_locked_projection(
                    source,
                    owner=owner,
                    publication_status=publication_status,
                    using=using,
                )
        except Exception as exc:
            # Roll back partial output writes, then invalidate under the same
            # raw lock. Late cleanup must not delete a newer worker's output.
            _linked_generated_qs(source, using=using).delete()
            failure = exc
    if failure is not None:
        raise failure
    return outcome


def delete_derived_acpv(acpv):
    """Remove only this raw source's explicitly linked generated output."""
    if (
        not isinstance(acpv, AggregatedCollectionPropertyValue)
        or acpv.is_derived
        or acpv.pk is None
    ):
        return 0
    _, details = _linked_generated_qs(acpv).delete()
    return details.get("waste_collection.AggregatedCollectionPropertyValue", 0)


def backfill_derived_acpvs(dry_run=False, owner=None, publication_status=None):
    """Maintain explicit per-source output identities, never infer legacy links.

    Dry runs lock each source and change no records. Ineligible sources are
    skipped; a real run also removes their stale linked outputs. Counts
    describe source outcomes, not unique data keys or individual deleted
    rows.
    """
    stats = {"created": 0, "updated": 0, "skipped": 0}
    cfg = _get_aggregate_value_config()
    source_qs = (
        AggregatedCollectionPropertyValue.objects.filter(is_derived=False)
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
                    AggregatedCollectionPropertyValue.objects.select_for_update(
                        no_key=True
                    )
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
                AggregatedCollectionPropertyValue.objects.only("pk")
                .filter(pk=source_id)
                .first()
            )
            if source is None:
                action = "skipped"
            else:
                # The generator owns its lock and invalidation commit. An
                # additional outer transaction would undo cleanup on error.
                _derived, action = create_or_update_derived_acpv(
                    source, owner=owner, publication_status=publication_status
                )
        stats[action] += 1
    logger.info(
        "Aggregate backfill complete: %d created, %d updated, %d skipped",
        stats["created"],
        stats["updated"],
        stats["skipped"],
    )
    return stats
