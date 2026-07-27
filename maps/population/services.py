"""Exact-year population resolution for regions and custom compositions.

The resolver never substitutes another year or another geography level.
Missing observations stay missing: callers receive ``None`` instead of a
forward-filled, backfilled, or latest-year value.
"""

from dataclasses import dataclass
from decimal import Decimal

from django.utils import timezone

from maps.models import RegionAttributeValue
from maps.validation import validate_region_composition

from .models import (
    PopulationEstimate,
    PopulationEstimateComponent,
    PopulationObservation,
    SourceStatus,
)

METHOD_DIRECT = "direct"
METHOD_SUMMED = "summed"
METHOD_LEGACY_ATTRIBUTE = "legacy_attribute"

TEMPORAL_BASIS_MIXED = "mixed"


@dataclass(frozen=True)
class PopulationResult:
    """Provenance-bearing result of a population resolution."""

    value: Decimal
    year: int
    method: str
    temporal_basis: str | None
    datasets: tuple
    observations: tuple
    is_provisional: bool
    is_mixed_provenance: bool


def _observation_candidates(region_ids, year):
    return PopulationObservation.objects.filter(
        region_id__in=region_ids, year=year
    ).select_related("dataset")


def _best_observation_per_region(region_ids, year):
    """Pick one observation per region, preferring canonical datasets."""
    best = {}
    for observation in _observation_candidates(region_ids, year).order_by(
        "region_id", "-dataset__is_canonical", "dataset__slug"
    ):
        best.setdefault(observation.region_id, observation)
    return best


def _direct_result(observation):
    return PopulationResult(
        value=observation.value,
        year=observation.year,
        method=METHOD_DIRECT,
        temporal_basis=observation.dataset.temporal_basis,
        datasets=(observation.dataset,),
        observations=(observation,),
        is_provisional=observation.source_status != SourceStatus.FINAL,
        is_mixed_provenance=False,
    )


def _summed_result(observations, year):
    datasets = {observation.dataset for observation in observations}
    temporal_bases = {dataset.temporal_basis for dataset in datasets}
    return PopulationResult(
        value=sum((observation.value for observation in observations), Decimal("0")),
        year=year,
        method=METHOD_SUMMED,
        temporal_basis=(
            temporal_bases.pop() if len(temporal_bases) == 1 else TEMPORAL_BASIS_MIXED
        ),
        datasets=tuple(sorted(datasets, key=lambda dataset: dataset.slug)),
        observations=tuple(observations),
        is_provisional=any(
            observation.source_status != SourceStatus.FINAL
            for observation in observations
        ),
        is_mixed_provenance=len(datasets) > 1,
    )


def _legacy_exact_year_value(region_id, year, legacy_attribute_id):
    """Exact-year compatibility adapter for legacy ``RegionAttributeValue`` rows.

    Only rows dated in the requested year qualify; there is no
    latest-value fallback.
    """
    value = (
        RegionAttributeValue.objects.filter(
            region_id=region_id,
            property_id=legacy_attribute_id,
            date__year=year,
        )
        .order_by("-date")
        .values_list("value", flat=True)
        .first()
    )
    if value is None:
        return None
    return PopulationResult(
        value=Decimal(str(value)),
        year=year,
        method=METHOD_LEGACY_ATTRIBUTE,
        temporal_basis=None,
        datasets=(),
        observations=(),
        is_provisional=False,
        is_mixed_provenance=False,
    )


def resolve_composed_population(region, year):
    """Sum exact-year observations over a custom region's components.

    Raises :class:`maps.validation.RegionCompositionError` for invalid or
    overlapping compositions. Returns ``None`` when the region has no
    components or any component lacks an exact-year observation.
    """
    members = list(region.composed_of.all())
    if not members:
        return None

    validate_region_composition(members, region=region)

    best = _best_observation_per_region([member.pk for member in members], year)
    if any(member.pk not in best for member in members):
        return None

    observations = [best[member.pk] for member in members]
    return _summed_result(observations, year)


def resolve_population(region, year, *, legacy_attribute_id=None):
    """Resolve the population of ``region`` for exactly ``year``.

    Resolution order:

    1. a direct observation for the region and year (canonical datasets
       preferred),
    2. the exact-year sum over the region's ``composed_of`` components,
    3. optionally, a legacy ``RegionAttributeValue`` row dated in the
       requested year when ``legacy_attribute_id`` is provided.

    Returns ``None`` when no exact-year value exists. Never selects
    another year or geography level.
    """
    if region is None or year is None:
        return None

    observation = (
        _observation_candidates([region.pk], year)
        .order_by("-dataset__is_canonical", "dataset__slug")
        .first()
    )
    if observation is not None:
        return _direct_result(observation)

    composed = resolve_composed_population(region, year)
    if composed is not None:
        return composed

    if legacy_attribute_id is not None:
        return _legacy_exact_year_value(region.pk, year, legacy_attribute_id)

    return None


def materialize_estimate(region, year):
    """Persist the composed estimate for a custom region with its components.

    Returns the up-to-date :class:`PopulationEstimate` or ``None`` when no
    complete exact-year composition result exists.
    """
    result = resolve_composed_population(region, year)
    if result is None:
        return None

    estimate, _created = PopulationEstimate.objects.update_or_create(
        region=region,
        year=year,
        defaults={
            "value": result.value,
            "is_mixed_provenance": result.is_mixed_provenance,
            "is_provisional": result.is_provisional,
            "calculated_at": timezone.now(),
        },
    )
    estimate.component_links.all().delete()
    PopulationEstimateComponent.objects.bulk_create(
        PopulationEstimateComponent(estimate=estimate, observation=observation)
        for observation in result.observations
    )
    return estimate


def population_values_by_region(region_ids, year, *, legacy_attribute_id=None):
    """Bulk exact-year population lookup, returning ``{region_id: Decimal}``.

    Uses direct observations (canonical datasets preferred) and the
    exact-year legacy adapter. Regions without an exact-year value are
    omitted; composed regions are not aggregated here.
    """
    region_ids = list(region_ids)
    values = {
        region_id: observation.value
        for region_id, observation in _best_observation_per_region(
            region_ids, year
        ).items()
    }

    if legacy_attribute_id is not None:
        missing = [region_id for region_id in region_ids if region_id not in values]
        if missing:
            legacy_qs = (
                RegionAttributeValue.objects.filter(
                    region_id__in=missing,
                    property_id=legacy_attribute_id,
                    date__year=year,
                )
                .order_by("region_id", "-date")
                .distinct("region_id")
                .values_list("region_id", "value")
            )
            for region_id, value in legacy_qs:
                values[region_id] = Decimal(str(value))

    return values
