"""Controlled vocabulary helpers for Soilcom waste collection models."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Final

from case_studies.soilcom.crosswalk import (
    get_crosswalk_equivalences,
    get_ttl_concept_registry,
)
from case_studies.soilcom.models import (
    AggregatedCollectionPropertyValue,
    Collection,
    CollectionFrequency,
    CollectionPropertyValue,
    CollectionSystem,
    FeeSystem,
    SortingMethod,
    WasteCategory,
)

VOCABULARY_VERSION: Final[str] = "0.4.0"
VOCABULARY_URI_BASE: Final[str] = "https://brit.bioresource-tools.net/vocab/soilcom"

CONCEPT_SCHEME_URIS: Final[dict[str, str]] = {
    "waste_categories": f"{VOCABULARY_URI_BASE}/scheme/waste-category",
    "collection_systems": f"{VOCABULARY_URI_BASE}/scheme/collection-system",
    "collection_frequencies": f"{VOCABULARY_URI_BASE}/scheme/collection-frequency",
    "sorting_methods": f"{VOCABULARY_URI_BASE}/scheme/sorting-method",
    "fee_systems": f"{VOCABULARY_URI_BASE}/scheme/fee-system",
    "collection_properties": f"{VOCABULARY_URI_BASE}/scheme/collection-property",
    "materials": f"{VOCABULARY_URI_BASE}/scheme/material",
    "units": f"{VOCABULARY_URI_BASE}/scheme/unit",
    "material_roles": f"{VOCABULARY_URI_BASE}/scheme/material-role",
    "connection_types": f"{VOCABULARY_URI_BASE}/scheme/connection-type",
    "required_bin_capacity_references": (
        f"{VOCABULARY_URI_BASE}/scheme/required-bin-capacity-reference"
    ),
    "country_languages": f"{VOCABULARY_URI_BASE}/scheme/country-language",
}

SEMANTIC_CONTRACT: Final[dict[str, object]] = {
    "canonical_identifier_field": "target_concept_uri",
    "equivalence_source_key": "crosswalk_equivalences",
    "concept_lifecycle_statuses": [
        "active",
        "deprecated",
        "superseded",
    ],
    "change_types": [
        "new_concept",
        "label_only",
        "deprecate",
        "semantic_split",
        "semantic_merge",
    ],
    "equivalence_policy": {
        "lexical_equivalents_share_concept_uri": True,
        "crosswalk_rows_must_reference_existing_concept_uri": True,
        "agent_matching_must_use_concept_uri": True,
    },
}

# ISO 639-1 language codes per country code used in maps_region.country.
COUNTRY_LANGUAGE_BY_ISO: Final[dict[str, tuple[str, ...]]] = {
    "BE": ("nl", "fr", "de"),
    "DE": ("de",),
    "DK": ("da",),
    "NL": ("nl",),
    "SE": ("sv",),
    "UK": ("en",),
}


def map_country_codes_to_languages(
    country_codes: Iterable[str],
) -> dict[str, tuple[str, ...]]:
    """Map country codes to controlled language lists.

    Args:
        country_codes: Iterable of country codes from ``maps_region.country``.

    Returns:
        Dict keyed by normalized country code. Values are tuples of ISO 639-1
        language codes. Unknown country codes are ignored.
    """
    languages_by_country: dict[str, tuple[str, ...]] = {}
    for code in country_codes:
        normalized = (code or "").strip().upper()
        if not normalized or normalized in languages_by_country:
            continue
        languages = COUNTRY_LANGUAGE_BY_ISO.get(normalized)
        if languages:
            languages_by_country[normalized] = languages
    return languages_by_country


def get_country_languages_for_collection_data() -> dict[str, tuple[str, ...]]:
    """Return languages for countries that already have collection records.

    The country list is derived dynamically from existing ``Collection`` rows.
    """
    country_codes = (
        Collection.objects.exclude(catchment__region__country__isnull=True)
        .exclude(catchment__region__country="")
        .values_list("catchment__region__country", flat=True)
        .distinct()
        .order_by("catchment__region__country")
    )
    return map_country_codes_to_languages(country_codes)


def get_unmapped_collection_country_codes() -> list[str]:
    """Return country codes present in collection data but missing language mapping."""
    country_codes = (
        Collection.objects.exclude(catchment__region__country__isnull=True)
        .exclude(catchment__region__country="")
        .values_list("catchment__region__country", flat=True)
        .distinct()
        .order_by("catchment__region__country")
    )
    unknown = {
        (code or "").strip().upper()
        for code in country_codes
        if (code or "").strip().upper() not in COUNTRY_LANGUAGE_BY_ISO
    }
    return sorted(code for code in unknown if code)


def get_collection_property_names_for_collection_data() -> list[str]:
    """Return collection property names currently used by collection values."""
    direct_names = set(
        CollectionPropertyValue.objects.exclude(property__name__isnull=True)
        .exclude(property__name="")
        .values_list("property__name", flat=True)
    )
    aggregated_names = set(
        AggregatedCollectionPropertyValue.objects.exclude(property__name__isnull=True)
        .exclude(property__name="")
        .values_list("property__name", flat=True)
    )
    return sorted(direct_names | aggregated_names)


def get_collection_frequency_names_for_collection_data() -> list[str]:
    """Return collection frequency names currently available for collection imports."""
    return list(
        CollectionFrequency.objects.order_by("name").values_list("name", flat=True)
    )


def get_material_names_for_collection_data() -> list[str]:
    """Return material names currently used in collection material constraints."""
    allowed = set(
        Collection.objects.exclude(allowed_materials__name__isnull=True)
        .exclude(allowed_materials__name="")
        .values_list("allowed_materials__name", flat=True)
    )
    forbidden = set(
        Collection.objects.exclude(forbidden_materials__name__isnull=True)
        .exclude(forbidden_materials__name="")
        .values_list("forbidden_materials__name", flat=True)
    )
    return sorted(allowed | forbidden)


def get_collection_unit_names_for_collection_data() -> list[str]:
    """Return unit names currently used by collection values."""
    direct_units = set(
        CollectionPropertyValue.objects.exclude(unit__name__isnull=True)
        .exclude(unit__name="")
        .values_list("unit__name", flat=True)
    )
    aggregated_units = set(
        AggregatedCollectionPropertyValue.objects.exclude(unit__name__isnull=True)
        .exclude(unit__name="")
        .values_list("unit__name", flat=True)
    )
    return sorted(direct_units | aggregated_units)


def get_concepts_by_uri(
    vocabulary_ttl_path: Path | None = None,
) -> dict[str, dict[str, str | None]]:
    """Return authoritative Soilcom concepts keyed by canonical URI.

    Args:
        vocabulary_ttl_path: Optional alternate Turtle vocabulary path.

    Returns:
        Dict keyed by canonical concept URI. Each value contains the concept's
        scheme URI plus canonical label metadata parsed from the authoritative
        Soilcom SKOS vocabulary.
    """
    return get_ttl_concept_registry(
        vocabulary_ttl_path=vocabulary_ttl_path,
        uri_base=VOCABULARY_URI_BASE,
    )


def get_waste_collection_controlled_vocabulary() -> dict[str, object]:
    """Build a controlled-vocabulary snapshot for waste collection models."""
    return {
        "version": VOCABULARY_VERSION,
        "uri_base": VOCABULARY_URI_BASE,
        "semantic_contract": SEMANTIC_CONTRACT,
        "concept_schemes": CONCEPT_SCHEME_URIS,
        "concepts_by_uri": get_concepts_by_uri(),
        "waste_categories": list(
            WasteCategory.objects.order_by("name").values_list("name", flat=True)
        ),
        "collection_systems": list(
            CollectionSystem.objects.order_by("name").values_list("name", flat=True)
        ),
        "collection_frequencies": get_collection_frequency_names_for_collection_data(),
        "sorting_methods": list(
            SortingMethod.objects.order_by("name").values_list("name", flat=True)
        ),
        "fee_systems": list(
            FeeSystem.objects.order_by("name").values_list("name", flat=True)
        ),
        "collection_properties": get_collection_property_names_for_collection_data(),
        "materials": get_material_names_for_collection_data(),
        "units": get_collection_unit_names_for_collection_data(),
        "material_roles": ["allowed", "forbidden"],
        "connection_types": [
            {"value": value, "label": label}
            for value, label in Collection._meta.get_field("connection_type").choices
        ],
        "required_bin_capacity_references": [
            {"value": value, "label": label}
            for value, label in Collection._meta.get_field(
                "required_bin_capacity_reference"
            ).choices
        ],
        "crosswalk_equivalences": get_crosswalk_equivalences(),
        "country_languages": get_country_languages_for_collection_data(),
        "unmapped_countries": get_unmapped_collection_country_codes(),
    }
