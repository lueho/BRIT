# Geodataset Harmonization Pipeline

**Date:** 2026-02-10
**Status:** Proposal
**Context:** Sources Explorer (Section 9 of UX Harmonization Guideline)

---

## 1. Problem Statement

Each source type (roadside trees, greenhouses, waste collection, etc.) may have multiple
spatial distribution datasets from different third-party providers covering different regions.
These datasets:

- Have **incompatible schemas** (different column names, data types, coded values)
- Use **different coordinate reference systems**
- Are published in **different formats** (WFS, Shapefile, GeoJSON, CSV, GeoPackage)
- Receive **periodic updates** (typically annual) from their providers
- Come from **different open data portals** with different access patterns

Manual harmonization does not scale. The goal is a system that:

1. Automatically pulls datasets from known sources on a schedule
2. Applies pre-configured schema mappings to harmonize column names and units
3. Loads the harmonized data into canonical target models in PostGIS
4. Tracks provenance, versioning, and data quality
5. Detects and alerts on upstream schema changes

## 2. Terminology

| Term | Definition |
|---|---|
| **Source type** | A category of bioresource-generating system (roadside trees, greenhouses, etc.) |
| **Data source** | A specific third-party dataset for a source type in a specific region (e.g., Hamburg tree registry) |
| **Schema mapping** | A configuration that translates a data source's native schema into the canonical target schema |
| **Target model** | The harmonized Django/PostGIS model for a source type with a canonical set of fields |
| **Dataset version** | A snapshot of a data source at a point in time, tied to a specific pull |
| **Connector** | A plugin that knows how to fetch data from a specific access pattern (WFS, file download, CKAN API) |

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│ DataSourceConfig (Django model)                     │
│  - source_type                                      │
│  - provider name, URL, licence                      │
│  - connector_type (WFS / file / CKAN / ...)         │
│  - column_mapping (JSONField)                       │
│  - transformations (JSONField)                      │
│  - target_crs (default: EPSG:4326)                  │
│  - schedule (cron expression)                       │
│  - region (FK to Region)                            │
│  - last_etag / last_hash / last_pull_at             │
│  - status (ok / needs_attention / disabled)          │
│  - bibliography_source (FK to Source)               │
└───────────────┬─────────────────────────────────────┘
                │ triggers periodically
                ▼
┌─────────────────────────────────────────────────────┐
│ Ingestion Pipeline                                  │
│                                                     │
│  1. EXTRACT                                         │
│     Connector.fetch(url, format) → raw GeoDataFrame │
│                                                     │
│  2. DETECT DRIFT                                    │
│     Compare source columns against expected mapping │
│     Alert if columns missing / renamed / added      │
│                                                     │
│  3. TRANSFORM                                       │
│     Apply column_mapping (rename)                   │
│     Apply transformations (unit conversion, codes)  │
│     Reproject CRS → target_crs                      │
│                                                     │
│  4. VALIDATE                                        │
│     Geometry: ST_IsValid, fix with ST_MakeValid     │
│     Spatial bounds: records within declared region   │
│     Attributes: type checks, range checks, nulls    │
│     Duplicates: same geometry + same attributes     │
│                                                     │
│  5. LOAD                                            │
│     bulk_create into target model                   │
│     Create GeoDataset version record                │
│     Link to DataSourceConfig + bibliography Source  │
│     Update last_etag / last_hash / last_pull_at     │
│                                                     │
│  6. REPORT                                          │
│     Log: records loaded, skipped, validation errors │
│     Update DataSourceConfig.status                  │
└─────────────────────────────────────────────────────┘
```

## 4. Key Design Decisions

### 4.1 One Canonical Target Model per Source Type

Each source type defines a single harmonized model with the fields the generation model
needs. Provider-specific fields that don't map to the canonical schema are either:

- Stored in an `extra_data` JSONField (if potentially useful)
- Discarded (if irrelevant to bioresource estimation)

Example for roadside trees:

```python
class RoadsideTreePoint(models.Model):
    geom = PointField(srid=4326)
    genus = CharField(max_length=100, null=True)
    species = CharField(max_length=100, null=True)
    planting_year = IntegerField(null=True)
    trunk_circumference_m = FloatField(null=True)
    crown_diameter_m = FloatField(null=True)
    height_m = FloatField(null=True)
    # provenance
    geodataset = ForeignKey(GeoDataset, on_delete=CASCADE)
    extra_data = JSONField(default=dict, blank=True)
```

Fields that a specific provider doesn't supply remain `null`. The generation model
works with whatever is available, using defaults or estimates for missing values.

### 4.2 Schema Mapping as Configuration, Not Code

Each data source's mapping is stored as JSON in `DataSourceConfig.column_mapping`:

```json
{
    "source_columns": {
        "gattung": {"target": "genus"},
        "pflanzjahr": {"target": "planting_year"},
        "kronendurchmesser": {"target": "crown_diameter_m", "transform": "value / 100"},
        "stammumfang": {"target": "trunk_circumference_m", "transform": "value / 100"}
    },
    "geometry_column": "geom",
    "source_crs": "EPSG:25832"
}
```

Adding a new data source (e.g., Berlin street trees) requires only writing this JSON
mapping and configuring the URL — no new Django model, no code changes.

### 4.3 Connectors as Plugins

Each access pattern is a connector class with a common interface:

- `WFSConnector` — OGC Web Feature Service (paginated GetFeature requests)
- `FileConnector` — HTTP download of Shapefile / GeoJSON / GeoPackage / CSV
- `CKANConnector` — CKAN data portal API (resource download with metadata)
- `ArcGISConnector` — ArcGIS REST API / Hub (FeatureServer queries)

All connectors return a GeoDataFrame. The pipeline is agnostic to the access pattern.

### 4.4 Versioning and Reproducibility

Each pipeline run creates a new `GeoDataset` record (a dataset version). Old versions
are retained so that:

- Inventories reference a specific dataset version and remain reproducible
- Users can compare versions over time (e.g., tree count trends)
- Rolling back to a previous version is trivial

A `GeoDataset` links to its `DataSourceConfig`, `Region`, bibliography `Source`,
and the actual data records via the existing `data_content_type` / `data_object_id`
GenericFK (or a direct FK on the target model).

### 4.5 Schema Drift Detection

Before applying the mapping, the pipeline checks:

1. All expected source columns exist in the fetched data
2. Column data types match expectations
3. Any new columns not in the mapping are logged

If a required column is missing → pipeline stops for this source, sets
`status = "needs_attention"`, sends a notification. This turns silent data corruption
into an explicit maintenance task.

## 5. Impact on Current Architecture

### 5.1 GeoDataset Model

The existing `GeoDataset.model_name` field (hardcoded choices) will be replaced by a
relationship to `DataSourceConfig.source_type`. The `data_content_type` GenericFK
continues to point to the target model.

### 5.2 Sources Explorer

The "Map" button on each source type card will link to the geodataset list filtered
by source type, showing all available spatial distributions with their regions,
providers, and version dates. Users pick which dataset to view on a map.

### 5.3 Inventories

The inventory scenario configuration will let users select a specific `GeoDataset`
(version) as the source distribution input. This replaces the current pattern of
hard-coding a specific map view.

### 5.4 Existing GIS Models

The existing per-dataset models (`HamburgRoadsideTrees`, `NantesGreenhouses`) will
be migrated into canonical target models per source type. This is a one-time
migration with backwards-compatible redirects for existing map URLs.

## 6. Implementation Phases

### Phase 1: Foundation (prerequisite for all other phases)

- [ ] Define canonical target models per source type (roadside trees, greenhouses)
- [ ] Create `DataSourceConfig` model with JSON schema mapping field
- [ ] Migrate existing data from per-dataset models into canonical models
- [ ] Update `GeoDataset` to reference `DataSourceConfig` instead of `model_name`
- [ ] Update Sources Explorer "Map" button to link to filtered geodataset list

### Phase 2: Pipeline Framework

- [ ] Implement base `Connector` interface and `FileConnector`
- [ ] Implement schema mapping engine (column rename + simple transforms)
- [ ] Implement validation framework (geometry, bounds, attributes)
- [ ] Implement pipeline orchestrator (management command)
- [ ] Schema drift detection and status reporting

### Phase 3: Scheduling and Monitoring

- [ ] Add Celery beat schedule (or cron-based management command)
- [ ] Dashboard or admin view for pipeline status and last-pull timestamps
- [ ] Email/notification on schema drift or pipeline failures
- [ ] Dataset version comparison (record count trends, quality metrics)

### Phase 4: Additional Connectors

- [ ] `WFSConnector` for OGC Web Feature Services
- [ ] `CKANConnector` for open data portals
- [ ] `ArcGISConnector` for ArcGIS REST/Hub sources

### Phase 5: Enrichment (future)

- [ ] Cross-source deduplication (same tree in overlapping datasets)
- [ ] Automated quality scoring per dataset
- [ ] User-contributed schema mappings (community-maintained)
- [ ] LLM-assisted initial schema mapping suggestions

## 7. Effort Estimate

| Component | Effort | Notes |
|---|---|---|
| Target models + data migration | 1–2 weeks | One-time, per source type |
| DataSourceConfig model + admin UI | 2–3 days | JSONField + Django admin |
| Pipeline framework + FileConnector | 1–2 weeks | Management command, GeoPandas-based |
| Schema mapping engine | 3–5 days | JSON-driven column rename + transforms |
| Validation framework | 2–3 days | Geometry + attribute checks |
| Drift detection + alerting | 1–2 days | Column comparison + status update |
| Versioning + provenance | 2–3 days | GeoDataset linking |
| Scheduling (Celery beat) | 1–2 days | If Celery already in stack |
| Each additional connector | 1–3 days | WFS is most complex |
| **Each new data source (after framework)** | **~1 hour** | **Write JSON mapping, configure URL** |
| **Total framework** | **~4–6 weeks** | |

## 8. Guiding Principles

1. **Configuration over code:** Adding a new data source should never require a new
   Django model or Python code — only a JSON schema mapping and a URL.

2. **Fail loudly on drift:** Never silently load data with a broken mapping. Alert and
   stop.

3. **Provenance is mandatory:** Every record traces back to a specific provider, dataset
   version, and schema mapping version.

4. **Versions are immutable:** Once a dataset version is created, it is never modified.
   New pulls create new versions.

5. **Graceful degradation:** Missing fields in a provider's data produce `null` in the
   target model, not pipeline failures. The generation model handles nulls with defaults.
