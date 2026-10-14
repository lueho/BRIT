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
`python manage.py bootstrap_database` provisions a completely empty database: it migrates `auth`, seeds `users` and `object_management`, migrates and seeds `properties`, then applies all remaining migrations and runs every discovered initializer. The staged order exists because the legacy `materials` migration requires the default owner and the default unit to already exist. The command is idempotent, safe on existing databases, and runs automatically via the `init` service when the local Compose stack starts. The user that owns default objects comes from `DEFAULT_OBJECT_OWNER_USERNAME` and falls back to `ADMIN_USERNAME` when unset.

## Existing Databases: Bibliography Baseline Adoption

The finalized bibliography baseline is an upgrade boundary. Before deploying the version that removes the twelve original bibliography migrations, every existing database that will be retained must already have the matching schema, all twelve original data/schema migrations applied, and the `bibliography.0001_squashed_0012` entry recorded in `django_migrations`.

Complete adoption separately while running the transitional migration graph (the originals plus the baseline with `replaces`) by running `python manage.py migrate bibliography` inside the application container. Django records the replacement without recreating existing tables. A separately validated manual metadata adoption is an alternative for an already verified database; do not fake unapplied transformations.

Verify the checkpoint on the target database before deployment:

```sql
SELECT app, name, applied
FROM django_migrations
WHERE app = 'bibliography'
  AND name = '0001_squashed_0012';
```

Require exactly one row. If it is absent or duplicated, stop deployment and reconcile the migration history first. This cleaned-up revision cannot perform adoption for an old database by simply running `migrate` or `bootstrap_database`; Django checks the already-applied dependencies before it can run the new initial migration. Keep obsolete history rows if desired; do not clear the migration table. Older backups must cross the same adoption boundary before this revision can use them.

Fresh databases do not need manual adoption: the baseline is applied normally during bootstrap.

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
