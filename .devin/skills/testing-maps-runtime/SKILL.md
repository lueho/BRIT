---
name: testing-maps-runtime
description: Test BRIT source-mounted map routes and runtime GeoDataset map routes end-to-end.
---

# Testing BRIT Maps Runtime Routes

Use this when verifying changes around `maps.registry`, source map mounts, source-domain runtime compatibility, map URLs, or GeoDataset runtime map rendering.

## Devin Secrets Needed

- None for local Docker/Compose map-route testing.

## Setup

1. Use the isolated BRIT worktree and Compose project:
   - `/home/ubuntu/repos/BRIT`
   - `/home/ubuntu/BRIT-ops/scripts/brit-worktree-compose /home/ubuntu/repos/BRIT ...`
2. Run app-dependent setup inside Docker, not host Python.
3. Seed complete map configuration before browser testing:
   - call `maps.utils.ensure_initial_data()`
   - assign test `GeoDataset` rows to `Default Map Configuration`
   - avoid sparse one-layer `MapConfiguration` fixtures for browser tests, because the map JS expects coherent layer config.
4. For source-mounted map views without a `pk`, create a legacy `GeoDataset` with `model_name` matching the source view's runtime model name (for example `HamburgRoadsideTrees`).
5. For runtime GeoDataset views, create:
   - a published `GeoDataset`
   - a `GeoDatasetRuntimeConfiguration(backend_type="django_model", runtime_model_name=...)`
   - at least two synthetic source model records with valid geometries, so the map bounds are readable and do not zoom to a single 2m-scale point.

## Runtime UI Test Pattern

1. Open the source-mounted `/maps/.../map/` route in the browser.
   - Assert the expected source map title/header renders.
   - Assert no Django error page is shown.
   - Assert the page HTML contains the expected source GeoJSON URL.
2. Open the runtime GeoDataset `/maps/geodatasets/<pk>/map/` route in the browser.
   - Assert the dataset name renders as the map header/title.
   - Assert `Table` and `Map` controls render.
   - Assert no Django error page is shown.
   - Assert the page HTML contains the expected GeoJSON URL from source runtime compatibility.
3. Run a Docker shell sanity check for registry-backed contracts when testing registry changes:
   - `get_source_domain_map_mounts()`
   - `get_source_domain_dataset_runtime_compatibility(<runtime_model_name>)`
   - `get_source_domain_geojson_cache_warmers()`
4. If map visuals look blank or grey, first check whether the local fixture is too sparse or zoomed to a single synthetic point before treating it as an application bug.

## Practical Notes

- Source-mounted map views may require both route registration and matching fixture data; a missing `GeoDataset.model_name` can produce an `ImproperlyConfigured` error that is unrelated to registry routing.
- `maps.utils.ensure_initial_data()` is idempotent and creates the default region, catchment, and features layers used by normal map rendering.
- Browser recordings should show both the source-mounted route and the runtime GeoDataset route, while shell command outputs can be included as text evidence in the report.
