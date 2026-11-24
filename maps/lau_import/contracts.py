"""Versioned, provider-neutral contract for the LAU vintage import API.

Like NUTS, BRIT can hold several LAU vintages side by side but deliberately
owns no acquisition code: fetching GISCO LAU releases, diffing them and
deciding what a vintage contains is private ETL work (BRIT-data), running on
a different host. This payload is the seam between the two.

One payload carries rows of a single LAU year, and a producer may split a
year across several requests — so a payload never implies deletions for rows
absent from it. Each row names its NUTS-3 parent inside a declared NUTS
vintage (``vintage.nuts_year``), which must already exist.

The JSON Schema below documents the ``1.0`` payload and is served at
``GET /lau/api/import/schema/``.

Within ``1.0``, ``geometry`` may be omitted or null on rows BRIT already
holds — the stored borders are kept — but it is required for a row BRIT does
not hold yet. A new row without a geometry is a row-level error that rolls
back the whole batch.

Versioning policy: ``SCHEMA_VERSION`` is a compatibility marker, not a
changelog. Adding an optional field stays within the current version, because
every payload that was valid before remains valid. Renaming or removing a
field, making one required, or changing a field's type or meaning bumps the
version, and BRIT-data producers are updated in the same release.
"""

SCHEMA_VERSION = "1.0"

GEOMETRY_SCHEMA = {
    "type": "object",
    "required": ["type", "coordinates"],
    "properties": {
        "type": {"enum": ["Polygon", "MultiPolygon"]},
        "coordinates": {"type": "array"},
    },
    "description": (
        "GeoJSON geometry in EPSG:4326. Required when a row is created; "
        "omit it on updates to keep the borders BRIT already holds."
    ),
}

LAU_IMPORT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://brit/maps/lau/import/v1.0",
    "title": "BRIT LAU vintage import payload",
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
            "required": ["year", "nuts_year"],
            "additionalProperties": False,
            "properties": {
                "year": {
                    "type": "integer",
                    "minimum": 1990,
                    "maximum": 2100,
                    "description": "LAU release year, e.g. 2018.",
                },
                "nuts_year": {
                    "type": "integer",
                    "minimum": 1990,
                    "maximum": 2100,
                    "description": (
                        "Year of the NUTS vintage the rows' nuts_parent_id "
                        "values resolve against, e.g. 2016."
                    ),
                },
            },
        },
        "regions": {
            "type": "array",
            "minItems": 1,
            "description": (
                "LAU rows of one year. A payload is one batch of a year, so "
                "rows absent from it are left untouched."
            ),
            "items": {
                "type": "object",
                "required": ["cntr_code", "lau_id", "nuts_parent_id"],
                "additionalProperties": False,
                "properties": {
                    "cntr_code": {"type": "string", "maxLength": 2},
                    "lau_id": {"type": "string", "maxLength": 13},
                    "lau_name": {"type": "string", "maxLength": 113},
                    "name_en": {
                        "type": "string",
                        "maxLength": 113,
                        "description": (
                            "English display name where one is known. The "
                            "source-language name remains the fallback."
                        ),
                    },
                    "nuts_parent_id": {
                        "type": ["string", "null"],
                        "maxLength": 5,
                        "description": (
                            "NUTS-3 region of the declared NUTS vintage this "
                            "LAU belongs to, or null where none applies."
                        ),
                    },
                    "geometry": {**GEOMETRY_SCHEMA, "type": ["object", "null"]},
                },
            },
        },
    },
}
