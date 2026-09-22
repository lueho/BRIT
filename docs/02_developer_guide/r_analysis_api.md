# R analysis API and BRIT-EU analysis package

`GET /waste_collection/api/collection/analysis/` adds a read-only, paginated export-oriented representation. The existing lean list endpoint is unchanged. Schema `1.0` returns `count`, `next`, `previous`, `results`, `schema_version`, `generated_at` (UTC), and `snapshot_isolation: false`.

Rows use `CollectionFlatSerializer` fields plus stable `id` and `publication_status`. Dynamic numeric metrics keep explicit adjacent unit fields. Existing collection scope, filters, and property-value visibility apply. Non-public scopes require authentication. Ordering is by primary key; pages default to 100 and are capped at 200. Responses are marked private/no-store. This is a live read, not a database snapshot.

The API is consumed by `analysis/brit_eu/R/brit_api.R`. `analysis/brit_eu/README.md` documents the end-user workflow. The historical scripts and the fixed input manifest are versioned alongside that client. Historical raw data are delivered separately in the complete release ZIP, never inferred from current database state.

Deployment requires the ordinary BRIT application release; no migration or new secret is required. Anonymous users receive published objects only. The analysis client does not upload data or publish records. A data release can be hosted separately as an immutable directory containing `data/manifest.json` and its checksum-protected `data/raw/` files.

Validation: `sources.waste_collection.tests.test_analysis_api` covers pagination, ID filtering, publication scope, owner isolation, zero-valued metrics, units, private metric exclusion and read-only behavior. R client tests run as `Rscript --vanilla tests/test_client.R` in the restored analysis environment.
