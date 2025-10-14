# Initial Data & Default Objects Management

## Overview & Motivation
BRIT centralizes default objects and initial data outside of migrations to improve migration safety, test reliability, and maintainability. Previously, initial data logic was scattered across migrations, helpers, and fixtures (see notes/default_objects_and_initial_data_review.md).

## Per-App `ensure_initial_data()` Pattern
Each app defines an idempotent `ensure_initial_data()` function in its `utils.py`. This function creates required default objects (groups, superuser, base materials, etc.). A management command `ensure_initial_data` orchestrates execution of all app routines.

## Autodiscovery Mechanism
BRIT uses Django’s AppConfig registry to discover and execute each installed app’s `ensure_initial_data()` hook. This removes the need for manual imports and prevents circular dependencies.

## Dependency Management & Sequencing
Apps declare `INITIALIZATION_DEPENDENCIES` to express ordering (e.g., materials → distributions). The management command resolves these dependencies before invoking initialization routines. Credentials for superuser creation come from environment variables (`ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`).

## Simplification & Refactor Lessons
Key refactor steps included:
- Extracting initialization logic from migrations into `utils.py` (see initial_data_refactor.md).
- Centralizing default-fetching helpers in `utils.py` (never in `models.py`).
- Creating a DRY management command to bootstrap data.

For full details, see:
- `docs/initial_data_simplification_plan.md`
- `docs/initial_data_refactor_completion.md`

## Per-App Examples
- [Users Initialization Refactor](../users_initial_data_refactor.md)
- [Utils Initialization Refactor](../utils_initial_data_refactor.md)

## Design Decisions & References
- [MADR: Canonical Pattern for Default Objects and Initial Data](../04_design_decisions/2025-05-16_default_objects_and_initial_data.madr.md)
- [MADR: Initial Data and Test Refactor](../04_design_decisions/2025-05-16_initial_data_and_tests_refactor.madr.md)
- [MADR: Avoiding Circular Imports for Default Objects and Initial Data](../04_design_decisions/2025-05-19_circular_imports_initial_data.madr.md)
