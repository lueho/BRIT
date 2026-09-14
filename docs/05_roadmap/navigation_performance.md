# Navigation performance: plan and learning log

## Goal and working agreement

Make ordinary BRIT navigation noticeably faster without changing visibility,
permissions, filter semantics, or data freshness guarantees. Prefer small,
measurable improvements over a frontend rewrite.

Track work here using `[ ]` (pending), `[-]` (in progress), and `[x]` (verified).
Record evidence, exact verification commands, and remaining limitations before
marking an implementation step complete. An implemented step is not necessarily
merged or deployed. Keep changes isolated; do not change production or the main
checkout's database to obtain benchmarks.

## Baseline audit (2026-09-14)

- [x] Inspect shared navigation, views, filters, templates, and map loading.
- [x] Make read-only requests to the existing local development instance.
- [ ] Capture representative production and isolated production-like baselines.

Observed locally, with Django Debug Toolbar enabled:

| Request | Observation |
| --- | --- |
| Collections URL without query parameters | 302 redirect after 15.40 s |
| Following `?scope=published` request | 200 after 13.72 s; 18 SQL queries, 10.73 s SQL |
| Repeat `?scope=published` request | Approximately 0.37 s; 18 SQL queries, 122.52 ms SQL |
| Repeat collection query breakdown | 10 slider queries; 2 published-count queries; 10-row list query took 87.44 ms |
| Warm Home / About requests | Approximately 37–42 ms TTFB in an earlier sample |
| Materials list | Blocked by missing local `materials_sample.datetime_precision` column |

These are individual development observations, not production benchmarks or
percentiles. The large first/repeat difference does not establish a cause;
investigate database I/O, caching, and host contention. SQL timings include
instrumentation effects. Do not infer an expected production speedup from them.

## Implementation sequence

### 1. Early default-filter redirects

- [x] Move the redirect decision ahead of `FilterView.get()` work in
  `utils/views.py::FilterDefaultsMixin`.
- [x] Add a failing test that proves the underlying view pipeline is skipped.
- [x] Assert a zero-query redirect on a representative published list.
- [x] Preserve URL encoding, path, and subclass default-filter overrides.
- [x] Preserve nonempty query strings, no-default behavior, and HEAD behavior.
- [x] Verify login and moderation checks still happen before the redirect.
- [x] Run focused tests, directly affected view tests, and CI-equivalent checks.
- [x] Record results and remaining limitations below.

Acceptance: a parameterless GET with defaults returns the same 302 Location
without constructing the filterset, paginating, or building the page context.
This step retains the existing redirect; removing that extra HTTP round trip is
not part of this first change.

### 2. Collection list query and indexes

- [ ] Obtain an up-to-date isolated database with representative collection data.
- [ ] Capture SQL and `EXPLAIN (ANALYZE, BUFFERS)` for published, owned, and filtered
  lists, including later pages.
- [ ] Inspect actual indexes and sorting costs; verify model/migration inheritance.
- [ ] Evaluate an index matching scope and stable name/ID ordering; do not add
  `(publication_status, name, id)` blindly.
- [ ] Check selected columns and joins against what the page actually renders.
- [ ] Add ordering/pagination regression tests and compare repeated query plans.

### 3. Filter metadata and unnecessary counts

- [ ] Replace slider `exists()` plus aggregate pairs with nullable aggregates.
- [ ] Combine compatible aggregates and reuse duplicate choice queries.
- [ ] Decide whether stable slider ranges should be cached; specify invalidation,
  scope handling, empty-data defaults, and acceptable freshness first.
- [ ] Audit consumers of `public_count`, `private_count`, and `review_count`.
- [ ] Remove unused scope counts without removing the paginator's result count.
- [ ] Audit Explorer counts for appropriate caching separately.
- [ ] Add query budgets and empty/zero/null/filter correctness tests.

### 4. Authenticated list and review performance

- [ ] Measure anonymous, owner, moderator, and staff paths separately.
- [ ] Batch or annotate per-row latest-submission/review-feedback indicators.
- [ ] Preserve ownership, editor grants, and review-cycle semantics in tests.
- [ ] Avoid materializing all heterogeneous review results before pagination;
  evaluate lightweight ordered IDs or a database-level union.
- [ ] Verify filtering, ordering, totals, and later pages with larger datasets.

### 5. Map loading and repeat visits

- [ ] Measure time to first visible geometry, interaction readiness, transferred
  bytes, version-check latency, and browser long tasks.
- [ ] Audit map-specific overrides before changing the shared version mechanism.
- [ ] Evaluate cheaper version tokens with complete dependency invalidation.
- [ ] Evaluate progressive rendering rather than waiting for complete GeoJSON.
- [ ] Consider cached-first rendering only where freshness permits it; private
  caches must remain permission-aware and isolated across users/sessions.
- [ ] Test filtering, cancellation, empty layers, stale data, logout, and permission
  changes. Do not weaken current visibility checks to improve caching.

### 6. Browser assets

- [ ] Capture cold and warm browser waterfalls before changing the asset stack.
- [ ] Consolidate overlapping Bootstrap/theme CSS without dropping components.
- [ ] Evaluate self-hosting fonts/assets and use a suitable font-display policy.
- [ ] Load page-specific assets only where required; inspect gallery image sizes.
- [ ] Rebuild committed assets with `make assets` and verify visual behavior,
  keyboard navigation, modals, filters, and maps.

### 7. Runtime capacity and cold-request variance

- [ ] Verify effective production Gunicorn settings, worker count, memory, and
  request queueing; Heroku's command differs from the Dockerfile command.
- [ ] Inspect database latency/I/O, connection behavior, and Redis health.
- [ ] Verify delivered compression/cache headers rather than assuming app settings
  reflect proxy/CDN behavior.
- [ ] Check contention between large map requests and ordinary HTML navigation.
- [ ] Propose capacity/configuration changes only with measurements and approval.

### 8. End-to-end verification and rollout

- [ ] Establish repeated cold/warm navigation scenarios for collections, materials,
  maps, Explorers, and review pages on representative data.
- [ ] Compare TTFB, SQL count/time, redirect count, rendering/interaction metrics,
  and p50/p95 across anonymous and authenticated roles.
- [ ] Add stable query-budget regression tests, not brittle wall-clock unit tests.
- [ ] Set performance targets from the baseline and agree on freshness trade-offs.
- [ ] Roll out small changes and compare production observations after deployment.
- [ ] Record regressions, follow-ups, and final outcomes here.

## Learnings and decisions

### Audit

- Common optimizations already exist: owner and collection relation joins,
  moderation-badge caching, hashed static assets, and long-lived asset caching.
- The shared scope-count partial has no references in the HTML templates found
  during the audit; verify non-template consumers before deleting its inputs.
- Collection API list/GeoJSON/version actions already skip slider initialization.
- Map layers are fetched concurrently, but cached geometry waits for version
  validation. The streaming parser currently renders only on completion.
- Treat local schema drift as a benchmark blocker, not proof of a production bug.

### Step 1 execution

- Branch: `fix/navigation-performance`; isolated worktree: `navigation-performance`.
- Preflight passed using the BRIT-ops TDD wrapper. Main checkout changes remain
  untouched. No shared application secret file was edited.
- `get_default_filters()` overrides in private/review lists and map galleries
  derive defaults from class/view configuration, not the filterset instance.
- The implementation only moves the call to the underlying view after the
  redirect branch. Existing docstrings, status code, Location, and HEAD semantics
  are unchanged. Authentication/moderation still execute in `dispatch()`.
- RED: the pipeline-skip assertion failed; zero-query assertions failed for all
  five representative views. GREEN: all 13 focused tests passed.
- Measured view-level redirect queries in the isolated test database:

  | View | Before | After |
  | --- | ---: | ---: |
  | Published collections | 8 | 0 |
  | Private collections (staff request) | 10 | 0 |
  | Review collections (staff request) | 10 | 0 |
  | Published dataset gallery | 2 | 0 |
  | Private dataset gallery (staff request) | 4 | 0 |

- These query budgets use RequestFactory and exclude middleware/session/user
  loading. They are not whole-request production query counts or latency claims.
  Staff requests exercise permitted private/review dispatch without permission
  lookup queries; separate tests cover anonymous and non-moderator rejection.
- The isolated test database initialized successfully without changing the stale
  main development database. Production-like latency benchmarking remains pending.

## Verification log

Commands below use the BRIT-ops scripts directory as `$OPS` and the isolated
worktree's root as the working directory.

### Step 1 (2026-09-14)

```bash
bash "$OPS/brit-tdd-preflight" "$PWD"

"$OPS/brit-worktree-test" navigation-performance --print-targets -- \
  utils.object_management.tests.test_views.FilterDefaultsMixinTest \
  utils.object_management.tests.test_views.PublishedObjectsFilterViewTestCase

"$OPS/brit-worktree-test" navigation-performance --parallel 1 -- \
  utils.object_management.tests.test_views.FilterDefaultsMixinTest \
  utils.object_management.tests.test_views.PublishedObjectsFilterViewTestCase

"$OPS/brit-worktree-test" navigation-performance -- \
  utils.tests.test_views \
  utils.object_management.tests.test_views \
  maps.tests.test_views \
  materials.tests.test_views \
  sources.waste_collection.tests.test_views \
  bibliography.tests.test_views \
  inventories.tests.test_views \
  processes.tests.test_views

"$OPS/brit-worktree-check" navigation-performance --no-up

git diff --check
```

- Preflight: passed (invoked with `bash` because the local script did not have
  executable permission).
- Explicit target printout: verified the two focused classes.
- Focused RED: 13 tests, 6 expected failures (one pipeline-skip assertion plus
  five view subtests); no unrelated failures.
- Focused GREEN: the identical 13-test command passed after the production fix
  and again after the formatting adjustments.
- Related view modules: 3,914 tests, no failures, 861 skipped; default parallelism 4.
- CI-equivalent gates: Ruff lint passed; the first formatting check reported
  three layout adjustments in the new test code. Applied only those formatting
  changes and reran the gates: 677 files formatted, lint passed, no missing
  migrations. No assets changed, so an asset rebuild was not needed.
- Whitespace check: passed. Verification completed before PR creation; merge and
  deployment remain separate rollout steps.
- `$OPS/brit-worktree-stop navigation-performance`: completed; isolated services
  stopped, with the worktree and test database volumes preserved for the next step.
- Remaining work: steps 2–8 and representative production-like timing remain
  pending. No inference of a production latency reduction is made from unit-test
  timing. The existing HTTP redirect remains in place.
