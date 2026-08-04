"""Versioned, provider-neutral contract for the NUTS vintage import API.

BRIT can hold several NUTS vintages side by side but deliberately owns no
acquisition code: fetching GISCO releases, diffing them and deciding what a
vintage contains is private ETL work (BRIT-data), running on a different host.
This payload is the seam between the two.

The JSON Schema below documents the ``1.0`` payload and is served at
``GET /maps/nuts/api/import/schema/``.
"""

SCHEMA_VERSION = "1.0"

GEOMETRY_SCHEMA = {
    "type": "object",
    "required": ["type", "coordinates"],
    "properties": {
        "type": {"enum": ["Polygon", "MultiPolygon"]},
        "coordinates": {"type": "array"},
    },
    "description": "GeoJSON geometry in EPSG:4326.",
}

NUTS_IMPORT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://brit/maps/nuts/import/v1.0",
    "title": "BRIT NUTS vintage import payload",
    "type": "object",
    "required": ["schema_version", "vintage", "regions"],
    "additionalProperties": False,
    "properties": {
        "schema_version": {"const": SCHEMA_VERSION},
        "dry_run": {
            "type": "boolean",
            "description": "When true, validate and report without persisting.",
        },
        "vintage": {
            "type": "object",
            "required": ["year"],
            "additionalProperties": False,
            "properties": {
                "year": {
                    "type": "integer",
                    "minimum": 1990,
                    "maximum": 2100,
                    "description": "NUTS release year, e.g. 2024.",
                },
                "source_release": {
                    "type": "string",
                    "description": "Upstream release, e.g. 'GISCO NUTS 2024 01M 4326'.",
                },
                "is_current": {
                    "type": "boolean",
                    "description": (
                        "Make this the vintage all user-facing queries default "
                        "to. Only one vintage is current at a time."
                    ),
                },
            },
        },
        "regions": {
            "type": "array",
            "minItems": 1,
            "description": (
                "Regions of one vintage. Send them lowest level first: a "
                "region's parent must already exist in the same vintage."
            ),
            "items": {
                "type": "object",
                "required": ["nuts_id", "levl_code", "cntr_code"],
                "additionalProperties": False,
                "properties": {
                    "nuts_id": {"type": "string", "maxLength": 5},
                    "parent_nuts_id": {
                        "type": "string",
                        "maxLength": 5,
                        "description": (
                            "The parent's code, for the rare region whose own "
                            "code does not imply it (NUTS 2016 files UKN10-"
                            "UKN16 under UKN0). Omit it and the parent is the "
                            "code minus its last character."
                        ),
                    },
                    "levl_code": {"type": "integer", "minimum": 0, "maximum": 3},
                    "cntr_code": {"type": "string", "maxLength": 2},
                    "name_latn": {"type": "string", "maxLength": 70},
                    "nuts_name": {"type": "string", "maxLength": 106},
                    "mount_type": {"type": ["integer", "null"]},
                    "urbn_type": {"type": ["integer", "null"]},
                    "coast_type": {"type": ["integer", "null"]},
                    "geometry": {**GEOMETRY_SCHEMA, "type": ["object", "null"]},
                },
            },
        },
    },
}
