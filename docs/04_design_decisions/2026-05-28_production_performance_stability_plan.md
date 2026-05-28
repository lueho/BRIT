# Production Performance and Stability Plan

- **Status**: Active roadmap; immediate unbounded catchment-geometry guard complete
- **Date**: 2026-05-28
- **Scope**: Production latency, crawler resilience, GIS serialization safety, GeoJSON delivery, and operational noise reduction

## 1. Context

Papertrail logs from 2026-05-26 and 2026-05-28 show that BRIT's most critical production stability risk is not general infrastructure pressure. Redis, Celery, and Heroku router behavior were broadly healthy in the inspected windows. The critical failures were web-worker timeouts caused by expensive in-process serialization paths.

The strongest confirmed 2026-05-28 incident was a Gunicorn worker timeout in `maps.views.CatchmentOptionGeometryAPI`, where an unbounded request could serialize all catchments through DRF-GIS and GEOS/OGR. Production currently has more than 31,000 catchments and about 2.8 million geometry points, so crawler-style or malformed requests can consume enough CPU and memory to kill a web worker.

The immediate guard for that specific endpoint is complete: `/maps/catchment_options/data/` now requires `id` or `parent_id` and rejects unbounded requests before serialization.

This document tracks the remaining recommendations needed to make the system more stable and lower-latency.

## 2. Principles

- **Bound every expensive public endpoint**
  - No public GIS endpoint should serialize an unbounded production-scale dataset by default.

- **Prefer server-side enforcement over crawler etiquette**
  - `robots.txt` is useful, but not sufficient. Expensive endpoints need application-level guards.

- **Move geometry serialization out of Python hot paths where possible**
  - Large geometry responses should avoid repeated DRF-GIS and GEOS/OGR conversion when database-side GeoJSON or cached artifacts can serve the same purpose.

- **Keep generic dataset exploration safe by default**
  - Dynamic `GeoDataset` surfaces need caps, indexes, observability, and clear exposure policies before broad public use.

- **Treat warning noise as an operational signal**
  - Repeated 404/400 patterns can hide real issues and can also indicate stale links, frontend misuse, or crawlers discovering expensive surfaces.

## 3. Current Findings

### 3.1 Critical GIS serialization paths

- `maps.views.CatchmentOptionGeometryAPI` previously serialized all catchments when no filter was provided.
- `maps.mixins.CachedGeoJSONMixin._stream_geojson` previously appeared in a worker-timeout stack while serializing geometry one feature at a time.
- Both paths point to the same underlying risk: Python-side GeoJSON generation is too costly for large or complex uncached geometries.

### 3.2 Registration POST latency

Repeated `/users/register/?next=/home/` POSTs from varied IP addresses took up to about 3.2 seconds and returned HTTP 200. This is likely invalid bot/form traffic, possibly involving Turnstile validation. It is not the main stability issue, but it is a cheap hardening target.

### 3.3 Broken-link and warning noise

The inspected logs included repeated warnings for:

- `/waste_collection/collectors/<id>/None`
- `/maps/geodatasets/<id>/table/`
- `/waste_collection/properties/<id>/`
- `/waste_collection/api/collection/geojson/`
- unordered pagination for `sources.greenhouses.models.NantesGreenhouses`

These should be cleaned up so production logs better distinguish real incidents from stale navigation and crawler noise.

## 4. Completed Immediate Action

### Phase 0 - Bound the most dangerous crawler-triggered endpoint

Status: complete.

Implemented:

- `CatchmentOptionGeometryAPI` now requires `id` or `parent_id`.
- Unbounded requests return HTTP 400 before any GeoJSON serialization.
- Regression coverage verifies:
  - unbounded requests are rejected
  - single-catchment `id` requests still work
  - bounded `parent_id` child requests still work

Commit:

- `423087a545daa0561a88d4b7d22fa0fcae2f4730` - `fix: bound catchment geometry endpoint`

## 5. Remaining Delivery Plan

### Phase 1 - Audit and bound all public GIS serialization endpoints

Goal: make it impossible for crawlers or malformed requests to trigger production-scale GIS serialization through public routes.

Status: implemented for known public GeoJSON serialization paths.

Implementation checkpoint:

- The shared `CachedGeoJSONMixin` now rejects cache-miss or forced-stream unbounded GeoJSON requests above the configured feature cap before serialization.
- Bounded requests remain allowed when they use `id`, a valid `bbox`, or a filter declared by the endpoint's filterset.
- Unknown query parameters do not count as bounds.
- Dataset-scoped local-relation GeoJSON routes now apply the same guard using `id` and explicitly filterable dataset columns.
- Direct GeoJSON actions that bypass the shared mixin now call the shared rejection helper:
  - `maps.viewsets.LocationViewSet.geojson`
  - `sources.greenhouses.viewsets.NantesGreenhousesViewSet.geojson`
  - `case_studies.closecycle.viewsets.ShowcaseViewSet.geojson`
  - `sources.waste_collection.waste_atlas.viewsets.CatchmentViewSet.geojson`

Tasks:

- Inventory all public or anonymous geometry endpoints, including:
  - `*/geojson/`
  - `*/data/` geometry endpoints
  - dataset-scoped GeoDataset GeoJSON routes
  - source-domain map GeoJSON routes
  - export endpoints that can trigger map rendering or geometry fetches
- For each endpoint, record:
  - whether anonymous access is allowed
  - whether the endpoint can return an unbounded dataset
  - whether bounding parameters are required
  - whether max feature-count, bbox, pagination, or streaming safeguards exist
  - whether the endpoint uses DRF-GIS/GEOS serialization, database-side GeoJSON, cached JSON, or static artifacts
- Add explicit guards for endpoints that can still return large unbounded geometry responses.
- Add regression tests for every endpoint that receives a new guard.

Success criteria:

- No anonymous endpoint can serialize a full production-scale GIS dataset without an explicit safe bound or approved cached path.
- Guard behavior is covered by tests.
- `robots.txt` remains advisory, not the primary protection.

### Phase 2 - Move large GeoJSON generation to cheaper serialization paths

Goal: reduce CPU and memory cost for legitimate large geometry requests.

Tasks:

- Prefer database-side geometry serialization for large querysets:
  - `ST_AsGeoJSON`
  - Django GIS `AsGeoJSON`
  - controlled `SimplifyPreserveTopology` where appropriate
- Avoid materializing `serializer.data` for large geometry result sets.
- Add simplified geometry modes for UI map display where full precision is not needed.
- Evaluate whether common boundaries should have precomputed simplified geometry columns or cached artifacts.
- Keep full-resolution geometry available only where the product actually needs it.

Success criteria:

- Large map responses avoid repeated Python GEOS/OGR conversion.
- Memory usage is bounded during cache misses.
- Visual map quality remains acceptable for normal browsing.

### Phase 3 - Harden GeoJSON caching, streaming, and cache warming

Goal: make cold map loads predictable and reduce repeated expensive cache misses.

Tasks:

- Extend cache/version behavior to any remaining custom geometry endpoints that bypass `CachedGeoJSONMixin`.
- Add or extend warmers for common public map scopes.
- Track and expose response metadata consistently:
  - `X-Cache-Status`
  - `X-Total-Count`
  - `X-Data-Version`
- Add instrumentation around:
  - feature count
  - geometry point count where cheap to compute
  - serialization duration
  - response size
  - cache hit/miss
- Define safe behavior for cache misses on very large datasets.

Success criteria:

- Common maps are served from cache or pre-warmed artifacts most of the time.
- Cache misses have bounded memory/CPU behavior.
- Production logs make slow GeoJSON requests diagnosable without stack traces.

### Phase 4 - Frontend request discipline

Goal: prevent BRIT's own JavaScript from accidentally making broad geometry requests.

Tasks:

- Audit map JavaScript callers for geometry endpoints.
- Ensure selection-driven maps only request bounded scopes.
- Add client-side checks that avoid geometry fetches when required selectors are empty.
- Prefer top-level lightweight summary or NUTS-level geometry when no detailed catchment scope is selected.
- Remove or disable stale map entry points that are marked out of use.

Success criteria:

- Normal UI interactions cannot accidentally request all catchment geometries.
- Empty selector states load cheap defaults, not detailed features.
- Frontend behavior matches server-side guard expectations.

### Phase 5 - Generic GeoDataset runtime safeguards

Goal: ensure dynamic dataset exploration remains safe as more datasets become runtime-configured.

Tasks:

- Add feature-count and query-cost guardrails to dataset-scoped map/GeoJSON routes.
- Require or strongly prefer indexes for:
  - primary key column
  - geometry column
  - common filter columns
- Add operator-facing health checks for large datasets.
- Add warnings for public datasets with unsafe unfiltered map defaults.
- Ensure hidden columns cannot leak through table, detail, filter, export, or GeoJSON paths.
- Consider per-dataset maximum unfiltered feature limits and required bbox behavior.

Success criteria:

- Large local-relation datasets can be browsed without worker timeouts.
- Operators can see when a dataset is unsafe to publish broadly.
- Dynamic routes retain the same exposure-policy guarantees as bespoke routes.

### Phase 6 - Reduce bot and invalid-request pressure

Goal: reduce avoidable latency and wasted work from automated traffic.

Tasks:

- Add rate limiting for `/users/register/`.
- Confirm Turnstile validation fails cheaply for invalid submissions.
- Consider infrastructure-level bot rules for repeated invalid registration POSTs.
- Add rate limiting or throttling for expensive anonymous geometry and export endpoints.
- Review whether DRF throttling, middleware-level throttling, or edge/WAF rules are the best fit per endpoint category.

Success criteria:

- Registration bot traffic cannot create repeated multi-second application work.
- Expensive anonymous endpoints have a clear request budget.
- Legitimate logged-in users are not blocked by crawler protections.

### Phase 7 - Clean production warning noise

Goal: make logs actionable and remove repeated stale-link patterns.

Tasks:

- Fix `/waste_collection/collectors/<id>/None` link generation.
- Fix or hide `/maps/geodatasets/<id>/table/` links for unsupported datasets.
- Fix stale `/waste_collection/properties/<id>/` links or redirect legacy paths where appropriate.
- Investigate repeated `/waste_collection/api/collection/geojson/` bad requests and align frontend query construction if needed.
- Add deterministic ordering to `NantesGreenhouses` list pagination.

Success criteria:

- Repeated known 404/400 warnings are removed or intentionally downgraded.
- Production warning logs are useful for detecting new regressions.

## 6. Observability Checklist

Add structured logging or metrics for high-risk endpoints with at least:

- route name or endpoint family
- authenticated vs anonymous request
- query parameters relevant to bounding
- result count
- cache status
- response time
- response size where available
- warning when an endpoint rejects an unbounded request

Avoid logging sensitive data, tokens, credentials, or full arbitrary query strings.

## 7. Definition of Done

This roadmap is complete when:

- no public GIS endpoint can trigger unbounded full-dataset serialization through normal HTTP requests
- large legitimate GeoJSON responses are cached, streamed safely, or generated through cheaper database-side serialization
- common public map scopes are pre-warmed or have predictable cache-miss behavior
- dynamic GeoDataset routes have explicit size, policy, and index safeguards
- registration and expensive anonymous routes have reasonable bot protection
- recurring broken-link and bad-request warning noise is cleaned up
- production logs contain enough structured context to diagnose future slow requests without relying on worker-timeout tracebacks
