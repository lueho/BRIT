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

- [x] Obtain an up-to-date isolated database with representative collection data.
- [x] Capture SQL and `EXPLAIN (ANALYZE, BUFFERS)` for published, owned, and filtered
  lists, including later pages.
- [x] Inspect actual indexes and sorting costs; verify model/migration inheritance.
- [x] Evaluate an index matching scope and stable name/ID ordering; do not add
  `(publication_status, name, id)` blindly.
- [x] Check selected columns and joins against what the page actually renders.
- [x] Add ordering/pagination regression tests and compare repeated query plans.

### 3. Filter metadata and unnecessary counts

- [x] Replace slider `exists()` plus aggregate pairs with nullable aggregates.
- [x] Combine compatible aggregates and reuse duplicate choice queries.
- [x] Decide whether stable slider ranges should be cached; specify invalidation,
  scope handling, empty-data defaults, and acceptable freshness first.
- [x] Audit consumers of `public_count`, `private_count`, and `review_count`.
- [x] Remove unused scope counts without removing the paginator's result count.
- [x] Audit Explorer counts for appropriate caching separately.
- [x] Add query budgets and empty/zero/null/filter correctness tests.

### 4. Authenticated list and review performance

- [x] Measure anonymous, owner, moderator, and staff paths separately.
- [x] Batch or annotate per-row latest-submission/review-feedback indicators.
- [x] Preserve ownership, editor grants, and review-cycle semantics in tests.
- [x] Avoid materializing all heterogeneous review results before pagination;
  evaluate lightweight ordered IDs or a database-level union.
- [x] Verify filtering, ordering, totals, and later pages with larger datasets.

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
- [x] Make repeat-visit GeoJSON HEAD validation metadata-only (step 5a); retain
  the same endpoint, version calculation, filters, and access checks.

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

### Step 2 execution (2026-09-14)

- Step 1 merged as PR #402. Step 2 uses `fix/collection-list-query`, branched from
  the then-current `origin/main` (`7468f432`), in a separate isolated worktree.
- Loaded a production snapshot into that worktree only. The required attachment
  variable was loaded without displaying `.env` or its values. Production and
  the main development database were not modified.
- Restore completed with only the five documented missing `_heroku` event-trigger
  errors; the snapshot's application schema was already up to date.
- Snapshot: 12,503 collections, of which 3,751 were published. PostgreSQL had
  auto-analyzed the collection table before the recorded comparisons.
- Confirmed that neither the model nor the actual collection table had a name or
  publication-status index. The intermediate abstract `NamedUserCreatedObject`
  replaces `Meta` rather than inheriting the base publication-status index.
  Fixing index inheritance globally would expand this task to unrelated tables;
  the new index is deliberately collection-specific.
- The list view replaced model ordering `name, id` with `name`. Besides losing a
  unique tiebreaker, the unindexed query joined thousands of matching rows to
  catchments, regions, collectors, owners, and categories before its top-N sort.
  Those joins are needed for current row rendering; retained them and tested that
  the related fields still load in one query.
- Compared stable ordering alone, `(publication_status, name, id)`, `(name, id)`,
  and both indexes. Trial indexes were created inside transactions and rolled
  back afterwards; expected page IDs were checked against stable ordering.
- Selected **one `(name, id)` index** (`collection_name_id_idx`). It supports
  public lists and "Mine", whose owner/editor predicate spans publication states.
  The status-leading candidate alone did not accelerate "Mine". Both indexes
  improved some deeper/filter-heavy pages further, but the single index captures
  the large first-page gains with less storage and write amplification.
- The selected index occupied 1,130,496 bytes in this snapshot; the additional
  status-leading candidate would have occupied another 1,253,376 bytes.
- Implemented `CollectionListMixin.ordering = ("name", "id")` so Django applies
  stable default ordering while explicit view ordering remains respected.
- Added a non-atomic `AddIndexConcurrently` migration. It builds the index without
  the ordinary index build's write-blocking table lock. It still consumes I/O and
  can wait on concurrent transactions; monitor deployment rather than assuming it
  is instantaneous. A failed concurrent build may leave an invalid index; inspect
  before retrying, and do not silently drop/recreate it.

Three-run medians from the paired candidate experiment, in milliseconds:

| Query (10 rows/page) | Original | Stable ordering + selected index |
| --- | ---: | ---: |
| Published page 1 | 57.893 | 0.317 |
| Published page 10 | 53.978 | 1.483 |
| Published page 100 | 71.043 | 16.074 |
| Largest-owner page 1 | 68.524 | 0.444 |
| Largest-owner page 10 | 69.474 | 1.086 |
| Category + valid-on filter, page 1 | 34.200 | 0.396 |
| Category + valid-on filter, page 10 | 37.561 | 5.536 |

- Benchmarked real view querysets after `CollectionFilterSet`, using
  `request.GET` and asserting form validity. Used the most common published waste
  category and `valid_on=2024-07-01`; no object names or user identities were logged.
  A preliminary scalar-dict filter probe was excluded from this table because it
  did not validate the multiselect input correctly.
- Additional five-run selectivity checks: an owner with 81 records improved from
  45.414 to 9.384 ms; a collector-specific query was already fast and essentially
  unchanged (0.588 vs 0.638 ms, using its existing index).
- Published page 1 changed from a broad hash-join/top-N-sort plan (1,523 shared
  buffer hits) to an ordered index/nested-loop plan (97 hits), stopping after ten
  visible matches. "Mine" page 1 used 119 hits instead of 1,524. Late OFFSET pages
  still inspect and join preceding matches; keyset pagination is a separate
  potential follow-up, not part of this change.
- Timings are warm local PostgreSQL `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`
  execution times, not end-to-end or production latency. Shared-host load can
  change timings. Slider/count costs remain for step 3.
- RED: seven focused tests produced five expected failures, covering the missing
  index, missing tiebreaker in two views, and actual duplicate-name page ordering.
  GREEN: all seven passed with the implementation and migrated test database.
- Applied the migration to the isolated snapshot; PostgreSQL reports the index
  valid and ready, and no trial indexes remain. All seven final query scenarios
  selected `collection_name_id_idx` using the actual updated view/filter pipeline.
  Final three-run medians were 1.404 / 2.976 / 11.094 ms for published pages
  1 / 10 / 100; 0.416 / 2.132 ms for owned pages 1 / 10; and 0.376 / 2.032 ms for
  filtered pages 1 / 10. Buffer counts matched the candidate experiment, while
  timings varied with shared-host load. These final measurements reinforce the
  plan improvement without implying a fixed production speedup.
- Related verification: 1,573 tests completed without failures, 379 skipped.
  Ruff lint/format and the missing-migration gate passed.

### Step 3 execution (2026-09-14)

- Worktree/branch: `collection-filter-overhead` / `fix/collection-filter-overhead`.
  Started from step 2 (`0992b926` on `fix/collection-list-query`) because PR #404
  was still open. The preceding worktree and PR branch were left unchanged.
- Consolidated five slider-range calculations into three fresh aggregate queries:
  property maxima share a filtered aggregate, bin capacities/sizes share another,
  and frequency maxima aggregate the per-frequency sum of standard counts.
  Optional frequency counts remain excluded, as before.
- Range-setting helpers now receive computed maxima rather than querying the
  database independently. Missing aggregates use field defaults, zero remains a
  valid maximum, property maxima retain upward rounding, and explicit property
  range settings remain respected. Existing global range scope is unchanged.
- The regression tests also exposed an existing initialization-order problem:
  requests without `scope` can construct the form before ranges are assigned.
  Range setup now updates the actual filter/form widgets as well as widget
  configuration, so the computed metadata is not silently discarded.
- Material checkbox choices are evaluated lazily and shared only within one
  filterset instance. Both widgets reuse one result, while field validation still
  checks the queryset. New instances observe new materials, and API-only filter
  construction (`skip_min_max=True`) still performs no metadata/choice queries.
- **No cross-request slider cache was added.** Three fresh queries avoid an
  invalidation contract spanning model saves, imports, and bulk updates. A bulk
  update regression test verifies that a new filterset immediately sees changes.
- Searched all repository consumers of the three scope-count context variables.
  Their only template consumer was the unreferenced legacy scope-switcher partial.
  With explicit approval, removed the calculations, obsolete explanatory comments,
  context variables, and `brit/templates/partials/scope_switcher.html` together.
  Active buttons in `filtered_list.html` and paginator result totals are retained.
- Explorer audit: `sources.registry` already caches its public card counts for
  one hour. Collection and Materials Explorers calculate visible counts on each
  request. Those are not unused counts; left them intact. A separate cache change
  would need an agreed freshness/invalidation policy, rather than silently making
  displayed totals stale as part of this cleanup.

Verified query budgets in isolated Django tests:

| Operation | Before | After |
| --- | ---: | ---: |
| Populated slider metadata | 10 | 3 |
| Empty property/bin metadata, seeded frequency data | 6 | 3 |
| Both material checkbox widgets, first render | 2 | 1 |
| Re-rendering those widgets in the same instance | 2 | 0 |
| Anonymous shared-list context including paginator | 2 | 1 |
| Staff published/private/review context including paginator | 4 | 1 |

- A complete anonymous collection-list render with 25 fixture rows is guarded by
  a nine-query regression test (analytics disabled; RequestFactory excludes
  middleware/session loading). This is not a production timing benchmark. The
  audit's earlier 18-query observation used populated production-like metadata;
  do not equate the two datasets or infer a precise end-to-end speedup.
- RED: 11 tests reported 9 expected assertion failures and 4 missing-widget-limit
  errors, exposing duplicate work and the initialization-order defect. The same
  11 tests passed after implementation. Expanded focused coverage then passed all
  20 tests, including custom bounds and full collection-list rendering.
- Broader verification: 4,169 tests completed without failures, 861 skipped.
  After the final lint adjustment, all 20 focused tests passed again. Ruff lint,
  formatting, and missing-migration checks passed.
- Iterator detail: `list(ModelChoiceIterator)` can call its length hint and issue
  a `COUNT()` before fetching rows. `list(iter(choices))` materializes the iterator
  without that extra count. The one-query checkbox regression protects this
  behavior; no lint suppression or cross-request cache is needed.

### Step 4 execution (2026-09-14)

- Continued in the existing isolated `collection-filter-overhead` worktree because
  step 3 was still uncommitted. Step 3 changes were preserved, not overwritten or
  discarded. PR #404 (step 2) was merged by the start of this step.
- Compared anonymous, owner, non-owner moderator, and non-owner staff row-policy
  paths at page sizes 1 and 10. With permission/content-type/editor caches warmed,
  owner row loading plus feedback evaluation grew from 3 to 21 SQL queries;
  anonymous/non-owner paths stayed at one. This isolates per-row feedback work,
  not session loading, pagination, or cold authorization-cache costs.
- Added one owner-feedback batch per model represented on the selected list page.
  Only the page's owned IDs enter the annotation query. Scalar subqueries select
  the latest submission and latest non-owner, non-submission action, ordered by
  `(created_at, id)`. Comparing these pairs reproduces current review-cycle
  semantics without fetching action objects per row. The lookups match existing
  content-type/object/action index prefixes; no schema change is added.
- During review, moved annotations off the full filtered queryset and into that
  page-ID batch. This trades one extra SQL round trip for bounded feedback work,
  avoiding evaluation across all matches when filters use DISTINCT. The batch
  regression verifies its IDs exactly equal the selected page's owned IDs and
  that it does not inherit the full queryset's DISTINCT operation.
- Unpaginated map views remain lazy, and galleries that do not render feedback
  cells skip the batch. Two extra red/green tests protect those cases. Authenticated
  table pages now load rows/flags during context preparation; the paginator still
  issues only one COUNT, separately asserted in the step 3 regression.
- A SQL CASE evaluates the flag for the current owner's rows. Non-owner rows
  receive no cached boolean, and anonymous querysets are unchanged. The model
  property retains its original fallback, so direct access and detail/review
  contexts keep their existing behavior. This does not grant editors owner-only
  feedback capabilities and adds no persistent cache.
- Kept timestamp precedence, event-ID ties, resubmission resets, current ownership,
  and content-type isolation. A later owner comment does not hide earlier valid
  moderator feedback. Used scalar latest-event comparisons rather than a nested
  per-feedback-action search to avoid repeatedly locating the latest submission
  for every historical candidate action.
- Replaced the dashboard's eager collection loops with shared reference selection
  and page loading, with approval to remove/update the obsolete explanations.
  SQL applies existing per-model filters; only `(model, id, name, submitted_at)`
  references are collected and sorted. Only the selected HTML page is loaded as
  full model objects with the existing related-object joins.
- Removed the heuristic cap from HTML reference selection, so paginator totals
  and later pages cover the whole eligible queue. Kept `collect_review_items()`
  as an unpaginated compatibility path for the JSON queue, including its previous
  unfiltered per-model cap and filtered-result behavior. Both paths reuse the same
  per-model filtering, ordering, and object-loading helpers.
- Retained Python case-insensitive ordering, including Unicode, and existing
  handling of null submission dates and models without a name field. Added a
  primary-key tiebreaker to initial unfiltered per-model ordering. Avoided a SQL
  UNION/name-collation rewrite in this step to limit semantic changes.
- Object loading reuses the visibility-filtered querysets. If an item leaves
  review between reference selection and loading, it is omitted rather than
  rendered from stale metadata. In that race the page can be short and the total
  reflects the reference snapshot; this is not transactionally consistent paging.

Isolated regression observations:

| Operation | Before | After |
| --- | ---: | ---: |
| Owner, load 1 row and evaluate policy | 3 queries | 2 queries |
| Owner, load 10 rows and evaluate policies | 21 queries | 2 queries |
| Anonymous/non-owner moderator/staff, same warmed paths | 1 query | 1 query |
| Full objects loaded to display 5 filtered items | 100 | 5 |
| Unfiltered eligible total in the 100-item fixture | 60 (capped) | 100 |
| Last page in that fixture (5 items/page) | Clamped to page 12 | Page 20 |

- RED: 14 tests produced 12 expected failures (including subtests), covering query
  growth, page-object loading, truncated totals, and name sorting outside the old
  date window. The first implementation passed all 14 tests.
- Expanded focused verification passed 40 tests after the final batch refinement,
  including the new step 4 tests and earlier redirect, scope-count, and
  collection-list budgets.
- Remaining limits: metadata collection/sorting is still O(N) in matching items;
  only full-object loading is page-bounded. Database-native pagination remains a
  possible follow-up for substantially larger queues. The JSON queue's existing
  cap and per-item last-comment queries were intentionally not redesigned here.
  No production-like latency or database-work reduction is inferred solely from
  the SQL round-trip counts.
- Final broader verification: 4,415 tests completed without failures, 861 skipped.
  Ruff lint, formatting, and missing-migration checks passed. No schema or asset
  changes were needed for step 4.

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

### Step 2 (2026-09-14)

```bash
bash "$OPS/brit-tdd-preflight" "$PWD"

"$OPS/brit-worktree-up" collection-list-query --with-db-snapshot

"$OPS/brit-worktree-test" collection-list-query --print-targets -- \
  sources.waste_collection.tests.test_views.CollectionListQueryTestCase

"$OPS/brit-worktree-test" collection-list-query --parallel 1 -- \
  sources.waste_collection.tests.test_views.CollectionListQueryTestCase

"$OPS/brit-worktree-compose" collection-list-query exec -T web \
  python manage.py sqlmigrate waste_collection 0008

"$OPS/brit-worktree-compose" collection-list-query exec -T web \
  python manage.py migrate waste_collection

"$OPS/brit-worktree-compose" collection-list-query exec -T web \
  python manage.py sqlmigrate waste_collection 0008 --backwards

"$OPS/brit-worktree-test" collection-list-query -- \
  sources.waste_collection.tests.test_views \
  sources.waste_collection.tests.test_models \
  sources.waste_collection.tests.test_filters \
  utils.object_management.tests.test_views

"$OPS/brit-worktree-check" collection-list-query --no-up

git diff --check
```

- Snapshot restore requires explicit approval for the isolated database replacement
  and the documented credential environment. Do not run it over an existing
  worktree with local-only data without confirmation.
- Focused tests: RED (7 tests, 5 expected failures), then GREEN (7 tests passed).
  The isolated test database was migrated; the index test checks the actual schema.
- Forward migration SQL is `CREATE INDEX CONCURRENTLY`; reverse SQL is
  `DROP INDEX CONCURRENTLY IF EXISTS`. Applied forward on the isolated snapshot;
  inspected reverse SQL without executing it.
- Broader tests: 1,573 tests, no failures, 379 skipped, parallelism 4.
- CI-equivalent checks: lint passed, 679 Python files formatted, no missing
  migrations. No static assets changed. `git diff --check` passed.
- Query profiling ran through one-off `exec -T web python manage.py shell`
  heredocs: build real views with RequestFactory, validate a CollectionFilterSet
  using `request.GET` and `skip_min_max=True`, and call
  `queryset[offset:offset + 10].explain(analyze=True, buffers=True, format="json")`.
  Compare three repetitions per case. Offsets were 0, 90, and 990 for published
  lists, and 0 and 90 for owned and category/date-filtered lists. This measures
  page-row SQL rather than slider setup or pagination-count queries.
- Candidate indexes were tested in rollback-only transactions. No benchmark
  helper scripts, raw records, credentials, or database dumps were added to Git.
- HTTP smoke checks against the running isolated stack returned 200 for published
  collection pages 1 and 2 after migration.
- `$OPS/brit-worktree-stop collection-list-query`: completed; the stack is stopped
  and the snapshot/test volumes are preserved for the next step.
- Verification completed before PR creation. Production deployment, end-to-end
  latency measurements, and steps 3–8 remain separate follow-up work.

### Step 3 (2026-09-14)

```bash
bash "$OPS/brit-tdd-preflight" "$PWD"

"$OPS/brit-worktree-test" collection-filter-overhead \
  --base fix/collection-list-query --print-targets -- \
  sources.waste_collection.tests.test_filters.CollectionFilterMetadataTestCase \
  sources.waste_collection.tests.test_filters.CollectionFilterMetadataEmptyTestCase \
  utils.object_management.tests.test_views.SharedListScopeCountTestCase

"$OPS/brit-worktree-test" collection-filter-overhead --parallel 1 -- \
  sources.waste_collection.tests.test_filters.CollectionFilterMetadataTestCase \
  sources.waste_collection.tests.test_filters.CollectionFilterMetadataEmptyTestCase \
  utils.object_management.tests.test_views.SharedListScopeCountTestCase

"$OPS/brit-worktree-test" collection-filter-overhead --parallel 1 -- \
  sources.waste_collection.tests.test_filters.CollectionFilterMetadataTestCase \
  sources.waste_collection.tests.test_filters.CollectionFilterMetadataEmptyTestCase \
  utils.object_management.tests.test_views.SharedListScopeCountTestCase \
  sources.waste_collection.tests.test_views.CollectionListQueryTestCase

"$OPS/brit-worktree-test" collection-filter-overhead -- \
  utils.tests.test_views \
  utils.object_management.tests.test_views \
  maps.tests.test_views \
  materials.tests.test_views \
  sources.waste_collection.tests.test_views \
  sources.waste_collection.tests.test_filters \
  sources.waste_collection.tests.test_viewsets \
  bibliography.tests.test_views \
  inventories.tests.test_views \
  processes.tests.test_views

"$OPS/brit-worktree-check" collection-filter-overhead --no-up

git diff --check
git diff --cached --check
```

- Preflight and explicit target inspection passed. Tests ran against this new
  worktree's isolated test database, not the main database or the step 2 snapshot.
- Initial RED run: 11 tests, 9 expected assertion failures and 4 expected widget
  metadata errors. GREEN: all 11 passed; expanded focused suite: all 20 passed.
- Broader suite: 4,169 tests, no failures, 861 skipped. API coverage includes the
  existing lightweight `skip_min_max` paths and filter validation.
- The first lint run flagged C416 on a deliberate choice-materialization list
  comprehension. Replaced it with `list(iter(choices))`, retaining the no-count
  behavior. Gates then passed (679 Python files formatted, no missing migrations)
  and the 20 focused tests passed again against the final implementation.
- Confirmed no remaining runtime references to the removed scope-count values or
  template. Active scope controls and filtered result totals are exercised in
  rendered-response tests. No assets or migrations were added by step 3.
- `$OPS/brit-worktree-stop collection-filter-overhead`: completed; isolated
  services stopped and test database volumes preserved. The main checkout and
  preceding worktrees remain unchanged.
- Changes are not yet committed or deployed. Steps 4–8 and deployed performance
  measurements remain pending; persistent Explorer caching is a separately
  evaluated follow-up, not silently enabled here.

### Step 4 (2026-09-14)

```bash
bash "$OPS/brit-tdd-preflight" "$PWD"

"$OPS/brit-worktree-test" collection-filter-overhead --print-targets -- \
  utils.object_management.tests.test_views.OwnerReviewFeedbackQueryTests \
  utils.object_management.tests.test_views.ReviewDashboardPaginationQueryTests

"$OPS/brit-worktree-test" collection-filter-overhead --parallel 1 -- \
  utils.object_management.tests.test_views.OwnerReviewFeedbackQueryTests \
  utils.object_management.tests.test_views.ReviewDashboardPaginationQueryTests

"$OPS/brit-worktree-test" collection-filter-overhead --parallel 1 -- \
  utils.object_management.tests.test_views.OwnerReviewFeedbackQueryTests \
  utils.object_management.tests.test_views.ReviewDashboardPaginationQueryTests \
  utils.object_management.tests.test_views.SharedListScopeCountTestCase \
  utils.object_management.tests.test_views.FilterDefaultsMixinTest \
  sources.waste_collection.tests.test_views.CollectionListQueryTestCase

"$OPS/brit-worktree-test" collection-filter-overhead -- \
  utils.object_management.tests \
  utils.tests.test_views \
  maps.tests.test_views \
  materials.tests.test_views \
  sources.waste_collection.tests.test_views \
  sources.waste_collection.tests.test_filters \
  sources.waste_collection.tests.test_viewsets \
  bibliography.tests.test_views \
  inventories.tests.test_views \
  processes.tests.test_views

"$OPS/brit-worktree-check" collection-filter-overhead --no-up

git diff --check
git diff --cached --check
```

- Initial RED: 14 tests, 12 expected failures including subtests. GREEN: all 14
  passed. An initial broader run passed 4,412 tests before the page-batch refinement.
- Added and ran two more failing tests for unpaginated-view laziness and galleries
  without feedback cells; guarded the batch to fix both. Added a DISTINCT/page-ID
  regression and verified the final expanded focused suite: 40 tests passed.
- Re-ran the full listed broader selection against the final page-batched code:
  4,415 tests, no failures, 861 skipped; includes permissions, editor grants, API
  contracts, model review-cycle behavior, and representative app views.
- The date-filter test emits the same pre-existing naive-datetime warning from the
  form's dummy queryset in both RED and GREEN runs. Actual queue date filtering
  continues to use the existing per-model date lookups; warning cleanup was not
  bundled into this optimization.
- Lint/format and missing-migration checks passed. No new migrations, assets, or
  cross-request caches were added. The earlier anonymous nine-query render budget
  and zero-query default redirects remain green.
- `$OPS/brit-worktree-stop collection-filter-overhead`: completed after the final
  gates; the isolated stack is stopped and its test volumes are preserved.
- Steps 3 and 4 remain uncommitted together in this isolated worktree. Production
  deployment, browser profiling, very-large-queue SQL pagination, and steps 5–8
  remain follow-up work; the main checkout and production database were untouched.

## Step 5a: metadata-only map cache validation (2026-09-16)

### Finding and implementation

- The active feature loader in `streaming-geojson.js` validates IndexedDB entries
  with HEAD against the original GeoJSON URL. `filtered_map.html`, its iframe
  variant, and GeoDataset detail templates enable this loader. The separate
  region/catchment loader in `maps.js` already uses a version endpoint.
- The shared GeoJSON action previously constructed serializer data on small
  cache-miss HEAD requests, even though the HTTP body is discarded. Cache-hit
  HEAD responses also carried the full cached payload through response rendering.
- HEAD now returns only metadata through an empty streaming HTTP response after
  the existing filtering, count, rejection, and version checks. The empty
  iterator yields no features; the streaming response type keeps production
  `CommonMiddleware` from injecting an incorrect `Content-Length: 0` header.
  Cache hits retain their headers without response data; would-be streams do
  not build a generator. GET remains unchanged.
- A cold HEAD intentionally no longer warms the geometry cache. A subsequent GET
  still serializes and stores the actual data. On a cache hit, fetching/deserializing
  the Redis payload is still required for the existing cached feature count.
- No frontend, asset, schema, version-token, cross-request caching, permission,
  or throttling changes. The client still validates before displaying cached data.

### Evidence and verification

- The controlled two-region regression reproduced two full Region instances
  being loaded by cold HEAD before the change, versus zero afterward. This is
  an object-materialization measurement, not an end-to-end latency benchmark.
- Initial RED failures included full response data on HEAD, serializer invocation,
  and stream construction. Initial GREEN: 13 tests passed. A second RED showed
  `CommonMiddleware` adding a `Content-Length` header to the rendered empty HEAD
  body on cold and warm requests; green returned after successful HEAD switched
  to an empty streaming response.
- Affected gate: 773 tests initially, re-run at 776 tests after the streaming-HEAD
  revision; no failures, 104 skipped. Covered map views/throttling, NUTS vintage
  scoping, collection API behavior, and roadside-tree consumers.
- Ruff lint, formatting, missing-migration checks, and both staged/unstaged
  whitespace checks passed after implementation.

Commands (OPS=/home/phillipp/projects/BRIT-ops/scripts):

```bash
"$OPS/brit-worktree-test" collection-filter-overhead -- \
  maps.tests.test_views.GeoJSONHeadTests \
  sources.waste_collection.tests.test_viewsets.CollectionViewSetTestCase.test_geojson_head_preserves_scope_visibility \
  maps.tests.test_throttling.GeoJSONThrottleTests

"$OPS/brit-worktree-test" collection-filter-overhead -- \
  maps.tests.test_views maps.tests.test_throttling maps.tests.test_vintage_scoping \
  sources.waste_collection.tests.test_viewsets sources.roadside_trees.tests

"$OPS/brit-worktree-check" collection-filter-overhead --no-up
git diff --check
git diff --cached --check
```

### Remaining work and limitations

- First visible geometry, interaction readiness, bytes transferred, browser long
  tasks, and production-like version-check timings have not been measured here.
  No browser or production-latency improvement is claimed by this change.
- Progressive rendering, cancellation, logout/permission-change browser scenarios,
  and permission-isolated cached-first rendering remain unchecked roadmap work.
- Cheaper version tokens need a separate dependency audit. Existing implementations
  differ: Catchment includes Region timestamps; the default uses dataset aggregates
  or a cache-key fallback. This change preserves those mechanisms, not a claim
  that their existing invalidation coverage is complete.
- Direct Region bbox testing exposed an existing FieldError: the generic bbox
  helper selects the Python `geom` property as though it were a database field.
  Production impact was not tested, and no bbox implementation was changed here.
  A working spatial-field consumer is covered separately by the roadside-tree test.
- Steps 3, 4, and 5a remain uncommitted in the same isolated worktree. No production
  database, main-checkout file, or secret was changed. Full step 5 remains open.

Final verification after the CommonMiddleware `Content-Length` fix:

- New RED before the fix: `test_head_omits_unknown_content_length_with_common_middleware`
  failed on both cold and warm subtests (`Content-Length` present in the
  middleware-processed response). Green after successful HEAD switched to an
  empty streaming response.
- `"$OPS/brit-worktree-test" collection-filter-overhead -- maps.tests.test_views.GeoJSONHeadTests sources.waste_collection.tests.test_viewsets.CollectionViewSetTestCase.test_geojson_head_preserves_scope_visibility maps.tests.test_throttling.GeoJSONThrottleTests sources.roadside_trees.tests.test_views.HamburgRoadsideTreesMapViewTestCase.test_geojson_head_preserves_bbox_metadata`
  — 16 tests, no failures.
- `"$OPS/brit-worktree-test" collection-filter-overhead -- maps.tests.test_views maps.tests.test_throttling maps.tests.test_vintage_scoping sources.waste_collection.tests.test_viewsets sources.roadside_trees.tests`
  — 776 tests, no failures, 104 skipped.
- `"$OPS/brit-worktree-check" collection-filter-overhead --no-up`: Ruff lint,
  Ruff format check, and missing-migration checks passed.
- `git diff --check` and `git diff --cached --check` passed.
- `$OPS/brit-worktree-stop collection-filter-overhead`: completed after the final
  gates; the isolated stack is stopped and its test volumes are preserved.
