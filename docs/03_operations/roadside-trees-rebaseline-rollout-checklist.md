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

- [x] Choose the new app name and plugin slug for Hamburg green areas.
- [x] Create the new domain app structure.
- [x] Move `HamburgGreenAreas` model ownership, admin registration, and any related URLs into the new app.
- [x] Update inventory algorithms and other runtime imports that currently import `HamburgGreenAreas` from `sources.roadside_trees`.
- [x] Update tests that assume `HamburgGreenAreas` belongs to `roadside_trees`.

### 2. Pre-flight audit for the roadside tree pilot

- [x] Find and review all references to `flexibi_hamburg_*` table names.
- [x] Confirm whether any raw SQL, GIS config, exports, or management commands use the old table names directly.
- [x] Decide the final stable `db_table` names for the remaining roadside tree model(s).
- [x] Confirm whether index renaming can be deferred for the pilot.

### 3. Rename rollout under the current migration graph

- [x] Add explicit `db_table` values to the extracted green areas app and to the remaining `sources.roadside_trees` models.
- [x] Create standard forward migrations that rename the physical tables to their new app-owned names.
- [x] Ensure the migration is reversible.
- [x] Validate ORM reads, writes, filters, serializers, views, and admin behavior after the rename.

### 4. Validation on non-production environments

- [x] Run targeted Django tests in Docker for the extracted green areas app and `sources.roadside_trees`.
- [x] Run any broader regression tests needed for content types, permissions, and map/API flows.
- [x] Verify the renamed tables and indexes in the database.
- [x] Validate on a staging-like database before planning production cutover.

### 5. Production rename rollout on the existing graph

- [x] Deploy the current rename migration to production without changing the historical baseline yet.
- [x] Confirm production now uses `roadside_trees_hamburgroadsidetrees` and no longer exposes `flexibi_hamburg_hamburgroadsidetrees`.
- [x] Verify ORM reads and critical admin/runtime flows against the renamed production table.

### 6. Recreate the clean migration baseline

- [x] Replace the transitional migration histories with clean `0001_initial` files that describe the extracted and renamed schema directly.
- [x] Ensure the new baselines have no dependency on `flexibi_hamburg`.
- [x] Decide whether a small follow-up content-type migration is still needed for existing environments.
- [x] Validate that a fresh database can migrate cleanly using only the new app migration histories.

### 7. Production migration-history cutover

- [x] Write the exact production procedure for updating `django_migrations`.
- [x] Rehearse the recorder update on a restored or staging copy of production.
- [x] Define rollback steps before touching production.
- [x] Apply the production recorder fix only after the production rename, schema, and new baseline are verified.

### 8. Legacy shim removal

- [x] Remove the `flexibi_hamburg` entries from `INSTALLED_APPS` and `MIGRATION_MODULES`.
- [x] Delete `sources/legacy_flexibi_hamburg`.
- [x] Update tests that currently assert the existence of the legacy shim.
- [x] Re-run the relevant Django test scope in Docker.

## Open questions

- [x] Working app name chosen: `urban_green_spaces`. Plugin slug matches app name.
- [x] Production deployment completed 2026-04-07. Rollback window and verification steps were successful.
- [x] No direct SQL consumers outside Django identified.
- [x] Content type reconciliation handled via `0002_update_content_types` migration (now retired with clean baseline).
- [x] Migration-recorder rewrite was executed manually with verified SQL procedure.

## Progress log

- [x] Agreed on the pilot strategy: start with the Hamburg source-domain split.
- [x] Agreed that `HamburgGreenAreas` should move out of `sources.roadside_trees` first.
- [x] Working app name chosen: `urban_green_spaces`.
- [x] Extraction work completed.
- [x] Pre-flight audit completed.
- [x] Rename migration prepared.
- [x] Rename migration validated on a dev snapshot.
- [x] Production rename rollout completed.
- [x] Clean `0001_initial` created via makemigrations.
- [x] Production cutover executed (django_migrations updated).
- [x] Legacy shim removed.
- [x] Smoke tests passed.

**Status: COMPLETE - 2026-04-07**

## Post-completion cleanup

### Stale files identified for removal

- [ ] `sources/legacy_flexibi_hamburg/` - Empty directory (migrations deleted, apps.py still present)
- [ ] Remove `flexibi_hamburg` from `MIGRATION_MODULES` in settings if still present

### Stale documentation to update

- [ ] `docs/04_design_decisions/2026-02-10_sources_consolidation_plan.md` - Still references `flexibi_hamburg` extensively; should be updated to reflect completed state
- [ ] `docs/04_design_decisions/2026-02-09_module_ux_harmonization_guideline.md` - References `case_studies/flexibi_hamburg`
- [ ] `brit/settings/settings.py` - Verify `flexibi_hamburg` removed from `INSTALLED_APPS` and `MIGRATION_MODULES`

### Follow-up tasks

- [ ] Greenhouses (flexibi_nantes) migration re-baseline - similar process pending
- [ ] Waste collection (soilcom) migration re-baseline - similar process pending
