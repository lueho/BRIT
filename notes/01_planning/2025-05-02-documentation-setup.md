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

## Documentation Sections
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

This setup follows the documentation guidelines established in `notes/README.md`.
