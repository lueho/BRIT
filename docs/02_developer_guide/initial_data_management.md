# Initial Data & Default Objects Management

## Overview & Motivation
BRIT centralizes default objects and initial data outside of migrations to improve migration safety, test reliability, and maintainability. Previously, initial data logic was scattered across migrations, helpers, and fixtures.

## Per-App `ensure_initial_data()` Pattern
Each app defines an idempotent `ensure_initial_data()` function in its `utils.py`. This function creates required default objects (groups, superuser, base materials, etc.). A management command `ensure_initial_data` orchestrates execution of all app routines.

## Autodiscovery Mechanism
BRIT uses Django’s AppConfig registry to discover and execute each installed app’s `ensure_initial_data()` hook. This removes the need for manual imports and prevents circular dependencies.

## Dependency Management & Sequencing
Apps declare `INITIALIZATION_DEPENDENCIES` to express ordering (e.g., materials → distributions). Dependencies must be labels of installed apps; unknown labels and circular dependencies abort with an error. The management command resolves these dependencies before invoking initialization routines. Credentials for superuser creation come from environment variables (`ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`).

## Bootstrapping a Fresh Database
`python manage.py bootstrap_database` provisions a completely empty database: it runs `migrate` followed by `ensure_initial_data`. Fresh schema setup is covered by schema-only replacement migrations (`0001_squashed_…`) for `properties`, `materials`, `waste_atlas`, `maps`, `processes`, `inventories`, `distributions`, `layer_manager`, `object_management`, `closecycle`, `population` and `waste_collection`; the required defaults that the replaced data migrations used to seed are created by the idempotent app initializers. The original migration files were removed once all retained databases had adopted the baselines; the baselines keep their `replaces` metadata so databases whose legacy histories were fully applied still adopt the replacements automatically during `migrate` without manual SQL. Databases with partially applied legacy histories can no longer be upgraded directly — restore them from a snapshot that already recorded the baseline, or migrate them fully on an older revision first. The command is idempotent, safe on existing databases, and runs automatically via the `init` service when the local Compose stack starts. The user that owns default objects comes from `DEFAULT_OBJECT_OWNER_USERNAME` and falls back to `ADMIN_USERNAME` when unset.

## Existing Databases: Bibliography Baseline Adoption

The twelve original bibliography migrations are replaced by one schema-only baseline, `bibliography.0001_squashed_0012`, which lists them in `replaces`. Dependent migrations in other apps point at the baseline.

Existing databases adopt the baseline automatically. When all twelve originals are recorded in `django_migrations`, Django treats the baseline as applied and `python manage.py migrate` (also run by the Heroku release phase and `bootstrap_database`) records the `0001_squashed_0012` row without touching the bibliography tables. Do not fake or delete migration-history rows by hand.

A database that has applied only some of the originals cannot use the baseline. Bring it up to `bibliography.0012_source_type_vocabulary` on an earlier revision first.

To verify adoption after deployment:

```sql
SELECT app, name, applied
FROM django_migrations
WHERE app = 'bibliography'
  AND name = '0001_squashed_0012';
```

Expect exactly one row.

Fresh databases apply the baseline normally during bootstrap.

`replaces` must stay until every retained database (production, staging, kept snapshots) has the baseline row. Remove it in a later cleanup change.

## Waste Atlas Baseline and Map Configuration Defaults

The 31 original `waste_atlas` migrations are replaced by the schema-only baseline `waste_atlas.0001_squashed_0027`, which creates only the two Atlas tables (`WasteAtlasMapConfiguration`, `WasteAtlasRenderingSettings`) and keeps the originals and `replaces` metadata for adoption and partial-history upgrades. All former seeding migrations are superseded by the `waste_atlas` initializer: `python manage.py ensure_initial_data --app waste_atlas` inserts the 58 current default map configurations from `initial_map_configurations.json` plus the rendering settings singleton. The initializer is idempotent and uses `get_or_create` keyed on the configuration `key` and the singleton primary key, so existing values, IDs, and `updated_at` timestamps — including deliberately emptied or customized configurations — are preserved; it restores missing defaults but never replays historical configuration updates. The Heroku release phase chains `ensure_initial_data --app waste_atlas` after `migrate`, so fresh deployments receive the defaults and existing ones receive newly added keys without touching other apps' data.

## Simplification & Refactor Lessons
Key refactor steps included:
- Extracting initialization logic from migrations into `utils.py`.
- Centralizing default-fetching helpers in `utils.py` (never in `models.py`).
- Creating a DRY management command to bootstrap data.

For canonical rationale and constraints, see the design decision record linked below.

## Per-App Examples
- See each app's `utils.py` for its `ensure_initial_data()` implementation.

## Design Decisions & References
- [MADR: Canonical Pattern for Default Objects and Initial Data](../04_design_decisions/2025-05-16_default_objects_and_initial_data.madr.md)
