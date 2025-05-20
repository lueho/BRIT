# MADR: Canonical Pattern for Default Objects and Initial Data (2025-05-16)

## Status
Accepted

## Context
Historically, BRIT managed default objects and initial data in a fragmented manner: via migrations, scattered helpers, and ad hoc test fixtures. This led to:
- Duplication of logic and knowledge
- Inconsistent environments between dev, test, and CI
- Fragile or hidden dependencies
- Difficulty in enforcing DRY and explicit practices

Recent refactors have unified and clarified the canonical pattern for managing default objects and initial data.

## Decision

### 1. **All initial data creation is centralized in per-app `ensure_initial_data()` functions**
- Each app provides a DRY, idempotent `ensure_initial_data()` in its `utils.py`.
- No initial data is created in migrations; migrations are schema-only.
- Initialization is orchestrated by a management command that resolves dependencies via `INITIALIZATION_DEPENDENCIES`.

### 2. **Fetch-only helpers in `utils.py`**
- All helpers for fetching default objects (e.g., `get_default_owner`, `get_default_unit`, `get_default_component`, etc.) are defined in `utils.py`.
- These helpers **never create** objects; they raise a clear error if the object is missing, instructing the user to run `ensure_initial_data()`.
- ForeignKey fields with a default **must use** a fetch-only PK helper from `utils.py` (e.g., `get_default_owner_pk`).
- No such helpers remain in `models.py`.

### 3. **Tests and code must import these helpers from `utils.py`**
- No code or test should import default-fetching helpers from `models.py`.
- This is enforced by code review and CI.

### 4. **Canonical distinction between default and fallback objects**
- E.g., in `materials`, the default component ("Fresh Matter (FM)") and the fallback ("Other") are always fetched by explicit, separate helpers and manager methods.
- Tests and business logic must never conflate these roles.

### 5. **Documentation and review**
- The canonical pattern is documented in `notes/default_objects_and_initial_data_review.md`.
- This ADR is referenced in onboarding and code review checklists.

## Consequences
- DRY, explicit, and robust management of initial data and default objects
- Consistent environments across dev, test, and CI
- Reduced risk of accidental object creation or hidden dependencies
- Easier onboarding and maintenance

## Alternatives Considered
- Creating initial data in migrations (rejected: not DRY, not idempotent)
- Allowing helpers to create missing objects (rejected: hides errors, leads to inconsistent state)

## References
- `notes/default_objects_and_initial_data_review.md`
- Initial data management command and dependency resolution logic
- Code review and CI onboarding docs

---
**This pattern is now canonical and must be followed for all future development.**
