"""Crosswalk helpers for harmonizing raw import terms to controlled vocabulary labels."""

from __future__ import annotations

import csv
import re
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path
from typing import Final

CONTROLLED_STRING_FIELDS: Final[dict[str, str]] = {
    "collection_system": "collection_systems",
    "frequency": "collection_frequencies",
    "waste_category": "waste_categories",
    "sorting_method": "sorting_methods",
    "fee_system": "fee_systems",
}

CONTROLLED_MULTI_VALUE_FIELDS: Final[dict[str, str]] = {
    "allowed_materials": "materials",
    "forbidden_materials": "materials",
}

MAPPINGS_DIR: Final[Path] = Path(__file__).resolve().parent / "ontology" / "mappings"
VOCABULARY_TTL_PATH: Final[Path] = (
    Path(__file__).resolve().parent / "ontology" / "vocabulary.ttl"
)

_CSV_DOMAIN_FIELD: Final[str] = "domain"
_CSV_SOURCE_TERM_FIELD: Final[str] = "source_term"
_CSV_SOURCE_LANGUAGE_FIELD: Final[str] = "source_language"
_CSV_TARGET_SCHEME_URI_FIELD: Final[str] = "target_scheme_uri"
_CSV_TARGET_CONCEPT_URI_FIELD: Final[str] = "target_concept_uri"
_CSV_TARGET_LABEL_FIELD: Final[str] = "target_label"

DOMAIN_FIELD_MAP: Final[dict[str, str]] = {
    "collection_system": "collection_system",
    "frequency": "frequency",
    "waste_category": "waste_category",
    "sorting_method": "sorting_method",
    "fee_system": "fee_system",
    "connection_type": "connection_type",
    "required_bin_capacity_reference": "required_bin_capacity_reference",
}

DOMAIN_SNAPSHOT_KEY_MAP: Final[dict[str, str]] = {
    "collection_system": "collection_systems",
    "frequency": "collection_frequencies",
    "waste_category": "waste_categories",
    "sorting_method": "sorting_methods",
    "fee_system": "fee_systems",
    "connection_type": "connection_types",
    "required_bin_capacity_reference": "required_bin_capacity_references",
}

_CONNECTION_TYPE_IMPORT_ALIASES: Final[set[str]] = {
    "mandatory",
    "mandatory with exception",
    "mandatory with exception for home composters",
    "voluntary",
    "not specified",
    "not_specified",
}

_CONNECTION_TYPE_IMPORT_EQUIVALENTS: Final[dict[str, set[str]]] = {
    "mandatory": {"mandatory"},
    "voluntary": {"voluntary"},
    "mandatory with exception": {
        "mandatory with exception for home composters",
        "mandatory_with_home_composter_exception",
    },
    "mandatory with exception for home composters": {
        "mandatory with exception for home composters",
        "mandatory_with_home_composter_exception",
    },
    "not specified": {"not specified", "not_specified"},
    "not_specified": {"not specified", "not_specified"},
}

_REQUIRED_BIN_CAPACITY_REFERENCE_IMPORT_ALIASES: Final[dict[str, str]] = {
    "per person": "person",
    "person": "person",
    "persons": "person",
    "inh.": "person",
    "inh": "person",
    "inhabitant": "person",
    "inhabitants": "person",
    "inh. & month": "person",
    "inh & month": "person",
    "per household": "household",
    "household": "household",
    "households": "household",
    "per property": "property",
    "property": "property",
    "properties": "property",
    "non": "not_specified",
    "not specified": "not_specified",
    "not_specified": "not_specified",
}


def _normalize_required_bin_capacity_reference(value: str) -> str | None:
    """Return importer-equivalent canonical reference value when possible."""
    normalized = value.strip().lower()
    if not normalized:
        return None
    mapped = _REQUIRED_BIN_CAPACITY_REFERENCE_IMPORT_ALIASES.get(normalized)
    if mapped:
        return mapped
    if "person" in normalized:
        return "person"
    if re.search(r"\binh(?:abitant)?s?\.?\b", normalized):
        return "person"
    if "household" in normalized:
        return "household"
    if "propert" in normalized:
        return "property"
    return None


def _normalize_connection_type_candidates(value: str) -> set[str]:
    """Return normalized connection-type candidates for importer aliases."""
    normalized = _normalize_term(value)
    return _CONNECTION_TYPE_IMPORT_EQUIVALENTS.get(normalized, {normalized})


class CrosswalkValidationError(ValueError):
    """Raised when Soilcom crosswalk assets violate URI integrity rules."""

    def __init__(self, errors: Sequence[str] | str):
        if isinstance(errors, str):
            normalized_errors = [errors]
        else:
            normalized_errors = list(errors)

        self.errors = normalized_errors
        detail = "; ".join(normalized_errors[:3])
        if len(normalized_errors) > 3:
            detail = f"{detail}; ..."
        super().__init__(f"Soilcom crosswalk validation failed: {detail}")


def _normalize_term(value: str) -> str:
    """Return normalized lookup key for a raw source term."""
    return value.strip().casefold()


def _iter_crosswalk_rows(
    mappings_dir: Path | None = None,
) -> list[tuple[Path, int, dict[str, str]]]:
    """Return all crosswalk rows with source file and CSV line number."""
    rows: list[tuple[Path, int, dict[str, str]]] = []
    base_dir = mappings_dir or MAPPINGS_DIR
    if not base_dir.exists():
        return rows

    for csv_file in sorted(base_dir.glob("*.csv")):
        with csv_file.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for line_number, row in enumerate(reader, start=2):
                rows.append((csv_file, line_number, row))

    return rows


def _expand_ttl_identifier(value: str, uri_base: str) -> str:
    """Expand a compact Turtle identifier to a full URI."""
    compact = value.strip().rstrip(";.").strip()
    if compact.startswith("<") and compact.endswith(">"):
        return compact[1:-1]
    if compact.startswith("britvoc:"):
        return f"{uri_base}/{compact.removeprefix('britvoc:')}"
    return compact


@lru_cache(maxsize=4)
def _load_ttl_concept_registry(
    vocabulary_ttl_path: str,
    uri_base: str,
) -> dict[str, dict[str, str | None]]:
    """Parse the Soilcom SKOS Turtle file into a concept registry."""
    registry: dict[str, dict[str, str | None]] = {}
    current_uri: str | None = None
    current_scheme_uri: str | None = None
    current_notation: str | None = None
    current_pref_labels: list[tuple[str | None, str]] = []

    for raw_line in Path(vocabulary_ttl_path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("@prefix"):
            continue

        if line.startswith("britvoc:concept/") and " a skos:Concept" in line:
            current_uri = _expand_ttl_identifier(line.split()[0], uri_base)
            current_scheme_uri = None
            current_notation = None
            current_pref_labels = []
            continue

        if current_uri is None:
            continue

        if line.startswith("skos:inScheme "):
            current_scheme_uri = _expand_ttl_identifier(
                line.removeprefix("skos:inScheme "),
                uri_base,
            )
        elif line.startswith("skos:prefLabel "):
            literal_match = re.search(
                r'"(?P<label>[^"]+)"(?:@(?P<lang>[a-zA-Z-]+)|\^\^[^ ;.]+)?',
                line,
            )
            if literal_match:
                current_pref_labels.append(
                    (
                        literal_match.group("lang"),
                        literal_match.group("label"),
                    )
                )
        elif line.startswith("skos:notation "):
            literal_match = re.search(r'"(?P<notation>[^"]+)"', line)
            if literal_match:
                current_notation = literal_match.group("notation")

        if line.endswith("."):
            label = next(
                (
                    label_value
                    for lang, label_value in current_pref_labels
                    if (lang or "").lower() == "en"
                ),
                current_pref_labels[0][1] if current_pref_labels else None,
            )
            registry[current_uri] = {
                "scheme_uri": current_scheme_uri,
                "label": label,
                "notation": current_notation,
            }
            current_uri = None
            current_scheme_uri = None
            current_notation = None
            current_pref_labels = []

    return registry


def get_ttl_concept_registry(
    vocabulary_ttl_path: Path | None = None,
    uri_base: str = "https://brit.bioresource-tools.net/vocab/soilcom",
) -> dict[str, dict[str, str | None]]:
    """Return canonical concept metadata parsed from Soilcom Turtle vocabulary."""
    ttl_path = (vocabulary_ttl_path or VOCABULARY_TTL_PATH).resolve()
    return _load_ttl_concept_registry(str(ttl_path), uri_base)


def _expected_target_label_for_domain(
    domain: str,
    concept_entry: dict[str, str | None],
) -> str | None:
    """Return the canonical target string expected in crosswalk rows."""
    if domain == "required_bin_capacity_reference":
        return concept_entry.get("notation") or concept_entry.get("label")
    return concept_entry.get("label")


def validate_crosswalk_mappings(
    vocabulary_snapshot: dict | None = None,
    mappings_dir: Path | None = None,
    vocabulary_ttl_path: Path | None = None,
) -> list[str]:
    """Return URI integrity errors for Soilcom crosswalk CSV files."""
    if vocabulary_snapshot is None:
        from sources.waste_collection.vocabulary import (
            get_waste_collection_controlled_vocabulary,
        )

        vocabulary_snapshot = get_waste_collection_controlled_vocabulary()

    concept_schemes = vocabulary_snapshot.get("concept_schemes") or {}
    concept_registry = vocabulary_snapshot.get("concepts_by_uri") or {}
    if not concept_registry:
        concept_registry = get_ttl_concept_registry(
            vocabulary_ttl_path=vocabulary_ttl_path,
            uri_base=str(vocabulary_snapshot.get("uri_base") or "").rstrip("/"),
        )
    errors: list[str] = []
    seen_sources: dict[tuple[str, str], dict[str, object]] = {}

    for csv_file, line_number, row in _iter_crosswalk_rows(mappings_dir):
        domain = (row.get(_CSV_DOMAIN_FIELD) or "").strip()
        source_term = (row.get(_CSV_SOURCE_TERM_FIELD) or "").strip()
        target_scheme_uri = (row.get(_CSV_TARGET_SCHEME_URI_FIELD) or "").strip()
        target_concept_uri = (row.get(_CSV_TARGET_CONCEPT_URI_FIELD) or "").strip()
        target_label = (row.get(_CSV_TARGET_LABEL_FIELD) or "").strip()

        if not domain:
            errors.append(f"{csv_file.name}:{line_number}: Missing 'domain'.")
            continue
        if not source_term:
            errors.append(f"{csv_file.name}:{line_number}: Missing 'source_term'.")
            continue
        if not target_scheme_uri:
            errors.append(
                f"{csv_file.name}:{line_number}: Missing 'target_scheme_uri'."
            )
            continue
        if not target_concept_uri:
            errors.append(
                f"{csv_file.name}:{line_number}: Missing 'target_concept_uri'."
            )
            continue
        if not target_label:
            errors.append(f"{csv_file.name}:{line_number}: Missing 'target_label'.")
            continue

        snapshot_key = DOMAIN_SNAPSHOT_KEY_MAP.get(domain)
        if snapshot_key is None:
            errors.append(
                f"{csv_file.name}:{line_number}: Unknown crosswalk domain '{domain}'."
            )
            continue

        expected_scheme_uri = concept_schemes.get(snapshot_key)
        if target_scheme_uri != expected_scheme_uri:
            errors.append(
                f"{csv_file.name}:{line_number}: Domain '{domain}' must target scheme "
                f"'{expected_scheme_uri}', not '{target_scheme_uri}'."
            )

        concept_entry = concept_registry.get(target_concept_uri)
        if concept_entry is None:
            errors.append(
                f"{csv_file.name}:{line_number}: Unknown target_concept_uri "
                f"'{target_concept_uri}'."
            )
            continue

        concept_scheme_uri = concept_entry.get("scheme_uri")
        if concept_scheme_uri != expected_scheme_uri:
            errors.append(
                f"{csv_file.name}:{line_number}: Concept URI '{target_concept_uri}' belongs "
                f"to scheme '{concept_scheme_uri}', expected '{expected_scheme_uri}'."
            )

        if target_scheme_uri != concept_scheme_uri:
            errors.append(
                f"{csv_file.name}:{line_number}: target_scheme_uri '{target_scheme_uri}' "
                f"does not match concept scheme '{concept_scheme_uri}'."
            )

        expected_target_label = _expected_target_label_for_domain(domain, concept_entry)
        if expected_target_label and target_label != expected_target_label:
            errors.append(
                f"{csv_file.name}:{line_number}: target_label '{target_label}' must "
                f"match canonical value '{expected_target_label}' for '{target_concept_uri}'."
            )

        source_key = (domain, _normalize_term(source_term))
        current_mapping = {
            "scheme_uri": target_scheme_uri,
            "concept_uri": target_concept_uri,
            "target_label": target_label,
            "file": csv_file.name,
            "line": line_number,
        }
        seen_mapping = seen_sources.get(source_key)
        if seen_mapping and any(
            seen_mapping[field] != current_mapping[field]
            for field in ("scheme_uri", "concept_uri", "target_label")
        ):
            errors.append(
                f"{csv_file.name}:{line_number}: Conflicting mapping for domain '{domain}' "
                f"and source_term '{source_term}' (previously defined at "
                f"{seen_mapping['file']}:{seen_mapping['line']})."
            )
        else:
            seen_sources[source_key] = current_mapping

    return errors


def ensure_crosswalk_mappings_valid(
    vocabulary_snapshot: dict | None = None,
    mappings_dir: Path | None = None,
    vocabulary_ttl_path: Path | None = None,
) -> None:
    """Raise when Soilcom crosswalk mappings violate URI integrity rules."""
    errors = validate_crosswalk_mappings(
        vocabulary_snapshot=vocabulary_snapshot,
        mappings_dir=mappings_dir,
        vocabulary_ttl_path=vocabulary_ttl_path,
    )
    if errors:
        raise CrosswalkValidationError(errors)


@lru_cache(maxsize=1)
def _load_crosswalk_map() -> dict[tuple[str, str], str]:
    """Load all crosswalk CSVs into a (domain, source_term) lookup map."""
    mapping: dict[tuple[str, str], str] = {}
    for _, _, row in _iter_crosswalk_rows():
        domain = (row.get(_CSV_DOMAIN_FIELD) or "").strip()
        source = (row.get(_CSV_SOURCE_TERM_FIELD) or "").strip()
        target = (row.get(_CSV_TARGET_LABEL_FIELD) or "").strip()
        if not domain or not source or not target:
            continue
        mapping[(domain, _normalize_term(source))] = target

    return mapping


def apply_crosswalks_to_record(record: dict) -> dict:
    """Return a copy of *record* with known crosswalk mappings applied.

    Args:
        record: Raw import record (serializer-validated dict).

    Returns:
        Copy of the record where known domain values are normalized to the
        canonical controlled-vocabulary label.
    """
    mapped_record = record.copy()
    mapping = _load_crosswalk_map()

    for domain, field_name in DOMAIN_FIELD_MAP.items():
        raw_value = mapped_record.get(field_name)
        if not isinstance(raw_value, str):
            continue

        source = raw_value.strip()
        if not source:
            continue

        target = mapping.get((domain, _normalize_term(source)))
        if target:
            mapped_record[field_name] = target

    return mapped_record


def validate_record_against_controlled_vocabulary(
    record: dict,
    vocabulary_snapshot: dict,
) -> list[str]:
    """Return warnings for record values not covered by controlled vocabulary.

    The function is intentionally non-blocking so importer workflows can keep
    collecting diagnostics while preserving current record-level skip behavior.
    """
    warnings: list[str] = []

    for record_field, snapshot_key in CONTROLLED_STRING_FIELDS.items():
        value = record.get(record_field)
        if not isinstance(value, str) or not value.strip():
            continue

        allowed = set(vocabulary_snapshot.get(snapshot_key) or [])
        if value not in allowed:
            warnings.append(
                f"Field '{record_field}' has non-controlled value '{value}'."
            )

    for record_field, snapshot_key in CONTROLLED_MULTI_VALUE_FIELDS.items():
        values = record.get(record_field)
        if not isinstance(values, list):
            continue

        allowed = set(vocabulary_snapshot.get(snapshot_key) or [])
        for value in values:
            if not isinstance(value, str) or not value.strip():
                continue
            if value not in allowed:
                warnings.append(
                    f"Field '{record_field}' has non-controlled value '{value}'."
                )

    connection_value = record.get("connection_type")
    if isinstance(connection_value, str) and connection_value.strip():
        allowed_connection_values = {
            _normalize_term(str(candidate))
            for entry in vocabulary_snapshot.get("connection_types") or []
            if isinstance(entry, dict)
            for candidate in (entry.get("label"), entry.get("value"))
            if candidate
        }
        candidate_values = _normalize_connection_type_candidates(connection_value)
        if candidate_values.isdisjoint(allowed_connection_values):
            warnings.append(
                "Field 'connection_type' has non-controlled value "
                f"'{connection_value}'."
            )

    ref_value = record.get("required_bin_capacity_reference")
    if isinstance(ref_value, str) and ref_value.strip():
        allowed_ref_values = {
            entry.get("value")
            for entry in vocabulary_snapshot.get("required_bin_capacity_references")
            or []
            if isinstance(entry, dict) and entry.get("value")
        }
        normalized_ref_value = _normalize_required_bin_capacity_reference(ref_value)
        if ref_value not in allowed_ref_values and (
            normalized_ref_value not in allowed_ref_values
        ):
            warnings.append(
                "Field 'required_bin_capacity_reference' has non-controlled value "
                f"'{ref_value}'."
            )

    return warnings


@lru_cache(maxsize=1)
def get_crosswalk_equivalences() -> dict[str, dict[str, dict[str, object]]]:
    """Return crosswalk equivalence groups keyed by domain and concept URI.

    The structure is intended for machine agents that need a stable source of
    truth for equivalent source terms across languages and spellings.
    """
    equivalences: dict[str, dict[str, dict[str, object]]] = {}
    if not MAPPINGS_DIR.exists():
        return equivalences

    seen_terms: dict[tuple[str, str], set[tuple[str, str]]] = {}

    for csv_file in sorted(MAPPINGS_DIR.glob("*.csv")):
        with csv_file.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                domain = (row.get(_CSV_DOMAIN_FIELD) or "").strip()
                source_term = (row.get(_CSV_SOURCE_TERM_FIELD) or "").strip()
                source_language = (row.get(_CSV_SOURCE_LANGUAGE_FIELD) or "").strip()
                concept_uri = (row.get(_CSV_TARGET_CONCEPT_URI_FIELD) or "").strip()
                target_label = (row.get(_CSV_TARGET_LABEL_FIELD) or "").strip()

                if not domain or not source_term or not concept_uri or not target_label:
                    continue

                concept_map = equivalences.setdefault(domain, {})
                concept_entry = concept_map.setdefault(
                    concept_uri,
                    {
                        "target_label": target_label,
                        "source_terms": [],
                    },
                )

                term_key = (source_language, source_term)
                seen_key = (domain, concept_uri)
                concept_seen_terms = seen_terms.setdefault(seen_key, set())
                if term_key in concept_seen_terms:
                    continue

                concept_entry["source_terms"].append(
                    {
                        "term": source_term,
                        "language": source_language,
                    }
                )
                concept_seen_terms.add(term_key)

    for concept_map in equivalences.values():
        for concept_entry in concept_map.values():
            concept_entry["source_terms"].sort(
                key=lambda term: (term.get("language") or "", term.get("term") or ""),
            )

    return equivalences
