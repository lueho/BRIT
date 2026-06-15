# BRIT Technical Roadmap: Platform Consolidation

This document is the agenda for the coming months of BRIT development and maintenance.
It records the findings of a full-codebase review (2026-06-09) and turns them into
prioritized workstreams. Small, self-contained defects from the same review are tracked
as GitHub issues (listed in the appendix); this file holds the architectural arcs that
must be implemented bit by bit.

Guiding goal: BRIT is a core platform that will grow for years — more domains, more
data, higher-level features. That requires a foundation in which **lower-level modules
never depend on higher-level modules**, duplication is systematically factored into the
core, and the core itself is small, safe, and fast.

---

## 1. Target architecture: the layering contract

All apps are assigned to a layer. Imports may only point downward. Upward integration
happens exclusively through registries/hooks that are *defined* in a lower layer and
*filled* by higher layers at app-startup time (`AppConfig.ready()`).

| Layer | Apps | Role |
|---|---|---|
| L0 Foundation | `utils` (object_management, properties, file_export), `users`, `brit` (settings/urls as composition root) | Generic lifecycle, permissions, exports, project plumbing. Zero domain knowledge. |
| L1 Reference | `bibliography`, `distributions`, `maps` | Shared reference data and geo core. May use L0 only. |
| L2 Domain data | `materials`, `processes` | Catalogue/measurement domains. May use L0–L1. |
| L3 Orchestration | `inventories` + `layer_manager` | Scenario tooling over datasets. May use L0–L2. |
| L4 Source domains | `sources/*` (roadside_trees, greenhouses, urban_green_spaces, waste_collection) | Pluggable inventory domains. May use L0–L3. |
| L5 Products | `waste_atlas`, `case_studies/*`, `interfaces/*` | End-user products composed from lower layers. |

**Composition-root exception:** `brit/urls.py` and `brit/settings` may reference any
layer (they assemble the deployment). Nothing else in L0 may.

**Enforcement:** the layering contract gets a CI check (import-linter or an equivalent
custom test) once the violations below are resolved, so regressions are impossible.

---

## 2. Verified layering violations (current state)

Non-test code only; test-code coupling is tracked separately in WS6.

| # | Violation | Where | Fix direction |
|---|---|---|---|
| V1 | `utils.object_management` hardcodes `waste_collection.Collection` knowledge | `utils/object_management/api_views.py:182-233`, `views.py:78,536-546`, `review_context.py:66-345` | Review-context/search-field plugin hooks; domain registers enrichers (WS1-A) |
| V2 | `utils.properties` imports `bibliography` | `utils/properties/models.py:8`, `serializers.py:3`; also `utils/forms.py:548` | Decide: promote `bibliography` to an explicit L0 dependency of properties, or invert via swappable source relation (WS1-B) |
| V3 | `utils.file_export` discovers `sources` plugins | `utils/file_export/registry_init.py` | Invert: source apps push exports into `export_registry` from their own `AppConfig.ready()` (WS1-C) |
| V4 | `maps` imports `sources.registry` | `maps/urls.py:3`, `maps/tasks.py:11`, `maps/runtime_adapters.py:12`, `maps/management/commands/warm_geojson_cache.py` | Move the *contract* (map mounts, cache warmers, runtime compatibility) into `maps`; source apps register themselves (WS1-D) |
| V5 | `maps` hardcodes domain dataset names | `maps/models.py:33-39` (`GIS_SOURCE_MODELS` incl. `WasteCollection`), legacy `GeoDataset.model_name` | Finish runtime-configuration migration, delete legacy name dispatch (WS1-D, overlaps #85) |
| V6 | `layer_manager` imports `inventories`, `materials`, `distributions` | `layer_manager/models.py:6-8` | Merge `layer_manager` into `inventories` (it is its private result store) or genericize via contenttypes (WS8) |
| V7 | `inventories` discovers algorithms via `pkgutil` over `sources` + DB dotted paths | `inventories/models.py:31-36,88-106,158-163` | Replace with the source-domain plugin registry; drop `flexibi_hamburg` aliases (WS8) |
| V8 | Sideways: `roadside_trees` imports `urban_green_spaces` | `sources/roadside_trees/models.py:4`, `inventory/algorithms.py:6` | Remove dead import; move shared Hamburg data access behind explicit interface |
| V9 | `brit.sitemap_items` imports `sources.registry` | `brit/sitemap_items.py` | Acceptable short-term (composition root); fold into the same registry pattern when WS1-D lands |

---

## 3. Workstreams

### WS1 — Enforce the dependency rule (foundation inversion)

The single most important arc. Sub-items in implementation order:

1. **A. Object-management hooks (V1).** Define in `utils.object_management` a small
   registry: `register_review_context_enricher(model_label, fn)`,
   `register_review_search_fields(model_label, [...])`, and an optional
   "update-context" hook. Move the Collection-specific serialization from
   `review_context.py`/`api_views.py`/`views.py` into
   `sources/waste_collection/review_hooks.py`, registered in its `AppConfig.ready()`.
   Outcome: the review dashboard scales to any future domain without touching utils.
2. **B. Properties/bibliography (V2).** `PropertyValue.sources` (M2M to
   `bibliography.Source`) makes `utils.properties` depend on L1. Pragmatic decision:
   declare `bibliography` a documented dependency of `utils.properties` and move both
   into L0/L1 adjacency, OR extract the sources M2M into the domain models that need
   attribution. Decide once, document in architecture.md, enforce.
3. **C. Export registry inversion (V3).** Delete `utils/file_export/registry_init.py`;
   each source app calls `register_export(...)` in its own `ready()`. The
   `sources.contracts.SourceDomainExport` dataclass moves to
   `utils.file_export.contracts` (it is a core contract, not a domain one).
4. **D. Maps/sources inversion (V4, V5).** Move the mount/warmer/runtime-compat
   contracts from `sources/registry.py` into `maps.contracts` (or a new tiny
   `core_registry`), keep discovery in `sources` but have `maps` consume only its own
   contract types via registration. Then delete `GIS_SOURCE_MODELS`,
   `LEGACY_FEATURES_API_BASENAMES`, and the deprecated `GeoDataset.model_name`
   string-dispatch (migration + data backfill to `GeoDatasetRuntimeConfiguration`).
   Existing issue #86 ("Sources plugin decoupling: finish remaining phases") is the
   umbrella; #85 (geodataset harmonization) is the data side.
5. **E. Registry robustness.** `sources/registry.py:235` runs discovery at import time.
   Move initialization to `AppConfig.ready()` with an explicit, validated lifecycle so
   a broken plugin yields a clear startup error, not an import-order heisenbug.
6. **F. Enforcement.** Add import-linter (or a dedicated test) encoding the table in
   §1, run in CI. From then on the layering is a build invariant, not a convention.

### WS2 — Harden the user-created object lifecycle (utils.object_management)

The review/publication workflow is the heart of the platform; every domain model relies
on it.

1. **Atomic state transitions.** `submit_for_review/withdraw/approve/reject/archive`
   (`utils/object_management/models.py:217-281`) are check-then-save without locking and
   call `save()` without `update_fields`. Implement compare-and-swap transitions
   (`filter(pk, publication_status=expected).update(...)` inside a transaction, or
   `select_for_update`), saving only workflow fields. Add transition tests.
2. **Single source of truth for permissions.** Permission logic is spread over
   `permissions.py` (object permission, submit/approve checks, `get_object_policy`),
   view mixins, and viewsets with double `check_object_permissions` calls. Consolidate
   into one policy module consumed by views, API, and templates; document the matrix
   (owner/moderator/staff × status × action). Verify the moderator edge case: changing
   `publication_status` of published objects they do not own.
3. **Status constants.** Replace scattered string literals (`"published"` appears in
   domain code, e.g. `sources/waste_collection/views.py:1352`) with the
   `UserCreatedObject.STATUS_*` constants / a `TextChoices` enum.
4. **Review notifications.** Five `TODO: Implement notification` markers in the
   transition methods. Design once (signal → Celery task → email/in-app), implement for
   submit/approve/reject. Complements existing issue #51 (internal reviewer comments).
5. **Review dashboard decomposition.** `ReviewDashboardView` (~400 lines) handles model
   discovery, filtering, pagination, caching. Split into collector/filter components,
   add per-model `select_related` declarations instead of silent try/except fallbacks
   (existing issues #34, #35, #37).

### WS3 — Waste Atlas consolidation

The atlas is the largest product surface and the largest concentration of duplication
(~40% of `waste_atlas` code is copy-paste variants).

1. **Publication scoping (SECURITY, first).** No `publication_status` filtering exists
   anywhere in `waste_atlas/viewsets.py` or `map_selection.py`; all 48 viewsets query
   `Collection.objects` directly, so private/review/declined data feeds public maps.
   Add a single scoped queryset helper (`published_collections()`) and use it
   everywhere; add a regression test that creates a private collection and asserts it
   never appears. (GitHub issue created — see appendix.)
2. **Config as data, not code.** `map_configs.py` (1,309 lines), `urls.py` (1,121
   lines, ~190 imports) and 48 near-identical viewsets encode what is really a table:
   *(metric, waste-category variant, country scope) → endpoint + legend*. Introduce a
   declarative `AtlasMapSpec` registry that generates routes, viewsets, and JS config.
   Target: adding a new atlas map = one spec entry. Expect to delete 2,500–3,500 lines.
3. **Aggregation unification.** Three strategies coexist for "amount per inhabitant"
   (`_get_collection_amount`, `_get_green_waste_collection_amount`,
   `_get_organic_amounts`). Unify behind one function with pluggable fallback chain
   (ACPV → CPV → derived), tested against known fixtures.
4. **Materialized-view lifecycle.** Green-waste MV work started as private
   operations SQL outside the public app repository. Move creation into a
   migration, add a `refresh_green_waste_acpvs` management command plus
   scheduled (Celery beat) refresh, and document staleness expectations.
5. **Caching & throttling.** Atlas endpoints recompute aggregations per request and use
   plain `ScopedRateThrottle` while `maps.throttling` already provides subnet-aware
   GeoJSON throttling. Cache per (country, year, prefix) with invalidation on
   collection/CPV change; align throttle classes. Related: #139, #141, #145.

### WS4 — Systematic DRY: kill the boilerplate at the source

Duplication is concentrated in three patterns; fix the pattern in L0 once, then sweep.

1. **CRUD view-set factory.** Every model spawns 8–9 nearly empty view classes
   (`materials/views.py:157-527` alone has ~56; `waste_collection/views.py:570-870`
   ~600 lines more). Provide
   `utils.object_management.views.crud_views(model, form, filterset, ...)` returning
   the standard bundle (published/private/review lists, create/detail/update/delete +
   modal variants) plus a `register_crud_urls()` helper. Migrate app by app; expect
   1,500+ lines deleted and one place to change list/detail behavior platform-wide.
2. **Source-app toolkit.** roadside_trees/greenhouses/waste_collection duplicate
   serializers/renderers/exports/routers/tasks (~45% overlap, ~500 lines). Create
   `sources/base/` (or extend utils) with the shared bases; new source domains then
   ship only models + domain logic + a plugin declaration.
3. **Importer framework.** Source-specific importer commands were extracted to
   the private `BRIT-data` tooling boundary. Continue consolidating their shared
   CLI args, API client, batching, dry-run, and value maps there. Keep only the
   generic bulk-import API/service in BRIT. The bulk-import path should suspend
   per-row derived-value signals (`signals.py:155-179`) in favor of a post-import
   batch recompute.
4. **Shared form/filter snippets.** Duplicated `image_metadata_section()`
   (materials/processes forms), repeated scope-initialization logic in filtersets —
   move to `utils.forms` / a base `FilterSet`.

### WS5 — Performance and resource conservation

1. **N+1 sweep with budget tests.** Verified hotspots: collection detail/review views
   (sources/flyers/CPV sources loops, `waste_collection/views.py:1336-1395,1614-1631`),
   sample detail + serializers (`materials/views.py:1019-1120`,
   `serializers.py:163-178`), greenhouse model properties
   (`sources/greenhouses/models.py:68-107,196-216`), inventories views. Fix with
   prefetches and add `assertNumQueries` guards so regressions fail tests.
2. **Index program.** Add migrations for: `Collection.publication_status`,
   `(valid_from, valid_until)`, CPV `(collection, property, year, is_derived)`;
   materials FKs used in filters; review composite indexes after `pg_stat_statements`
   confirmation in production.
3. **Geometry payloads.** `SimplifyPreserveTopology` exists (`maps/db_functions.py`)
   but is unused by the serializers; large-region GeoJSON ships full geometries. Wire
   simplification (optionally `?simplify=` bounded parameter) into region/catchment
   serializers and the local-relation streaming adapter; enforce
   `MAX_LOCAL_RELATION_ROWS` on streamed feature collections
   (`maps/runtime_adapters.py:265-280`). Related: #139.
4. **Cache invalidation precision.** Signals clear whole patterns
   (`region_geojson:*`) on any region save and miss `RegionAttributeValue` /
   `RegionAttributeTextValue` mutations entirely (`maps/signals.py`). Add the missing
   signals, then narrow keys (per-dataset/per-region) so warm caches survive unrelated
   edits. Related: #145.
5. **Properties that query.** `Sample.group_ids`, `Sample.components`,
   `Greenhouse.*` properties hit the DB per access; convert to methods or cached
   properties with explicit invalidation.

### WS6 — Quality gates and CI

1. **CI test workflow.** 2,294 test functions exist, but `.github/workflows/` contains
   only the asset check — nothing runs the suite. Add a workflow: PostGIS + Redis
   services, `manage.py test --parallel`, ruff check, djlint. This precedes all
   refactors above; nothing else in this roadmap is safe without it.
2. **Layering check** (from WS1-F) in the same workflow.
3. **Decouple utils tests from domain apps.** utils/object_management tests import
   waste_collection/bibliography/maps models as fixtures. Create a minimal concrete
   test app (test-only `UserCreatedObject` subclass) so foundation tests do not depend
   on domains.
4. **Targeted gap-filling** (from review): atlas publication scoping, review-workflow
   concurrency, inventory algorithms (`sources/*/inventory/algorithms.py` have zero
   tests), importer idempotency/partial-failure, cache-invalidation signals.
5. **Flaky/serial test hygiene.** Document `SerialAwareTestRunner` + `@serial_test`
   usage; fix the hardcoded test DB name (`brit/settings/testrunner.py:25,31`) to allow
   parallel local runs.

### WS7 — Settings and operational safety

Consolidated hardening (single issue with checklist; see appendix):

- `SECRET_KEY` falls back to `get_random_secret_key()` per process — sessions/CSRF
  break on every restart if the env var is missing; fail hard in production instead.
- Celery↔Redis uses `ssl.CERT_NONE`; require verification in production.
- Cache `IGNORE_EXCEPTIONS=True` hides Redis outages — keep for availability but add
  logging/metrics (`django_redis` logger) so failures are visible.
- `EMAIL_USE_SSL` is read as a raw string; `ADMINS` can become `[(None, None)]`.
- No CSP; templates rely on inline JS and several `|safe` usages
  (`utils/templates/bootstrap5/formset_base.html` etc.). Adopt django-csp in
  report-only mode, then enforce after the asset pipeline emits nonces.
- Error monitoring (Sentry or equivalent) for web + Celery; currently only
  console/mail_admins logging in production.
- Add `.env.example`; document required vs optional variables.
- `brit/urls.py` catch-all `path("<str:short_code>/", DynamicRedirectView...)`
  swallows arbitrary root paths — audit interaction with 404 handling and bots.

### WS8 — Inventories/scenario subsystem: decide, then act

The FLEXIBI-era scenario machinery (`inventories` + `layer_manager`) is functional but
carries the oldest debt: string/dotted-path dispatch from the DB, dynamic table
creation via `schema_editor` and app-registry mutation
(`layer_manager/models.py:195-264`), missing FAILED state (scenarios stuck in RUNNING
when a chord fails, `inventories/tasks.py:54-62`), commented-out methods, and 10+
design TODOs in models.

**Decision to make this quarter:** is scenario modeling a strategic feature?
- If **yes**: execute the modernization — merge layer_manager into inventories (fixes
  V6), plugin-based algorithm registration (fixes V7), Celery error handling with
  FAILED status + cleanup, replace dynamic tables with a generic results schema
  (JSONB or a fixed star schema), then build new features on top.
- If **not now**: contain it — fix only the correctness items (FAILED state, race in
  `block_running_scenario`), freeze the API, and exclude it from the layering
  enforcement allowlist with an explicit `# legacy` marker so it cannot spread.

### WS9 — Data-model integrity

- Unique constraints: manual (non-derived) CPVs per (collection, property, year) —
  derived ones already constrained; materials `Composition(sample, group)` and
  `ComponentMeasurement(sample, group, component, basis)`; investigate duplicates
  before adding (data cleanup migration).
- Nullable-FK audit on `Collection` (catchment/system/category/frequency) — extends
  existing issue #142 (collector NOT NULL); enforce at DB level after backfill.
- Decimal vs float: composition normalization converts Decimal→float→Decimal
  (`materials/composition_normalization.py:192-235`); keep Decimal end-to-end and add
  a "shares sum to 100%" invariant test (relates to bug #143).
- Rename legacy `soilcom_*` constraint names during the next touching migration (#87).

### WS10 — Documentation and hygiene

- `docs/index.md` and `mkdocs.yml` reference the deleted `04_design_decisions/` —
  fix nav; record durable design decisions in this roadmap or restore the section.
- Architecture docs: add the layering table (§1) to
  `02_developer_guide/architecture.md` once WS1 lands; document the plugin contract
  for adding a new source domain end-to-end.
- Dead-code sweep (tracked as one issue): `brit/signals.py` no-op `post_migrate`
  handler, `set_settion/get_settion` URL typos, unused
  `GeoDataSet{Published,Review,Private}FilteredMapView`, non-existent
  `patches.disable_research_metrics` import, roadside_trees dead import, EOL-marked
  classes (`AutoPermModelViewSet`, `HasModelPermission`, `FieldLabelMixin`),
  `requirements.txt` stub, tracked `.DS_Store`.

---

## 4. Sequencing

Order matters: safety first, then the inversion that everything else builds on, then
consolidation that pays compounding dividends.

**Phase 0 — Safety (immediately, days)**
1. Waste Atlas publication scoping fix + regression test (WS3.1)
2. CI workflow running the full suite + ruff (WS6.1)
3. Settings hardening checklist (WS7)
4. Atomic review-state transitions (WS2.1)

**Phase 1 — Foundation inversion (next, ~1 month)**
5. Object-management hooks; strip waste_collection out of utils (WS1-A)
6. Export-registry inversion (WS1-C) and maps/sources contract move (WS1-D start)
7. Registry init in `ready()` (WS1-E); layering check in CI (WS1-F)
8. Decide bibliography/properties placement (WS1-B); decide inventories future (WS8)

**Phase 2 — Consolidation (months 2–3)**
9. CRUD view factory + migrate materials, processes, waste_collection (WS4.1)
10. Atlas config-as-data + viewset decomposition (WS3.2–3.3)
11. N+1/index/caching program with query-budget tests (WS5)
12. Source-app toolkit + importer framework (WS4.2–4.3)

**Phase 3 — Expansion enablers (months 3–6)**
13. Finish GeoDataset runtime migration; delete legacy model_name dispatch (WS1-D end, #85/#86)
14. Inventories modernization or containment per WS8 decision
15. Review-workflow notifications + dashboard decomposition (WS2.4–2.5)
16. Documentation of the "add a new domain" golden path (WS10)

**Definition of done for the foundation:** a new source domain (models + plugin +
spec entries) can be added without modifying `utils`, `maps`, `brit` (beyond
`INSTALLED_APPS`), or any other domain app — and CI proves the layering holds.

---

## 5. Appendix: issue map

New issues from this review (created 2026-06-09):

| Issue | Topic | Workstream |
|---|---|---|
| #163 | Waste Atlas publication scoping (security) | WS3.1 |
| #164 | Atomic review-state transitions | WS2.1 |
| #165 | CI test workflow | WS6.1 |
| #166 | Settings hardening checklist | WS7 |
| #167 | Region-attribute cache invalidation | WS5.4 |
| #168 | waste_collection DB indexes | WS5.2 |
| #169 | Collection detail N+1 queries | WS5.1 |
| #170 | Manual-CPV uniqueness constraints | WS9 |
| #171 | Greenhouse algorithm crash + dead filter | WS8 |
| #172 | Scenario FAILED state / chord error handling | WS8 |
| #173 | Green-waste MV lifecycle | WS3.4 |
| #174 | Dead-code and hygiene sweep | WS10 |
| #175 | Atlas throttling alignment | WS3.5 |

Pre-existing issues this roadmap absorbs or extends: #34, #35, #37 (review dashboard),
#51 (reviewer comments), #85 (geodataset harmonization), #86 (sources plugin
decoupling), #87 (soilcom cleanup), #139/#141/#145 (GeoJSON/serialization
performance & cache warmup), #142 (collector NOT NULL), #143 (normalization bug),
#106 (legacy unit field).

_Last updated: 2026-06-09_
