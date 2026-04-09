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

### Completed 2026-04-08

- [x] **Urban Green Spaces full re-baseline** - Production deployment and verification complete
  - Table: `flexibi_hamburg_hamburggreenareas` → `urban_green_spaces_hamburggreenareas` 
  - Migration SQL cutover executed 
  - Clean `0001_initial` baseline active 
  - 4,722 green areas verified 

### Stale documentation to update

- [x] `docs/04_design_decisions/2026-02-10_sources_consolidation_plan.md` - Updated to frame legacy labels and migration strategy as historical state
- [x] `docs/04_design_decisions/2026-02-09_module_ux_harmonization_guideline.md` - Updated current module/app references away from legacy labels
- [x] `brit/settings/settings.py` - Verified `flexibi_hamburg` was removed from active settings/runtime

### Follow-up tasks

- [x] Greenhouses migration re-baseline - Complete 2026-04-08
- [x] Waste collection (soilcom) migration re-baseline - Complete 2026-04-09 (see Appendix C)

---

## Appendix A: Greenhouses Re-baseline Procedure

**Status:** COMPLETE - Deployed, cut over, and verified 2026-04-08

### Outcome

- `greenhouses` now runs on a clean `0001_initial`
- Legacy Nantes migration records were removed during cutover
- The legacy shim app/config is no longer required
- Inventory algorithms now use `sources.greenhouses.inventory.algorithms` as the canonical module path

### Key Differences from Roadside Trees

| Aspect | Roadside Trees | Greenhouses |
|--------|---------------|-------------|
| Models | 1 (`HamburgRoadsideTrees`) | 7 models |
| Table renames | 1 | 7 (batch in single migration) |
| Dependencies | `flexibi_hamburg` | Clean `0001_initial` baseline |
| Content types | Updated via migration | Same pattern |

### Risk Considerations

- **More models** = more tables to rename in production
- **Foreign key relationships** between models must remain intact after renames
- **Test coverage** verify all 7 models work post-rename
- **Staging validation** recommended before production cutover

---

## Appendix B: Urban Green Spaces Re-baseline Procedure

**Status:** COMPLETE - Deployed and verified 2026-04-08

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

- [x] 3. **Production SQL cutover**:
   ```sql
   BEGIN;
   
   DELETE FROM django_migrations 
   WHERE app = 'urban_green_spaces' 
   AND name IN ('0001_initial', '0002_rename_hamburggreenareas_table');
   
   INSERT INTO django_migrations (app, name, applied) 
   VALUES ('urban_green_spaces', '0001_initial', NOW());
   
   COMMIT;
   ```

- [x] 4. **Deploy and verify** 
   - Smoke test passed: 4,722 green areas intact
   - Migration history clean: single `0001_initial` record

---

## Appendix C: Waste Collection (soilcom) Re-baseline Procedure

**Status:** COMPLETE - Deployed, cut over, and verified 2026-04-09

Based on the successful roadside_trees and greenhouses pattern, this module required extra coordination because it started from:

- explicit `soilcom_*` concrete table names
- several explicit `soilcom_*` many-to-many tables that needed coordinated renames
- proxy models (`CollectionCatchment`, `CollectionSeason`, `WasteFlyer`, `WasteComponent`) that needed to stay proxy-only
- a legacy `sources.legacy_soilcom` shim in settings and migrations
- runtime seams that previously recognized the `soilcom` app label

### Current State

**Current repository migration state:**

- `sources/waste_collection/migrations/0001_initial.py` is the only `waste_collection` migration
- the clean baseline has no `soilcom` dependency
- `sources.legacy_soilcom` has been removed from the repo and from Django settings

**Current canonical concrete tables:**

- `Collector` → `waste_collection_collector`
- `CollectionSystem` → `waste_collection_collectionsystem`
- `SortingMethod` → `waste_collection_sortingmethod`
- `WasteCategory` → `waste_collection_wastecategory`
- `CollectionFrequency` → `waste_collection_collectionfrequency`
- `CollectionCountOptions` → `waste_collection_collectioncountoptions`
- `FeeSystem` → `waste_collection_feesystem`
- `Collection` → `waste_collection_collection`
- `CollectionPropertyValue` → `waste_collection_collectionpropertyvalue`
- `AggregatedCollectionPropertyValue` → `waste_collection_aggregatedcollectionpropertyvalue`

**Current explicit many-to-many tables:**

- `waste_collection_collection_allowed_materials`
- `waste_collection_collection_forbidden_materials`
- `waste_collection_collection_samples`
- `waste_collection_collection_flyers`
- `waste_collection_collection_sources`
- `waste_collection_collection_predecessors`
- `waste_collection_collectionpropertyvalue_sources`
- `waste_collection_aggregatedcollectionpropertyvalue_collections`
- `waste_collection_aggregatedcollectionpropertyvalue_sources`

**Proxy models that remain proxy-only:**

- `CollectionCatchment`
- `CollectionSeason`
- `WasteFlyer`
- `WasteComponent`

**Deployment status:**

- Phase 1 rename rollout already ran on production through `waste_collection.0005_alter_aggregatedcollectionpropertyvalue_collections_and_more`
- Phase 2 clean baseline was committed as `10f71a44` and pushed to `main` and `deploy`
- Phase 3 cutover SQL was rehearsed successfully on a restored production snapshot in dev; smoke checks passed
- production cutover and deploy completed 2026-04-09; Postgres smoke checks passed
- known leftover tables `soilcom_georeferencedcollector` and `soilcom_georeferencedwastecollection` remain outside the active `waste_collection` baseline

### Procedure Steps

#### Phase 0: Preconditions

1. **Finish the remaining shim-dependent runtime cleanup before removing the legacy app label**:
   - replace or retire code paths that still expect the `soilcom` app label where they are part of the live runtime surface
   - update tests that currently assert the `sources.legacy_soilcom` shim is present
   - confirm any string-based model labels such as `soilcom.Collection` are either intentionally retained for the cutover phase or migrated to `waste_collection.Collection`

2. **Decide canonical table naming** for the new baseline:
   - use Django-default `waste_collection_<modelname>` names for the concrete `waste_collection` models
   - rename explicit many-to-many tables to `waste_collection_*` counterparts in the same rollout

#### Phase 1: Table Renames (Current Migration Graph)

3. **Update concrete model `Meta.db_table` values** in `sources/waste_collection/models.py` from `soilcom_*` to `waste_collection_*`

4. **Create a dedicated rename migration** after `0003_alter_collection_required_bin_capacity_reference.py` that:
   - renames each concrete model table under the existing graph
   - renames each explicit many-to-many table under the existing graph
   - keeps proxy models unchanged
   - preserves database state accurately for constraints and relations

   Expected renamed concrete tables:

   - `soilcom_collector` → `waste_collection_collector`
   - `soilcom_collectionsystem` → `waste_collection_collectionsystem`
   - `soilcom_sortingmethod` → `waste_collection_sortingmethod`
   - `soilcom_wastecategory` → `waste_collection_wastecategory`
   - `soilcom_collectionfrequency` → `waste_collection_collectionfrequency`
   - `soilcom_collectioncountoptions` → `waste_collection_collectioncountoptions`
   - `soilcom_feesystem` → `waste_collection_feesystem`
   - `soilcom_collection` → `waste_collection_collection`
   - `soilcom_collectionpropertyvalue` → `waste_collection_collectionpropertyvalue`
   - `soilcom_aggregatedcollectionpropertyvalue` → `waste_collection_aggregatedcollectionpropertyvalue`

   Expected renamed explicit many-to-many tables:

   - `soilcom_collection_allowed_materials` → `waste_collection_collection_allowed_materials`
   - `soilcom_collection_forbidden_materials` → `waste_collection_collection_forbidden_materials`
   - `soilcom_collection_samples` → `waste_collection_collection_samples`
   - `soilcom_collection_flyers` → `waste_collection_collection_flyers`
   - `soilcom_collection_sources` → `waste_collection_collection_sources`
   - `soilcom_collection_predecessors` → `waste_collection_collection_predecessors`
   - `soilcom_collectionpropertyvalue_sources` → `waste_collection_collectionpropertyvalue_sources`
   - `soilcom_aggregatedcollectionpropertyvalue_collections` → `waste_collection_aggregatedcollectionpropertyvalue_collections`
   - `soilcom_aggregatedcollectionpropertyvalue_sources` → `waste_collection_aggregatedcollectionpropertyvalue_sources`

5. **Update tests** that currently assert `soilcom_*` `db_table` names and shim-backed `soilcom` app-label behavior

6. **Validate on dev**:
   ```bash
   docker compose exec web python manage.py migrate waste_collection
   docker compose exec web python manage.py test sources.tests.test_models sources.waste_collection --settings=brit.settings.testrunner
   ```

7. **Deploy to production** and apply the rename migration under the current graph before any history rewrite

#### Phase 2: Clean Baseline (Post-Rename)

8. **Remove old `waste_collection` migrations** and generate a clean `0001_initial.py` once the production tables already use the `waste_collection_*` names

   Expected old migrations to retire:

   - `0001_move_legacy_models.py`
   - `0002_update_content_types.py`
   - `0003_alter_collection_required_bin_capacity_reference.py`
   - the new rename migration from Phase 1

9. **Generate the clean baseline**:
   ```bash
   docker compose exec web python manage.py makemigrations waste_collection
   ```

   The new baseline should:

   - have no `soilcom` dependency
   - point concrete models at `waste_collection_*` tables
   - keep proxy models as proxy-only state
   - encode the renamed many-to-many tables correctly

10. **Only after fresh setup works without the shim**, remove legacy `soilcom` migration wiring:
    - remove `sources.legacy_soilcom.apps.LegacySoilcomConfig` from `INSTALLED_APPS`
    - remove `"soilcom": "sources.legacy_soilcom.migrations"` from `MIGRATION_MODULES`
    - delete `sources/legacy_soilcom/`
    - update tests that currently assert shim ownership

#### Phase 3: Production Cutover

11. **Execute the `django_migrations` cutover SQL on production before deploying the clean-baseline code**.

    Preconditions:

    - production has already applied the Phase 1 rename rollout through `waste_collection.0005_alter_aggregatedcollectionpropertyvalue_collections_and_more`
    - the deploy that removes `sources.legacy_soilcom` and replaces the migration graph with `waste_collection.0001_initial` has not been released yet

    Run this recorder update in the release window immediately before the new deploy:
    ```sql
    BEGIN;

    DELETE FROM django_migrations
    WHERE app = 'waste_collection'
    AND name IN (
        '0001_move_legacy_models',
        '0002_update_content_types',
        '0003_alter_collection_required_bin_capacity_reference',
        '0004_rename_soilcom_col_publica_c5f9a3_idx_waste_colle_publica_23ad95_idx_and_more',
        '0005_alter_aggregatedcollectionpropertyvalue_collections_and_more'
    );

    DELETE FROM django_migrations
    WHERE app = 'soilcom'
    AND name IN (
        '0001_initial',
        '0002_aggregatedcollectionpropertyvalue_approved_at_and_more',
        '0003_alter_aggregatedcollectionpropertyvalue_publication_status_and_more',
        '0004_alter_collection_min_bin_size_and_required_bin_capacity',
        '0005_georeferencedcollector_and_more',
        '0006_add_is_derived_to_collectionpropertyvalue',
        '0006_alter_aggregatedcollectionpropertyvalue_publication_status_and_more',
        '0007_enforce_unique_derived_cpv',
        '0008_merge_20260217_0951',
        '0009_alter_collection_required_bin_capacity_and_more',
        '0010_add_sorting_method_and_established',
        '0011_collection_inline_waste_fields',
        '0012_remove_wastestream_model',
        '0013_move_models_to_sources'
    );

    INSERT INTO django_migrations (app, name, applied)
    VALUES ('waste_collection', '0001_initial', NOW());

    COMMIT;
    ```

12. **Deploy code** with the clean baseline and without the shim only after the cutover SQL is complete.

    Recommended release order:

    - stop any automatic migration step from the old release image
    - run the SQL above against the production database
    - deploy the new code containing only `waste_collection.0001_initial` and no `sources.legacy_soilcom`
    - run `python manage.py migrate`

    Do not leave the system in the intermediate state longer than necessary, because the old code would see the historical migration rows as missing.

13. **Smoke test**:
    ```bash
    docker compose exec web python manage.py showmigrations waste_collection
    docker compose exec web python manage.py shell -c "from sources.waste_collection.models import Collection, CollectionPropertyValue, AggregatedCollectionPropertyValue; print(Collection.objects.count(), CollectionPropertyValue.objects.count(), AggregatedCollectionPropertyValue.objects.count())"
    ```

    Snapshot rehearsal completed 2026-04-09:

    - restored production snapshot in dev accepted the cutover SQL and `python manage.py migrate`
    - `django_migrations` reduced to `waste_collection.0001_initial`
    - Postgres counts and targeted smoke tests passed

    Production verification completed 2026-04-09:

    - production `django_migrations` reduced to `waste_collection.0001_initial`
    - canonical `waste_collection_*` tables and row counts matched the rehearsal snapshot
    - sample published collections loaded normally via Postgres smoke checks

### Key Differences from Greenhouses

| Aspect | Greenhouses | Waste Collection |
|--------|-------------|------------------|
| Concrete models | 7 | 10 |
| Explicit many-to-many tables | 0 | 9 |
| Proxy models in app state | minimal | 4 important proxies |
| Current shim status | already removed | removed in repo and production |
| Cleanup prerequisite | inventory module-path data migration | post-cutover legacy artifact and documentation cleanup |

### Risk Considerations

- **More tables than greenhouses** means more rename operations to coordinate
- **Explicit many-to-many tables** add extra rename and validation surface beyond model tables
- **Fresh database setup** and production cutover are now verified, but follow-up cleanup should stay small and targeted
- **Known leftover georeferenced `soilcom_*` tables** are legacy artifacts and should not be mistaken for active schema ownership
- **Legacy `soilcom` content types and permissions** still exist for obsolete models and should be removed in a dedicated follow-up rather than bundled into the cutover

### Post-completion cleanup opportunities

**Repo/doc cleanup completed 2026-04-09:**

- updated `docs/04_design_decisions/2026-02-10_sources_consolidation_plan.md` so it records the completed migration outcome instead of the transitional shim/table strategy as the current target state
- updated `docs/04_design_decisions/2026-02-09_module_ux_harmonization_guideline.md` so `waste_collection` references the canonical `sources.waste_collection` app and current explorer structure
- updated `processes/PRODUCTION_ROADMAP.md` and `processes/SUMMARY.md` to use `waste_collection` as the active source-domain reference instead of the retired Soilcom path
- updated legacy documentation/examples in `utils/file_export/views.py` and `sources/waste_collection/ontology/README.md`
- deleted the unused `sources/waste_collection/model_definitions.py` artifact after confirming repo search found no imports of that file

**Separate follow-up migration or DB cleanup:**

- drop the empty legacy tables `soilcom_georeferencedcollector` and `soilcom_georeferencedwastecollection` only in a dedicated migration/SQL follow-up
- remove the obsolete `soilcom` content types for `georeferencedcollector`, `georeferencedwastecollection`, `wastestream`, `wastestreamallowed`, and `wastestreamcategory` together with their dependent `auth_permission` rows
- keep those content-type cleanups separate from the completed re-baseline, even though current production checks show zero `object_management_reviewaction` and zero `django_admin_log` rows for those legacy content types
