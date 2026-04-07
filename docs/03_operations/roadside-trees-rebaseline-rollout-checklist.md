# Roadside Trees Rebaseline Rollout Checklist

## Objective

Restructure the Hamburg source domains so that:

- `HamburgGreenAreas` is extracted from `sources.roadside_trees` into its own domain app
- the remaining roadside tree tables are owned and named consistently with `sources.roadside_trees`
- the long-term migration history lives cleanly in the new domain apps
- the legacy `flexibi_hamburg` migration shim can be retired after a controlled cutover

## Current decision

Start by extracting `HamburgGreenAreas` from `sources.roadside_trees` into its own domain app.

Chosen sequence:

1. Create a dedicated Hamburg green areas domain app and move `HamburgGreenAreas` ownership there while the current migration graph is still active.
2. Validate that extraction on dev and staging, including inventory and admin flows.
3. Rename the remaining `flexibi_hamburg_*` roadside-tree tables to `roadside_trees_*`.
4. Deploy and apply that rename on production under the current migration graph.
5. Recreate a clean `0001_initial` in the new Hamburg domain apps that matches the extracted and renamed schema.
6. Update the production `django_migrations` table as part of the migration-history cutover.
7. Remove the `flexibi_hamburg` legacy shim only after the new baselines are proven.

## Scope

In scope:

- `sources.roadside_trees`
- new Hamburg green areas domain app
- `sources/legacy_flexibi_hamburg`
- related Django migration settings and migration history
- related content type and permission validation

Out of scope for this pilot:

- `sources.greenhouses`
- `sources.waste_collection`
- index renaming unless it becomes necessary
- broader legacy compatibility cleanup outside the roadside trees path

## Success criteria

- `HamburgGreenAreas` no longer lives in `sources.roadside_trees`.
- The new Hamburg green areas app has clear ownership of its model, admin, URLs, and plugin metadata as needed.
- `roadside_trees` models point at stable `roadside_trees_*` table names.
- No runtime code depends on `flexibi_hamburg_*` physical table names.
- Existing environments can apply the table rename without data loss.
- Production can apply the current-graph rename before any migration-history rewrite begins.
- Fresh environments can bootstrap from clean migration baselines in the new Hamburg domain apps.
- Production migration history can be updated in a controlled and reversible way.
- The `flexibi_hamburg` shim is no longer required after cutover.

## Work plan

### 1. Extract `HamburgGreenAreas` into its own domain app

- [ ] Choose the new app name and plugin slug for Hamburg green areas.
- [ ] Create the new domain app structure.
- [ ] Move `HamburgGreenAreas` model ownership, admin registration, and any related URLs into the new app.
- [ ] Update inventory algorithms and other runtime imports that currently import `HamburgGreenAreas` from `sources.roadside_trees`.
- [ ] Update tests that assume `HamburgGreenAreas` belongs to `roadside_trees`.

### 2. Pre-flight audit for the roadside tree pilot

- [ ] Find and review all references to `flexibi_hamburg_*` table names.
- [ ] Confirm whether any raw SQL, GIS config, exports, or management commands use the old table names directly.
- [ ] Decide the final stable `db_table` names for the remaining roadside tree model(s).
- [ ] Confirm whether index renaming can be deferred for the pilot.

### 3. Rename rollout under the current migration graph

- [ ] Add explicit `db_table` values to the extracted green areas app and to the remaining `sources.roadside_trees` models.
- [ ] Create standard forward migrations that rename the physical tables to their new app-owned names.
- [ ] Ensure the migration is reversible.
- [ ] Validate ORM reads, writes, filters, serializers, views, and admin behavior after the rename.

### 4. Validation on non-production environments

- [ ] Run targeted Django tests in Docker for the extracted green areas app and `sources.roadside_trees`.
- [ ] Run any broader regression tests needed for content types, permissions, and map/API flows.
- [ ] Verify the renamed tables and indexes in the database.
- [ ] Validate on a staging-like database before planning production cutover.

### 5. Production rename rollout on the existing graph

- [ ] Deploy the current rename migration to production without changing the historical baseline yet.
- [ ] Confirm production now uses `roadside_trees_hamburgroadsidetrees` and no longer exposes `flexibi_hamburg_hamburgroadsidetrees`.
- [ ] Verify ORM reads and critical admin/runtime flows against the renamed production table.

### 6. Recreate the clean migration baseline

- [ ] Replace the transitional migration histories with clean `0001_initial` files that describe the extracted and renamed schema directly.
- [ ] Ensure the new baselines have no dependency on `flexibi_hamburg`.
- [ ] Decide whether a small follow-up content-type migration is still needed for existing environments.
- [ ] Validate that a fresh database can migrate cleanly using only the new app migration histories.

### 7. Production migration-history cutover

- [ ] Write the exact production procedure for updating `django_migrations`.
- [ ] Rehearse the recorder update on a restored or staging copy of production.
- [ ] Define rollback steps before touching production.
- [ ] Apply the production recorder fix only after the production rename, schema, and new baseline are verified.

### 8. Legacy shim removal

- [ ] Remove the `flexibi_hamburg` entries from `INSTALLED_APPS` and `MIGRATION_MODULES`.
- [ ] Delete `sources/legacy_flexibi_hamburg`.
- [ ] Update tests that currently assert the existence of the legacy shim.
- [ ] Re-run the relevant Django test scope in Docker.

## Open questions

- Working app name chosen: `urban_green_spaces`. Remaining question: whether the plugin slug should match exactly or use a shorter public slug.
- Confirm the production deployment window and rollback procedure for applying the rename migration before the rebaseline cutover.
- Are there any direct SQL consumers outside Django that must be migrated at the same time?
- Should content type reconciliation remain automated in the final history, or be handled as a one-time operational cutover step?
- How much of the production migration-recorder rewrite can be automated safely?

## Progress log

- [x] Agreed on the pilot strategy: start with the Hamburg source-domain split.
- [x] Agreed that `HamburgGreenAreas` should move out of `sources.roadside_trees` first.
- [x] Working app name chosen: `urban_green_spaces`.
- [x] Extraction work started.
- [x] Pre-flight audit completed.
- [x] Rename migration prepared.
- [x] Rename migration validated on a dev snapshot.
- [~] Production rename rollout in progress (deployed 2026-04-07, awaiting verification).
- [ ] Clean `0001_initial` drafted.
- [ ] Production cutover procedure drafted.
- [ ] Legacy shim removed.
