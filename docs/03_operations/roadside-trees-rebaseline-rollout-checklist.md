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

- [x] `sources/legacy_flexibi_hamburg/` - Deleted
- [x] Remove `flexibi_hamburg` from `MIGRATION_MODULES` in settings - Done

### In Progress

- [x] **Urban Green Spaces table rename deployed** 2026-04-07
  - `flexibi_hamburg_hamburggreenareas` → `urban_green_spaces_hamburggreenareas`
  - Migration `0002_rename_hamburggreenareas_table.py` applied on production
  - Next: Re-baseline to clean `0001_initial` (see Appendix B)

### Stale documentation to update

- [ ] `docs/04_design_decisions/2026-02-10_sources_consolidation_plan.md` - Still references `flexibi_hamburg` extensively; should be updated to reflect completed state
- [ ] `docs/04_design_decisions/2026-02-09_module_ux_harmonization_guideline.md` - References `case_studies/flexibi_hamburg`
- [ ] `brit/settings/settings.py` - Verify `flexibi_hamburg` removed from `INSTALLED_APPS` and `MIGRATION_MODULES`

### Follow-up tasks

- [ ] Greenhouses (flexibi_nantes) migration re-baseline - see Appendix A
- [ ] Waste collection (soilcom) migration re-baseline - similar process pending

---

## Appendix A: Greenhouses (flexibi_nantes) Re-baseline Procedure

Based on the successful roadside_trees pattern. The greenhouses app has multiple models with legacy `flexibi_nantes_*` table names.

### Current State

**Models with legacy table names:**
- `NantesGreenhouses` → `flexibi_nantes_nantesgreenhouses`
- `Greenhouse` → `flexibi_nantes_greenhouse`
- `Culture` → `flexibi_nantes_culture`
- `GreenhouseGrowthCycle` → `flexibi_nantes_greenhousegrowthcycle`
- `GrowthTimeStepSet` → `flexibi_nantes_growthtimestepset`
- `GrowthShare` → `flexibi_nantes_growthshare`
- `CaseStudyBaseObjects` → `flexibi_nantes_casestudybaseobjects`

**Current migrations:**
- `0001_move_legacy_models.py` - Creates model state, depends on `flexibi_nantes`
- `0002_update_content_types.py` - Updates content types from legacy app

### Procedure Steps

#### Phase 1: Table Renames (Current Migration Graph)

1. **Update model `Meta.db_table` attributes** in `sources/greenhouses/models.py`:
   ```python
   # Pattern: greenhouses_<modelname>
   db_table = "greenhouses_nantesgreenhouses"
   db_table = "greenhouses_greenhouse"
   # ... etc for all 7 models
   ```

2. **Create rename migration** `0003_rename_greenhouses_tables.py`:
   ```python
   dependencies = [("greenhouses", "0002_update_content_types")]
   
   operations = [
       migrations.AlterModelTable(name="nantesgreenhouses", table="greenhouses_nantesgreenhouses"),
       migrations.AlterModelTable(name="greenhouse", table="greenhouses_greenhouse"),
       # ... etc for all 7 models
   ]
   ```

3. **Update tests** that assert `db_table` names

4. **Validate on dev**:
   ```bash
   docker compose exec web python manage.py migrate greenhouses
   docker compose exec web python manage.py test greenhouses --settings=brit.settings.testrunner
   ```

5. **Deploy to production** - Apply rename under current graph

#### Phase 2: Clean Baseline (Post-Rename)

6. **Remove old migrations**:
   ```bash
   rm sources/greenhouses/migrations/0001_move_legacy_models.py
   rm sources/greenhouses/migrations/0002_update_content_types.py
   rm sources/greenhouses/migrations/0003_rename_greenhouses_tables.py
   ```

7. **Generate clean baseline**:
   ```bash
   docker compose exec web python manage.py makemigrations greenhouses
   ```
   Creates `0001_initial.py` with all 7 models and new table names, no `flexibi_nantes` dependency.

8. **Remove legacy shim** from settings:
   - Remove `sources.legacy_flexibi_nantes.apps.LegacyFlexibiNantesConfig` from `INSTALLED_APPS`
   - Remove `"flexibi_nantes": "sources.legacy_flexibi_nantes.migrations"` from `MIGRATION_MODULES`
   - Delete `sources/legacy_flexibi_nantes/` directory

#### Phase 3: Production Cutover

9. **Execute SQL on production**:
   ```sql
   BEGIN;
   
   -- Remove old greenhouses migration records
   DELETE FROM django_migrations 
   WHERE app = 'greenhouses' 
   AND name IN ('0001_move_legacy_models', '0002_update_content_types', '0003_rename_greenhouses_tables');
   
   -- Remove legacy flexibi_nantes migration records (if any)
   DELETE FROM django_migrations WHERE app = 'flexibi_nantes';
   
   -- Insert new baseline
   INSERT INTO django_migrations (app, name, applied) 
   VALUES ('greenhouses', '0001_initial', NOW());
   
   COMMIT;
   ```

10. **Deploy code** with clean baseline

11. **Smoke test**:
    ```bash
    docker compose exec web python manage.py showmigrations greenhouses
    docker compose exec web python manage.py shell -c "from sources.greenhouses.models import Greenhouse; print(Greenhouse.objects.count())"
    ```

### Key Differences from Roadside Trees

| Aspect | Roadside Trees | Greenhouses |
|--------|---------------|-------------|
| Models | 1 (`HamburgRoadsideTrees`) | 7 models |
| Table renames | 1 | 7 (batch in single migration) |
| Dependencies | `flexibi_hamburg` | `flexibi_nantes` |
| Content types | Updated via migration | Same pattern |

### Risk Considerations

- **More models** = more tables to rename in production
- **Foreign key relationships** between models must remain intact after renames
- **Test coverage** verify all 7 models work post-rename
- **Staging validation** recommended before production cutover

---

## Appendix B: Urban Green Spaces Re-baseline Procedure

**Status:** Clean baseline created 2026-04-07. Production SQL cutover pending next deploy.

### Re-baseline Steps

- [x] 1. **Remove old migrations**:
   ```bash
   rm sources/urban_green_spaces/migrations/0001_initial.py
   rm sources/urban_green_spaces/migrations/0002_rename_hamburggreenareas_table.py
   ```

- [x] 2. **Generate clean baseline**:
   ```bash
   docker compose exec web python manage.py makemigrations urban_green_spaces
   ```
   Creates `0001_initial.py` with `db_table = 'urban_green_spaces_hamburggreenareas'`

- [ ] 3. **Production SQL cutover** (run BEFORE deploying this commit):
   ```sql
   BEGIN;
   
   DELETE FROM django_migrations 
   WHERE app = 'urban_green_spaces' 
   AND name IN ('0001_initial', '0002_rename_hamburggreenareas_table');
   
   INSERT INTO django_migrations (app, name, applied) 
   VALUES ('urban_green_spaces', '0001_initial', NOW());
   
   COMMIT;
   ```

- [ ] 4. **Deploy** this commit and verify
