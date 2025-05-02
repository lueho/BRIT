# Documentation Setup: MkDocs Implementation

_Last updated: 2025-05-02_

---

## Overview
This document summarizes the implementation of MkDocs for BRIT project documentation, following the documentation structure plan.

---

## Current Setup
- **MkDocs** with Material theme installed via `requirements.txt`
- Documentation structure in `docs/` directory
- Configuration in `mkdocs.yml` in project root
- Server runs on port 8001 to avoid conflicts with Django

## Documentation Sections (Old)
- **Architecture:** System overview, data flow, models, deployment
- **Applications:** Django apps overview
- **API:** REST endpoints
- **Operations:** Deployment, environment setup
- **How-Tos:** Common tasks
- **References:** Settings, commands

## Running Documentation Server
```sh
# Start MkDocs on port 8001 (different from Django's default 8000)
mkdocs serve -a localhost:8001

# Build static site (outputs to site/ directory)
mkdocs build
```

## Future Enhancements
- Re-enable `mkdocstrings` for auto-generated API docs from Python docstrings
- Add CI/CD pipeline for automatic documentation builds
- Expand app-specific documentation
- Add diagrams and visualizations

---

## Separation of Concerns
- `docs/`: Finalized, user/developer-facing documentation
- `notes/`: Working notes, planning, research (not published)

---

## 2025-05-02 Major Documentation Reorganization

### Actions Taken
- Created new topic-based structure in `docs/`:
  - `01_user_guide/`, `02_developer_guide/`, `03_operations/`, `04_design_decisions/`, `05_reference/`
- Migrated all finalized user- and developer-facing docs from `notes/` and old `docs/` root to new locations
- Updated `mkdocs.yml` navigation to reflect new structure
- Verified build and local serve via Docker Compose
- Left all drafts, planning docs, and WIP in `notes/` as per documentation rules

### Console Warnings (2025-05-02)
- Files in old `docs/` root (e.g., `api.md`, `applications.md`, `architecture.md`, etc.) are now obsolete and excluded from nav
- `README.md` in `docs/` is excluded due to conflict with `index.md` (expected)
- Internal links to `README.md` should be updated to point to the new section overviews

### Next Steps
- Remove or archive redundant files from old `docs/` root and `notes/` that are now published
- Update onboarding and contribution docs to reference new structure
- Continue to move finalized docs from `notes/` to `docs/` as they are completed

---

This setup follows the documentation guidelines established in `notes/README.md`.
