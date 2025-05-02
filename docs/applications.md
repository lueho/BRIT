# Applications Overview

This section provides an overview of the main Django apps and submodules in the BRIT project.

---

## Core App: `brit/`
- Project settings, URLs, base logic, and shared utilities.
- Contains global middleware, templates, and context processors.

## Sub-Applications
- Each domain or feature area is implemented as a separate Django app.
- Examples: `users/`, `maps/`, `layer_manager/`, `inventories/`, `materials/`, etc.
- Each app should have its own README and, if complex, a dedicated documentation page.

## Adding New Apps
- Use `python manage.py startapp <name>`
- Register the app in `INSTALLED_APPS` in `brit/settings/base.py`
- Add URLs, models, admin, and views as needed
- Document app-specific logic in `docs/applications.md` or a subpage

---

For detailed documentation on each app, see the respective README in the app folder or future subpages here.

_Last updated: 2025-05-02_
