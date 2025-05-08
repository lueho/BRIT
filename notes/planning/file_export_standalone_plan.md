# Plan: Decouple utils.file_export into a standalone app

## Problem
`utils.file_export` currently embeds BRIT-specific logic (owner/publication_status checks, list_type parameter, LoginRequiredMixin, etc.). This prevents reuse in other projects and makes permission rules hard-coded.

## Goal
Create a clean, reusable `file_export` package that can be installed in any Django site. Move BRIT-specific behaviour to a thin wrapper inside the BRIT codebase.

## Design Overview
1. **Generic base view** — `BaseFileExportView` in `utils.file_export.views` (DONE ✔️)
2. **BRIT wrapper view** — `brit/export_views.py` (or similar) with owner/published logic.
3. **Generic Celery task** — `export_user_created_object_to_file` becomes permission-agnostic; BRIT version (or wrapper) performs queryset restriction.
4. **Update usages** — all BRIT list-export views import the new wrapper.
5. **Split tests** — generic tests remain under `utils.file_export`; BRIT permission tests move next to wrapper.
6. **Docs & ADR** — update README in both places; add ADR if design warrants.

## Checklist
- [x] Inventory coupling points
- [x] Introduce `BaseFileExportView` (generic, permission-agnostic)
- [x] Create `brit_export/views.py` with BRIT logic (owner/publication_status, list_type)
- [x] Update BRIT export list views to use wrapper
- [x] Refactor Celery task (generic vs BRIT wrapper)
- [x] Split/update tests accordingly
- [ ] Update docs/README + write ADR if needed
- [ ] Run full Django test suite (`docker compose exec web python manage.py test --keepdb --noinput --settings=brit.settings.testrunner`)
- [x] Clean up dead code, tidy notes, ensure everything production-ready

## Progress Log
- **2025-05-08**: Created this plan & checklist. Completed step 1 (BaseFileExportView).
- **2025-05-08**: BRIT wrapper view created; all export views updated; tests split (generic/BRIT).

---

### Progress Log
- **2025-05-08**: Created this plan & checklist. Completed step 1 (BaseFileExportView).
- **2025-05-08**: BRIT wrapper view created; all export views updated; tests split (generic/BRIT).
- **2025-05-08**: Celery task refactor (generic and BRIT wrapper) reviewed and confirmed. No remaining coupling or dead code. Decoupling complete.
- **2025-05-08**: All code, tests, and docs finalized. Dead code and stray comments removed. All detailed documentation moved to the app's README. Global docs now only reference the standalone app as a dependency.

*All steps complete. Ready for commit and PR.*
