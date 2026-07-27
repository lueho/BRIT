"""Versioned, provider-neutral contract for the population bulk-import API.

The import API is the clean architectural seam between public BRIT and any
private ETL (e.g. BRIT-data): providers acquire, match and normalize data
privately, then write observations through this stable payload contract.
BRIT never depends on provider-specific code.

The JSON Schema below documents the ``1.0`` payload. It is also served at
``GET /population/api/import/schema/`` so external ingestion pipelines can
validate against it.
"""

SCHEMA_VERSION = "1.0"

SUPPORTED_INDICATORS = ("population",)

# Accepted upstream units mapped to the multiplier that converts them to
# persons. Values are stored in persons using Decimal arithmetic.
UNIT_TO_PERSONS = {
    "persons": 1,
    "person": 1,
    "thousands": 1000,
    "ths": 1000,
}

POPULATION_IMPORT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://brit/population/import/v1.0",
    "title": "BRIT population bulk-import payload",
    "type": "object",
    "required": ["schema_version", "dataset", "observations"],
    "additionalProperties": False,
    "properties": {
        "schema_version": {"const": SCHEMA_VERSION},
        "dry_run": {
            "type": "boolean",
            "description": "When true, validate and report without persisting.",
        },
        "extracted_at": {"type": "string", "format": "date-time"},
        "upstream_updated_at": {"type": "string", "format": "date-time"},
        "checksum": {"type": "string"},
        "dataset": {
            "type": "object",
            "required": [
                "slug",
                "name",
                "provider",
                "geographic_scope",
                "temporal_basis",
            ],
            "additionalProperties": False,
            "properties": {
                "slug": {"type": "string", "description": "Stable dataset identifier."},
                "name": {"type": "string"},
                "provider": {"type": "string", "description": "e.g. 'eurostat'."},
                "external_id": {
                    "type": "string",
                    "description": "Upstream dataset code, e.g. 'nama_10r_3popgdp'.",
                },
                "release": {
                    "type": "string",
                    "description": "Provider release/version, e.g. '2026-02'.",
                },
                "geographic_scope": {"enum": ["nuts", "lau"]},
                "temporal_basis": {"enum": ["calendar_year_average", "point_in_time"]},
                "source_unit": {"type": "string"},
                "classification_version": {"type": "string"},
                "is_canonical": {"type": "boolean"},
            },
        },
        "observations": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": [
                    "region_scheme",
                    "region_code",
                    "indicator",
                    "reference_period",
                    "value",
                    "unit",
                ],
                "additionalProperties": False,
                "properties": {
                    "region_scheme": {"enum": ["NUTS", "LAU"]},
                    "region_code": {"type": "string"},
                    "region_version": {"type": "string"},
                    "indicator": {"enum": list(SUPPORTED_INDICATORS)},
                    "reference_period": {
                        "type": ["integer", "string"],
                        "description": "Reference year.",
                    },
                    "value": {"type": ["number", "string"]},
                    "unit": {"enum": sorted(UNIT_TO_PERSONS)},
                    "source_status": {"enum": ["final", "provisional", "estimated"]},
                    "flags": {"type": "string"},
                },
            },
        },
    },
}
