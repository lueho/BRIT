# Production Performance and Stability Plan

- **Status**: Active roadmap; May 31 logs add collection-list serialization and deployment-verification priorities; June 1 endpoint-consumer review adds guardrail priorities, a DRF-GIS-first geospatial delivery strategy, and public-surface/bot-protection work
- **Date**: 2026-05-28
- **Scope**: Production latency, crawler resilience, GIS serialization safety, GeoJSON delivery, heavy API list serialization, deployment verification, and operational noise reduction

## 1. Context

Papertrail logs from 2026-05-26 and 2026-05-28 show that BRIT's most critical production stability risk is not general infrastructure pressure. Redis, Celery, and Heroku router behavior were broadly healthy in the inspected windows. The critical failures were web-worker timeouts caused by expensive in-process serialization paths.

The strongest confirmed 2026-05-28 incident was a Gunicorn worker timeout in `maps.views.CatchmentOptionGeometryAPI`, where an unbounded request could serialize all catchments through DRF-GIS and GEOS/OGR. Production currently has more than 31,000 catchments and about 2.8 million geometry points, so crawler-style or malformed requests can consume enough CPU and memory to kill a web worker.

The deprecated endpoint that exposed that specific path has now been removed after confirming that only an out-of-use, unrouted view still referenced it.

Papertrail logs from 2026-05-31 09:00-23:59 UTC confirm two additional worker-killing paths:

- At 19:50 UTC, a Gunicorn worker timed out while DRF serialized a `sources.waste_collection` collection list. The stack reached `CollectionReferenceFieldsMixin.get_predecessor_ids()` through `CollectionFlatSerializer`/`CollectionResearchSerializer`, confirming that non-GIS list/research/export responses can still trigger timeout risk through per-row database work.
- At 22:38 UTC, a Gunicorn worker timed out again in `CatchmentOptionGeometryAPI.get()` while returning `JsonResponse({"geoJson": serializer.data})`. Web dyno memory reached about 419.84 MB shortly before the timeout on a 512 MB dyno. This confirms that stale high-risk endpoints should be removed when they are no longer used, and that code-level endpoint fixes must be deployed and smoke-tested in production.

The May 31 router logs remained sparse and did not show router 5xx or Heroku H-code errors. Redis remained healthy. The incidents are therefore still application hot-path failures, not infrastructure saturation.

This document tracks the remaining recommendations needed to make the system more stable and lower-latency.

## 2. Principles

- **Bound every expensive public endpoint**
  - No public GIS endpoint should serialize an unbounded production-scale dataset by default.

- **Bound heavy list serialization, not only geometry**
  - API list, research, and export responses must not materialize unbounded production-scale rows or run per-row database queries for dynamic columns.

- **Prefer server-side enforcement over crawler etiquette**
  - `robots.txt` is useful, but not sufficient. Expensive endpoints need application-level guards.

- **Minimize the anonymous public attack surface**
  - Every performance-critical endpoint should have an explicit access decision: public by product requirement, registered-user only, staff/reviewer only, or internal/worker only.
  - Public endpoints should be the exception for product-facing maps, public datasets, documented external GIS access, and registration/login flows, not the default for every API route.

- **Treat bots and crawlers as a first-class performance risk**
  - Bot controls, anonymous rate limits, cheap rejection, Cloudflare rules, and registration protection should be implemented before changing serializer architecture.

- **Treat "implemented" as incomplete until production behavior is verified**
  - Every critical guard needs a post-deploy smoke check against the production route, because an undeployed or misconfigured guard is operationally equivalent to no guard.

- **Keep DRF-GIS where it is the right abstraction**
  - Normal API/CRUD endpoints should keep DRF/DRF-GIS serializers for validation, permissions, browsable API behavior, nested fields, create/update behavior, and serializer reuse.

- **Switch away from DRF-GIS only as a last resort**
  - For heavy read-only layer delivery, first restrict unnecessary public access, add bounds and pagination, improve query planning, cache and pre-warm common responses, offload exports, and add bot/rate-limit controls.
  - Only move a route to database-side GeoJSON, vector tiles, cached artifacts, or worker-generated files when DRF-GIS remains too slow after those measures or when the endpoint is clearly a rendered geospatial transport rather than a domain API.

- **Keep generic dataset exploration safe by default**
  - Dynamic `GeoDataset` surfaces need caps, indexes, observability, and clear exposure policies before broad public use.

- **Treat warning noise as an operational signal**
  - Repeated 404/400 patterns can hide real issues and can also indicate stale links, frontend misuse, or crawlers discovering expensive surfaces.

## 3. Current Findings

### 3.1 Critical GIS serialization paths

- `maps.views.CatchmentOptionGeometryAPI` previously serialized all catchments when no filter was provided.
- The 2026-05-31 logs show the same endpoint still timed out in production at 22:38 UTC while materializing `serializer.data`.
- The endpoint and its stale `sources.waste_collection` catchment-selection consumer have been removed.
- `maps.mixins.CachedGeoJSONMixin._stream_geojson` previously appeared in a worker-timeout stack while serializing geometry one feature at a time.
- Both paths point to the same underlying risk: Python-side GeoJSON generation is too costly for large or complex uncached geometries.

### 3.2 Critical collection-list serialization paths

- The 2026-05-31 19:50 UTC timeout occurred during DRF list serialization for `sources.waste_collection`.
- The stack reached `sources/waste_collection/serializers.py` through:
  - `rest_framework.mixins.ListModelMixin.list`
  - `Response(serializer.data)`
  - `CollectionFlatSerializer.to_representation`
  - `CollectionReferenceFieldsMixin.get_predecessor_ids`
- This confirms a separate high-risk class from GIS: list/research/export endpoints that combine many rows with dynamic per-row fields, relationship lookups, property lookup, region attributes, CPV/ACPV display values, flyers, and sources.
- The default API list path should therefore be compact, paginated, and query-planned. Heavy dynamic-column output should be bounded, explicitly requested, or moved to an asynchronous export path.

### 3.3 Bot and invalid-request latency

Repeated `/users/register/?next=/home/` POSTs from varied IP addresses took up to about 3.2 seconds and returned HTTP 200. This is likely invalid bot/form traffic, possibly involving Turnstile validation. It is not the main stability issue, but it is a cheap hardening target.

The 2026-05-31 router logs additionally showed repeated invalid `POST /` traffic from one IP, taking about 2.3-3.1 seconds and returning 301/403. Root-level invalid POSTs should fail cheaply for the same reason as registration bot traffic.

Bot and crawler traffic should be treated as a likely amplifier for the GeoJSON
and heavy-list incidents. Before replacing DRF-GIS paths, audit which heavy
endpoints actually need anonymous access and apply registered-user, group,
throttle, or edge protections where public access is not part of the product
requirement. BRIT already uses Cloudflare Turnstile on registration; for API and
map endpoints, evaluate Cloudflare WAF rules, rate limiting, managed challenges,
or Turnstile/pre-clearance flows where compatible with normal browser map use.

### 3.4 Broken-link and warning noise

The inspected logs included repeated warnings for:

- `/waste_collection/collectors/<id>/None`
- `/maps/geodatasets/<id>/table/`
- `/waste_collection/properties/<id>/`
- `/waste_collection/api/collection/geojson/`
- unordered pagination for `sources.greenhouses.models.NantesGreenhouses`

These should be cleaned up so production logs better distinguish real incidents from stale navigation and crawler noise.

The 2026-05-31 logs showed the same warning families, with normalized counts in the inspected window:

- 46x `/maps/geodatasets/<id>/table/` 404
- 41x `/waste_collection/collectors/<id>/None` 404
- 33x `/waste_collection/properties/<id>/` 404
- 9x `UnorderedObjectListWarning` for `NantesGreenhouses`
- 8x `/waste_collection/api/collection/geojson/` 400
- 2x `/maps/geodatasets/<id>/map/null` 404

### 3.5 Endpoint-consumer review and guardrail plan

This review covers the remaining performance-critical endpoints after removing
`CatchmentOptionGeometryAPI`. The main finding is that not all large requests
are abusive. Some endpoints intentionally serve country-level or full-layer
datasets for maps, Waste Atlas pages, QGIS, or exports. Guardrails therefore
need to distinguish unsupported unbounded requests from legitimate broad
product use cases that should be cached, streamed, precomputed, or moved to
workers.

Serializer and delivery strategy should be tiered, with DRF-GIS as the default
and database/vector-tile transports as escalation paths rather than a blanket
replacement:

1. **DRF-GIS**
   - Use for correctness-oriented domain APIs, normal CRUD, admin-facing edit
     flows, modest payloads, object details, validation, permissions, browsable
     API behavior, and serializer reuse.
2. **DB-side GeoJSON streaming**
   - Use only after access restrictions, bot controls, caching/warming,
     query-planning improvements, bounds, pagination, and async exports are not
     enough for a heavy read-only endpoint.
   - Target endpoints that represent a rendered layer or export payload rather
     than editable domain objects.
   - Require bbox, country, year, waste category, collection system, ID, or
     similarly explicit filters unless the endpoint is backed by a warmed
     artifact or intentionally supports a broad public scope.
   - Generate each feature with PostGIS, transform output to EPSG:4326, and
     stream rows in chunks from Django without hydrating model instances.
   - Do not use a single `json_agg`/`json_build_object` query as the default
     implementation for large responses, because it still materializes the full
     FeatureCollection before returning it.
3. **PostGIS vector tiles**
   - Use as a later escalation for high-performance interactive maps with many
     features or complex nationwide geometries.
   - Keep GeoJSON available for smaller filtered datasets, debugging, public
     data access, and exports where FeatureCollection semantics are required.

Decision criterion: if an endpoint represents **domain objects**, keep DRF or
DRF-GIS. If it represents a **rendered geospatial layer**, still try DRF-GIS
with access controls, caching, throttling, and bounded requests first; prefer a
dedicated read-only transport path backed by PostGIS, artifacts, or vector tiles
only when those lower-risk measures are insufficient.

#### Shared map GeoJSON endpoints

Endpoints:

- `/maps/api/region/geojson/`
  - Viewset: `maps.viewsets.RegionViewSet`
  - Main use: contextual region boundaries on shared map pages.
- `/maps/api/catchment/geojson/`
  - Viewset: `maps.viewsets.CatchmentViewSet`
  - Main use: contextual catchment boundaries on shared map pages.
- `/maps/api/nuts_region/geojson/`
  - Viewset: `maps.viewsets.NutsRegionViewSet`
  - Main use: Waste Atlas country and administrative-level boundaries.
- `/maps/api/location/geojson/`
  - Viewset: `maps.viewsets.LocationViewSet`
  - Main use: location feature maps.

Consumers:

- `maps/static/js/maps.js`
  - `loadLayers()`
  - `fetchRegionGeometry()`
  - `fetchCatchmentGeometry()`
  - `fetchFeatureGeometries()`
- `maps.views.MapMixin`
  - builds `regionLayerGeometriesUrl`, `catchmentLayerGeometriesUrl`,
    `featuresLayerGeometriesUrl`, detail URL templates, and summary URLs.
- `sources.waste_collection.waste_atlas.static.js.waste_atlas_choropleth.js`
  - fetches NUTS country and regional geometry for atlas maps.

Exact use cases:

- Region and catchment layers are normally contextual overlays loaded by
  selected `region`, `catchment`, object detail context, or map configuration.
- NUTS regions are legitimately requested at country scope by Waste Atlas:
  `/maps/api/nuts_region/geojson/?levl_code=0&cntr_code=<country>` and
  `/maps/api/nuts_region/geojson/?levl_code=<level>&cntr_code=<country>`.
- Feature layers use endpoint-specific `featuresLayerGeometriesUrl` values
  injected by the current map view.

Current guardrails:

- `CachedGeoJSONMixin` provides server-side caching, cache-version headers,
  streaming above threshold, and rejection of unsafe unbounded cache misses.
- Bounded requests are allowed when they use `id`, `bbox`, or declared
  filterset parameters.
- `maps.js` also uses IndexedDB and version validation to reduce repeated
  downloads from normal browser sessions.

Recommended guardrails:

- Keep `id`, `bbox`, filterset-bound checks, cache-version headers, and
  client-side version-aware caching.
- Do not require `bbox` for Waste Atlas NUTS requests, because country-level
  NUTS geometry is a valid product use case.
- Keep large Region/Catchment/NUTS responses on DRF-GIS where caching,
  warming, simplified geometry, and bounded requests are sufficient.
- Escalate only persistently failing large Region/Catchment/NUTS responses to
  DB-side GeoJSON streaming or precomputed simplified artifacts.
- Add feature-count, estimated point-count, serialization-mode, cache-status,
  duration, and response-size logging.
- Pre-warm common country and NUTS-level artifacts used by Waste Atlas.

#### Waste Collection interactive map GeoJSON

Endpoint:

- `/waste_collection/api/collection/geojson/`
  - Viewset: `sources.waste_collection.viewsets.CollectionViewSet`
  - Serializer: `WasteCollectionGeometrySerializer`

Consumers:

- `sources.waste_collection.views.WasteCollectionPublishedMapView`
- `sources.waste_collection.views.WasteCollectionPrivateMapView`
- `sources.waste_collection.views.WasteCollectionReviewMapView`
- `sources.waste_collection.views.WasteCollectionPublishedMapIframeView`
- `sources/waste_collection/templates/waste_collection_map.html`
- `sources/waste_collection/static/js/waste_collection_map.js`
- `maps/static/js/maps.js`

Exact use cases:

- Public, private, and review map browsing for household waste collections.
- Filtered list-to-map navigation.
- Selecting overlapping collection polygons and opening detail, copy, edit,
  delete, or full-details actions.
- Exporting filtered collections from the map context.
- Public iframe map embedding.

Current guardrails:

- `CachedGeoJSONMixin` caching, versioning, streaming, and unbounded-request
  rejection.
- DRF throttling:
  - anonymous users: `10/minute`
  - authenticated users: `60/minute`
- Simplified geometry annotation from catchment region borders.
- Scope-aware latest-visible collection filtering.
- `skip_min_max=True` for `geojson`, `list`, and `version` actions to avoid
  expensive filter-widget min/max work.
- Consumer-impact check after the non-public scope auth guard:
  - Published map and iframe views force `scope=published`, so anonymous public
    map consumers should not change behavior.
  - Private and review map views are login/review gated before rendering; their
    browser GeoJSON, summary, detail, and version checks carry the authenticated
    session and can continue using `scope=private` or `scope=review`.
  - No source-code frontend consumer was found that anonymously constructs
    `scope=private` or `scope=review` for this endpoint.
- Production log check from `2026-06-01T12:00Z` through `2026-06-02T06:59Z`
  showed 12 `400 Bad Request` events for this endpoint. These are consistent
  with unsafe/unbounded GeoJSON requests being rejected instead of serialized.

Recommended guardrails:

- Treat this as the highest-priority remaining GeoJSON endpoint.
- Bypass DRF-GIS only for large read-only layer responses, using DB-side
  GeoJSON streaming or precomputed artifacts.
- Pre-warm common scopes:
  - published all
  - per country
  - common country/year/category filters
  - public iframe defaults
- Keep rate limits and server-side rejection as a fallback for unsafe
  cache-miss paths.
- Do not permanently reject legitimate broad published maps when they are
  served from warmed artifacts or a bounded streaming path.
- Add production smoke checks for both rejection behavior and legitimate
  filtered map behavior.

#### Waste Collection list and research API

Endpoint:

- `/waste_collection/api/collection/`
  - Viewset: `sources.waste_collection.viewsets.CollectionViewSet`
  - List serializer: `CollectionResearchSerializer`

Consumers:

- Internal research/review workflows.
- API clients that retrieve collection metadata.
- Test coverage in `sources.waste_collection.tests.test_viewsets` and
  `sources.waste_collection.tests.test_collection_research_metrics`.
- Potential BRIT MCP/review tooling that resolves collection summaries and
  predecessor/successor metadata.

Exact use cases:

- Paginated research metadata lookup.
- Scope-aware published/private/review collection discovery.
- Fetching relationship metadata, predecessor IDs, flyers, sources, and
  collection properties.

Consumer-impact check after the non-public scope auth guard:

- Known in-repo consumers that request non-public scopes are authenticated:
  - browser list/map flows are served from login-gated private/review views
  - `import_denmark_affaldsstatistik_cpvs` uses token authentication when it
    reads `published`, `review`, and `private` scopes
  - tests and MCP/review-style tooling are expected to authenticate for
    non-public scopes
- No in-repo JavaScript or template consumer was found that anonymously calls
  the collection list API with `scope=private` or `scope=review`.
- External anonymous clients must use `scope=published` or authenticate before
  requesting private/review/declined/archived scopes.

Current risk:

- The 2026-05-31 timeout shows that non-GIS collection serialization can kill a
  web worker. The hot path reached `CollectionFlatSerializer` and
  `CollectionReferenceFieldsMixin.get_predecessor_ids()`.
- The 2026-06-02 logs show the GeoJSON guardrails helped, but one web worker
  still timed out in the collection list API. The stack reached
  `CollectionResearchSerializer` and
  `CollectionReferenceFieldsMixin.get_successor_ids()`, indicating remaining
  N+1 relationship lookup risk in list serialization.
- Dynamic region attributes, CPV/ACPV display values, sources, flyers, and
  predecessor/successor fields can create per-row query storms when responses
  are too large or not preplanned.

Recommended guardrails:

- Prefetch predecessor and successor relationships for the list queryset and
  make `CollectionReferenceFieldsMixin` consume prefetched objects when present.
- Confirm and enforce DRF pagination for the collection API list action.
- Cap maximum page size for research/list API clients.
- Reject unpaginated heavy list requests unless routed to a safe asynchronous
  export flow.
- Split compact default API responses from heavyweight dynamic-column export
  output.
- Prefetch predecessors, successors, flyers, sources, visible CPV/ACPV values,
  and region attributes before serialization.
- Resolve dynamic `Property` IDs once per request, not once per row and
  property.
- Add query-count and response-time tests for representative collection list
  responses.

#### Waste Collection export

Endpoint:

- `/waste_collection/collections/export/`
  - View: `CollectionListFileExportView`
  - Base: `GenericUserCreatedObjectExportView`

Consumers:

- `sources/waste_collection/templates/waste_collection_map.html`
- `sources/waste_collection/templates/waste_collection/collection_filter.html`
- `sources/waste_collection/templates/waste_collection/collection_detail.html`

Exact use cases:

- Export filtered collection lists from list and map pages.
- Export a specific collection from a detail page.
- Produce heavy flat data that should not block a web request.

Current guardrails:

- Export dispatch is already asynchronous through Celery and returns a task ID.

Recommended guardrails:

- Keep heavy export generation off web dynos.
- Add row-count estimates before dispatching large exports.
- Add queue/rate controls for large exports.
- Limit concurrent export workers if export generation competes with cache
  warming or other production-critical worker tasks.
- Require explicit confirmation, staff-only mode, or background-only handling
  for very large exports.

#### Dynamic GeoDataset local-relation GeoJSON

Endpoint:

- `/maps/geodatasets/<pk>/features.geojson`
  - View: `maps.views.GeoDataSetRuntimeFeatureGeoJSONView`

Consumers:

- `GeoDataSetRuntimeMapView`
- `GeoDataSetRuntimeFeatureDetailView`
- `GeoDataSetRuntimeTableView`
- `maps/static/js/maps.js`

Exact use cases:

- Dynamic local-relation dataset maps.
- Filtered dataset maps.
- Single-feature detail maps where `id` selects one feature.
- Table-to-map and map-to-detail navigation for configured datasets.

Current guardrails:

- Only local-relation runtime adapters can use the route.
- Responses stream as GeoJSON feature collections.
- Unsafe unbounded requests are rejected using `id` and explicitly filterable
  dataset columns as bounds.
- Hidden columns are not accepted as filter bounds.

Recommended guardrails:

- Add per-dataset publication safety checks:
  - maximum unfiltered feature count
  - required `bbox` or required filter flag
  - geometry index check
  - index checks for public filterable columns
  - estimated payload-size or point-count threshold
- Ensure `id`-bounded single-feature requests compute count and version against
  the selected feature scope, not the full dataset.
- Add operator-facing warnings for public datasets with unsafe unfiltered map
  defaults.

#### Waste Atlas GeoJSON and thematic data endpoints

Geometry endpoint:

- `/waste_collection/api/waste-atlas/catchment/geojson/`
  - Viewset: `sources.waste_collection.waste_atlas.viewsets.CatchmentViewSet`

Thematic data endpoints:

- `/waste_collection/api/waste-atlas/orga-level/`
- `/waste_collection/api/waste-atlas/collection-system/`
- `/waste_collection/api/waste-atlas/*`

Consumers:

- `sources/waste_collection/waste_atlas/static/js/waste_atlas_choropleth.js`
- Waste Atlas map views under `/waste_collection/api/waste-atlas/map/...`
- Members of the `waste_atlas` group.

Exact use cases:

- Country/year/nuts-prefix scoped choropleth maps.
- Publication-quality D3 SVG rendering.
- Concurrent fetch of catchment geometry, NUTS country boundary, NUTS regional
  boundaries, and one thematic data endpoint.
- Optional outline overlays for ACPV-derived regions.

Current guardrails:

- Waste Atlas HTML views require login and membership in the `waste_atlas`
  group.
- Geometry endpoint supports country, year, NUTS-prefix, and `id` bounds.
- Catchment geometry uses simplified geometry annotation.

Recommended guardrails:

- Do not reject valid country/year Waste Atlas requests; they are the product
  use case.
- Add cache-first or artifact-first serving for:
  - geometry by `country/year/nuts_prefix`
  - thematic data by `map_type/country/year/nuts_prefix`
  - NUTS boundaries by `country/level`
- Add cache-version metadata and conditional request support.
- Add throttling even though the pages are group-restricted.
- Consider async render/export jobs for publication-quality map outputs.

#### Source-domain map GeoJSON endpoints

Endpoints:

- `/maps/nantes/api/nantes_greenhouses/geojson/`
  - Viewset: `sources.greenhouses.viewsets.NantesGreenhousesViewSet`
  - Also mounted publicly under
    `/case_studies/nantes/api/nantes_greenhouses/geojson/`.
- `/sources/api/hamburg_roadside_trees/geojson/`
  - Viewset: `sources.roadside_trees.viewsets.HamburgRoadsideTreeViewSet`
  - Also mounted for maps under
    `/maps/hamburg/api/hamburg_roadside_trees/geojson/`.
  - Legacy `/case_studies/hamburg/api/...` routes redirect to `/sources/api/...`.
- `/closecycle/api/showcase/geojson/`
  - Viewset: `case_studies.closecycle.viewsets.ShowcaseViewSet`

Consumers:

- Greenhouse, roadside-tree, and CLOSECYCLE showcase map pages.
- Source-specific JavaScript plus shared `maps.js`.
- Tests asserting that map pages include the relevant GeoJSON routes.

Exact use cases:

- Nantes greenhouses: filtered greenhouse map and summary metrics.
- Hamburg roadside trees: public point map with filter controls.
- CLOSECYCLE showcase: small showcase and pilot-region map.

Current guardrails:

- Greenhouses and CLOSECYCLE direct GeoJSON actions use the shared unbounded
  rejection helper.
- Roadside trees use `CachedGeoJSONMixin`, default-filter cache normalization,
  `only("id", "geom")`, and DRF throttling.

Recommended guardrails:

- Keep CLOSECYCLE as a low-risk small-dataset endpoint but document the
  small-data assumption.
- Move greenhouses to cached or DB-side streaming behavior if the dataset grows.
- Pre-warm roadside-tree all-points and common filtered artifacts if public map
  traffic is significant.
- Consider clustering or vector tiles for roadside trees if point counts become
  large.

#### Collector GeoJSON for QGIS

Endpoint:

- `/waste_collection/api/collector/geojson/`
  - Viewset: `sources.waste_collection.viewsets.CollectorViewSet`

Consumers:

- QGIS or other external GIS clients.

Exact use cases:

- Pull collector catchment geometries and organizational-level data for GIS
  rendering.
- Broad country or all-collector pulls may be legitimate.

Current guardrails:

- `CachedGeoJSONMixin` cache/version/streaming behavior.
- Cache key varies by `country` and `id`.
- Queryset filters to collectors with geometry and optimizes related geometry
  access.

Recommended guardrails:

- Add the same anonymous/authenticated GeoJSON throttles used by collection and
  roadside-tree GeoJSON endpoints.
- Preserve documented broad QGIS pulls when served from cache, artifacts, or
  safe streaming.
- Pre-warm likely QGIS scopes:
  - all
  - per country
  - selected collector IDs when known from workflows
- Move large responses to DB-side streaming or artifact serving before relying
  on rejection.

#### Guardrail strategy by use case

- Interactive BRIT maps:
  - Avoid auto-loading broad feature layers unless a map is intentionally
    configured for that behavior.
  - Prefer filter, `bbox`, selected object, or cache/artifact-backed requests.
  - Reject unsupported huge cache misses.
- Waste Atlas maps:
  - Allow country/year scopes.
  - Serve from warmed geometry and thematic artifacts.
  - Avoid request-time DRF-GIS serialization.
- QGIS/external GIS clients:
  - Allow documented broad pulls with throttling and cached/artifact-backed
    delivery.
  - Prefer country and ID filters over arbitrary unbounded traffic.
- Research/list API:
  - Enforce pagination and compact default serializers.
  - Move heavy dynamic fields to explicit export or bounded detail flows.
- Exports:
  - Keep work in Celery.
  - Add row-count estimates, queue controls, and explicit large-export handling.

Highest-priority next implementation reviews:

1. `/waste_collection/api/collection/geojson/`
   - product-critical, high-volume, and likely the largest interactive map
     surface.
2. `/waste_collection/api/collection/`
   - confirmed non-GIS worker-timeout family.
3. Waste Atlas geometry and thematic endpoints
   - valid large country/year requests should be cached or precomputed, not
     rejected.
4. `/maps/geodatasets/<pk>/features.geojson`
   - needs dataset-level publication safety and refined single-feature
     `id` handling.
5. `/waste_collection/api/collector/geojson/`
   - QGIS-oriented endpoint should get throttling and warmed broad-scope
     artifacts.

## 4. Completed Immediate Action

### Phase 0 - Remove the most dangerous stale crawler-triggered endpoint

Status: complete.

Implemented:

- `CatchmentOptionGeometryAPI` and the `/maps/catchment_options/data/` route have been removed.
- The out-of-use `CatchmentSelectView` and its stale `waste_collection_catchment_list.html` template have been removed.
- The stale `/waste_collection/catchment_selection/` plugin metadata entry has been removed.
- Regression coverage for the removed endpoint has been deleted.

Commit:

- `423087a545daa0561a88d4b7d22fa0fcae2f4730` - `fix: bound catchment geometry endpoint`

## 5. Remaining Delivery Plan

### Phase 1 - Audit and bound all public GIS serialization endpoints

Goal: make it impossible for crawlers or malformed requests to trigger production-scale GIS serialization through public routes.

Status: implemented for known public GeoJSON serialization paths in code; production deployment and smoke-check verification remain mandatory.

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
- The 2026-05-31 production timeout in `CatchmentOptionGeometryAPI` was addressed by removing the stale endpoint rather than maintaining another public geometry surface.

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
- Add post-deploy production smoke checks for critical guards:
  - `/maps/catchment_options/data/` is no longer registered.
  - `/waste_collection/api/collection/geojson/` rejects unbounded unsafe requests cheaply.
  - dataset-scoped GeoJSON routes reject unsafe unbounded requests.

Success criteria:

- No anonymous endpoint can serialize a full production-scale GIS dataset without an explicit safe bound or approved cached path.
- Guard behavior is covered by tests.
- Critical guard behavior is verified once on production after deployment.
- `robots.txt` remains advisory, not the primary protection.

### Phase 1.5 - Bound waste-collection list, research, and export serialization

Goal: prevent heavy non-GIS collection responses from killing web workers through unbounded row counts or per-row query work.

Tasks:

- Inventory `sources.waste_collection` API and export paths that use:
  - `CollectionFlatSerializer`
  - `CollectionResearchSerializer`
  - dynamic collection-list columns
  - review/research/export list endpoints
- Enforce pagination and maximum page sizes on collection list/research endpoints.
- Reject unpaginated or oversized heavy collection-list requests unless they are explicitly routed to a safe asynchronous export workflow.
- Split compact default list responses from heavyweight dynamic-column exports:
  - default list responses should include stable identity and label fields only
  - dynamic region attributes, CPV/ACPV values, sources, flyers, and version-link fields should require explicit export mode or a narrower filtered query
- Remove per-row database queries from the serializer hot path:
  - prefetch predecessors and successors before `get_predecessor_ids()` and `get_successor_ids()`
  - prefetch flyers and bibliography sources
  - prefetch or annotate region attributes for `Population` and `Population density`
  - resolve `Property` IDs for dynamic CPV/ACPV columns once per request, not once per row and property
  - prefetch visible CPV/ACPV rows needed by the response, respecting user visibility rules
- Add query-count and response-time regression tests for representative collection-list pages.
- Add structured slow-request logging for collection-list serialization with:
  - endpoint/action
  - result count/page size
  - selected serializer/export mode
  - serialization duration
  - query count where available in debug/test instrumentation

Success criteria:

- Collection list/research/export routes cannot materialize all production collections through normal web requests.
- Representative paginated collection list responses have bounded query counts and avoid N+1 relationship lookups.
- Heavy exports are explicit, bounded, or asynchronous and cannot trigger Gunicorn worker timeouts.

### Phase 2 - Audit public exposure and add bot/crawler protection

Goal: reduce avoidable anonymous load before changing serializer architecture.

Tasks:

- Classify every high-cost endpoint as one of:
  - anonymous public by product requirement
  - registered-user only
  - staff/reviewer only
  - internal/worker only
- Restrict endpoints to registered users when the only known consumers are
  authenticated BRIT UI flows, review workflows, admin/editor workflows, or
  internal tooling.
- Keep anonymous access only for intentional public surfaces:
  - public map pages and their necessary layer endpoints
  - public Waste Atlas views
  - documented public data or QGIS access
  - registration, login, static assets, and public documentation
- For anonymous public heavy endpoints, add or verify:
  - DRF throttling or middleware-level rate limits
  - cheap rejection for invalid methods and malformed parameters
  - required bbox/filter/country/year/category bounds where product-compatible
  - cache-aware handling so repeated public requests do not recompute data
  - structured logging for rejects, throttle hits, and suspicious user agents
- Use Cloudflare as an outer protection layer:
  - keep Turnstile on registration and confirm failures are cheap
  - consider Cloudflare WAF/rate-limiting rules for expensive anonymous API
    paths
  - consider managed challenges or Turnstile/pre-clearance for browser-facing
    map entry points where it does not break normal map tile/layer fetches
  - avoid adding interactive challenges directly to machine-oriented documented
    GIS/API endpoints unless an alternate authenticated access path exists
- Add post-deploy smoke checks for both anonymous rejection and allowed
  registered-user access.

Implementation checkpoint:

- Waste Collection API scope guard started:
  - `scope=published` remains anonymously accessible for public map/data use.
  - Explicit non-public scopes now require authentication on:
    - `/waste_collection/api/collection/`
    - `/waste_collection/api/collection/geojson/`
    - `/waste_collection/api/collection/summaries/`
    - `/waste_collection/api/collection/frequencies/`
    - `/waste_collection/api/collection/property-value/`
  - Anonymous requests to `private`, `review`, `declined`, or `archived` scopes
    fail before expensive filtering or serialization work.
- Validation:
  - `docker compose exec web python manage.py test sources.waste_collection.tests.test_viewsets.CollectionViewSetTestCase --settings=brit.settings.testrunner --keepdb --noinput`
  - `docker compose exec web ruff check sources/waste_collection/viewsets.py sources/waste_collection/tests/test_viewsets.py`

Success criteria:

- Each critical endpoint has an explicit public/authenticated/staff/internal
  exposure decision.
- Anonymous bots cannot freely exercise high-cost endpoints that are not
  intentionally public.
- Public map and data pages still work for legitimate users.
- DRF-GIS remains the serving path unless production evidence shows that access
  control, throttling, bounds, caching, and query improvements are insufficient.

### Phase 3 - Keep DRF-GIS viable for large read-only GeoJSON where possible

Goal: reduce CPU and memory cost for legitimate large geometry requests while
keeping DRF-GIS as the default implementation.

Tasks:

- Keep DRF-GIS on normal domain-object APIs and CRUD/edit endpoints.
- Optimize existing DRF-GIS layer endpoints before replacing them:
  - narrow querysets with `only()`, `defer()`, `select_related()`, and
    `prefetch_related()` where relevant
  - use simplified or annotated geometries for map display where full precision
    is unnecessary
  - avoid expensive dynamic properties in geometry serializers
  - precompute or cache repeated properties used in GeoJSON `properties`
  - keep `CachedGeoJSONMixin` cache/version behavior and pre-warm common scopes
  - enforce safe bbox/filter/country/year/category bounds on cache misses
- Prefer database-side geometry serialization only as a fallback for heavy
  read-only layer,
  export, or public data endpoints:
  - `ST_AsGeoJSON`
  - Django GIS `AsGeoJSON`
  - controlled `SimplifyPreserveTopology` where appropriate
- Avoid materializing `serializer.data` for large geometry result sets.
- Add simplified geometry modes for UI map display where full precision is not needed.
- Evaluate whether common boundaries should have precomputed simplified geometry columns or cached artifacts.
- Stream database rows, not serializer objects or aggregate JSON blobs:
  - Use server-side cursors, `iterator()`, or chunked raw cursor fetches.
  - Let PostGIS return geometry as GeoJSON text.
  - Transform geometry to EPSG:4326 before serializing GeoJSON transport.
  - Build each GeoJSON feature with lightweight Python `json.dumps`.
  - Yield the FeatureCollection wrapper and one feature per row.
  - Avoid model instantiation and DRF serializers for bulk map payloads.
- Avoid relying on one `json_build_object(..., "features", json_agg(...))`
  query for large endpoints. It can reduce Python overhead, but it still
  constructs the full response before Django can send bytes to the client.
- Evaluate vector tiles (`MVT`) for interactive map browsing:
  - Use `ST_AsMVT` for tile generation.
  - Use `ST_AsMVTGeom` to transform and clip features to tile coordinate space.
  - Return only features visible in the current tile/zoom.
  - Simplify automatically per zoom level.
  - Cache tiles aggressively.
  - Keep GeoJSON available for exports, debugging, and smaller filtered datasets.
- Precompute simplified geometry columns for repeated map display:
  - Store derived geometry at multiple precision levels (e.g., `geom_web_low`, `geom_web_medium`, `geom_web_high`).
  - Select geometry precision by endpoint or zoom level.
- Precompute common GeoJSON artifacts for known public scopes:
  - Store artifacts in Redis, S3, or Postgres materialized tables.
  - Serve artifacts directly from web dynos to avoid request-time serialization.
- Add content compression and conditional requests:
  - Ensure gzip/br compression is active.
  - Use `ETag` / `Last-Modified` and support `304 Not Modified`.
- Support pagination or chunking for non-map exports:
  - Cursor, limit, or page-based chunking.
  - Newline-delimited GeoJSON features.
  - Asynchronous export jobs for large datasets.
- Prefer the existing Celery file-export pattern for very large exports, because
  WSGI streaming still occupies a web worker for the full response duration and
  does not allow normal middleware to compute full-content metadata such as
  `ETag` or `Content-Length`.
- Keep full-resolution geometry available only where the product actually needs it.

Success criteria:

- Most large map responses remain on DRF-GIS and are served from cache, warmed
  artifacts, or bounded querysets.
- Routes that still time out after the earlier measures have a documented
  last-resort escalation plan.
- Memory usage is bounded during legitimate cache misses.
- Visual map quality remains acceptable for normal browsing.

### Phase 4 - Harden GeoJSON caching, streaming, and cache warming

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
- Offload repeatable expensive work to worker dynos:
  - GeoJSON cache warmers for common full-layer and filtered artifacts.
  - Materialized GeoJSON generation for common scopes.
  - Vector tile pre-generation for hot areas and zoom ranges only if a route is
    escalated beyond DRF-GIS/cached GeoJSON.
  - Simplified geometry column refresh after source geometry changes.
  - Dataset-version computation if current aggregation is expensive.
  - Async export file generation for user-requested large exports.
  - Targeted cache invalidation and warming after data changes.
  - Precompute geometry metrics (feature counts, point counts, bbox, estimated payload size).

Success criteria:

- Common maps are served from cache or pre-warmed artifacts most of the time.
- Cache misses have bounded memory/CPU behavior.
- Production logs make slow GeoJSON requests diagnosable without stack traces.

### Phase 5 - Frontend request discipline

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

### Phase 6 - Generic GeoDataset runtime safeguards

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

### Phase 7 - Reduce remaining bot and invalid-request pressure

Goal: reduce avoidable latency and wasted work from automated traffic.

Tasks:

- Keep rate limiting for `/users/register/` aligned with existing Cloudflare
  Turnstile protection.
- Confirm Turnstile validation fails cheaply for invalid submissions.
- Make invalid `POST /` requests fail cheaply before expensive middleware, form, or permission work.
- Consider infrastructure-level bot rules for repeated invalid registration POSTs.
- Add rate limiting or throttling for expensive anonymous geometry and export endpoints.
- Review whether DRF throttling, middleware-level throttling, or edge/WAF rules are the best fit per endpoint category.

Success criteria:

- Registration bot traffic cannot create repeated multi-second application work.
- Root-level invalid POST traffic cannot create repeated multi-second application work.
- Expensive anonymous endpoints have a clear request budget.
- Legitimate logged-in users are not blocked by crawler protections.

### Phase 8 - Clean production warning noise

Goal: make logs actionable and remove repeated stale-link patterns.

Tasks:

- Fix `/waste_collection/collectors/<id>/None` link generation.
- Fix or hide `/maps/geodatasets/<id>/table/` links for unsupported datasets.
- Fix or hide `/maps/geodatasets/<id>/map/null` links for unsupported map states.
- Fix stale `/waste_collection/properties/<id>/` links or redirect legacy paths where appropriate.
- Investigate repeated `/waste_collection/api/collection/geojson/` bad requests and align frontend query construction if needed.
- Add deterministic ordering to `NantesGreenhouses` list pagination.

Success criteria:

- Repeated known 404/400 warnings are removed or intentionally downgraded.
- Production warning logs are useful for detecting new regressions.

### Phase 9 - Web dyno vs worker dyno responsibility split

Goal: keep the web request path fast while still serving large feature collections.

Web dyno responsibilities:

- Small filtered GeoJSON responses.
- DRF-GIS GeoJSON responses for normal and optimized layer requests.
- Streaming DB-side GeoJSON rows only for approved last-resort medium filtered
  layer requests where tying up a WSGI worker is acceptable.
- Serving cached or precomputed artifacts directly.
- Returning `202 Accepted` for async exports.
- Returning `400` only for clearly abusive or unsupported requests.

Worker dyno responsibilities:

- Cache warmers for common scopes.
- Full-dataset or large-scope GeoJSON artifact generation.
- Simplified geometry / materialized view refresh.
- Export file generation.
- Post-deploy smoke and warmup jobs.
- Invalidation and warming after data changes.

Database responsibilities:

- Spatial filtering.
- Geometry simplification.
- Geometry-to-GeoJSON conversion only for escalated DB-side GeoJSON endpoints.
- Vector tile generation only for escalated interactive-map endpoints.
- Aggregation for summaries and dataset versions.

Important caveat: streaming is not a universal scalability answer under the
current WSGI/Gunicorn deployment model. It bounds Python memory during response
generation, but the request still occupies a web worker until the client
finishes receiving the response. Very large exports and repeatable broad scopes
should therefore be generated by workers and served as files or artifacts.

### Phase 10 - Recommended immediate next steps for the current branch

1. **Keep guardrails**
   - Treat rejection as a fallback for uncached/unsafe paths, not the desired steady state.
2. **Audit public exposure**
   - Decide for each high-cost endpoint whether it must be anonymous public, registered-user only, staff/reviewer only, or internal/worker only.
3. **Add bot and crawler protections**
   - Apply Cloudflare, DRF throttling, middleware rate limits, and cheap invalid-request handling before changing serializer architecture.
4. **Keep DRF-GIS for domain APIs and default layer delivery**
   - Do not replace DRF-GIS globally. Preserve it for CRUD, details, validation, permissions, modest payloads, and browsable API surfaces.
5. **Optimize DRF-GIS paths first**
   - Improve querysets, serializer properties, simplified geometries, caching, warmers, and bounds before replacing the transport.
6. **Bypass DRF-GIS only as a last resort**
   - Start only with endpoints that still fail after access control, bot controls, caching, bounds, and query optimization.
7. **Add a DB-side streaming GeoJSON helper only for escalated endpoints**
   - Shared utility that streams `ST_AsGeoJSON` rows as a feature collection when a route is approved for last-resort bypass.
   - Ensure the helper streams row chunks and does not hide a full `json_agg` response behind a streaming wrapper.
8. **Add worker cache warmers**
   - Especially for public map scopes and Waste Atlas defaults.
9. **Add artifact serving**
   - Serve precomputed compressed GeoJSON for common full-dataset scopes.
10. **Keep large exports async**
   - Use Celery workers and a download/status endpoint.
11. **Evaluate vector tiles only after earlier measures**
   - Use vector tiles only for high-feature-count pan/zoom maps where public-surface control, DRF-GIS optimization, streaming, and caching are still insufficient.
12. **Add observability**
   - Log feature count, point count estimate, cache hit/miss, serialization mode, duration, and response size.

## 6. Observability Checklist

Add structured logging or metrics for high-risk endpoints with at least:

- route name or endpoint family
- authenticated vs anonymous request
- query parameters relevant to bounding
- result count
- page size and export/list mode for non-GIS API list endpoints
- cache status
- response time
- response size where available
- warning when an endpoint rejects an unbounded request

Avoid logging sensitive data, tokens, credentials, or full arbitrary query strings.

## 7. Definition of Done

This roadmap is complete when:

- no public GIS endpoint can trigger unbounded full-dataset serialization through normal HTTP requests
- heavy non-GIS list/research/export endpoints cannot trigger unbounded full-dataset serialization or N+1 query storms through normal HTTP requests
- DRF-GIS remains in use for normal domain-object APIs and CRUD endpoints
- large legitimate GeoJSON responses remain on DRF-GIS where possible and are cached, bounded, warmed, or moved to async worker-generated artifacts
- DB-side GeoJSON streaming or vector tiles are used only where earlier access-control, bot-protection, caching, and DRF-GIS optimization measures are insufficient
- common public map scopes are pre-warmed or have predictable cache-miss behavior
- dynamic GeoDataset routes have explicit size, policy, and index safeguards
- registration and expensive anonymous routes have reasonable bot protection
- recurring broken-link and bad-request warning noise is cleaned up
- production logs contain enough structured context to diagnose future slow requests without relying on worker-timeout tracebacks
- critical guards have documented post-deploy production smoke checks
