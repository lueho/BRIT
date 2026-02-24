# Architecture Overview

This document provides a high-level overview of the BRIT system architecture, its major components, and how they interact.

## System Context
- BRIT is a modular Django-based web application.
- Uses PostgreSQL with PostGIS for geospatial data, Redis for caching and Celery tasks.
- Runs in Docker containers for local development and deployment.

## Major Components
- **Web Application:** Django project with multiple apps (see [Applications Overview](applications.md)).
- **Database:** PostgreSQL with PostGIS for spatial data.
- **Task Queue:** Celery with Redis as broker for background tasks.
- **Frontend:** Bootstrap 5, some jQuery (being phased out), and vanilla JS.
- **APIs:** RESTful endpoints for all major resources.

## Data Flow
- Requests enter via Nginx or directly to Django (dev).
- Django processes requests, interacts with the database, and serves responses.
- Celery handles background jobs (e.g., imports, notifications).
- Static/media files served via Nginx (prod) or Django (dev).

## Deployment
- Local: Docker Compose for all services.
- Production: Heroku (or compatible PaaS), with environment variables for configuration.

## Key Architectural Patterns
- **SCSS and Frontend Styling:**
  - The project utilizes Bootstrap 5 as its core CSS framework.
  - Customizations and theming are achieved by leveraging Bootstrap's Sass features (variables, functions, mixins).
  - The main SCSS manifest file is `brit/static/scss/brit-theme.scss`.
  - Custom SCSS partials are organized into subdirectories under `brit/static/scss/`:
    - `variables/`: For overriding Bootstrap default variables and defining custom theme variables (e.g., colors, spacing, navigation elements).
    - `components/`: For styling custom components or overriding Bootstrap component styles.
    - `layout/`: For global layout styles (e.g., page structure, authentication pages).
    - `navigation/`: For styling navigation elements like topnav and sidenav.
  - The project uses the Live Sass Compiler extension for Visual Studio Code, which automatically compiles `brit-theme.scss` to `brit-theme.css` upon changes.
- **Modular Apps:** Each domain is a separate Django app.
- **Reusable Utilities:** Shared logic in `utils/`.
- **Class-Based Views:** Preferred for clarity and extensibility.
- **Signals:** Used for decoupled event handling.
- **Canonical Initial Data & Default Objects:** All initial data and ForeignKey defaults are managed via fetch-only helpers in `utils.py` and per-app `ensure_initial_data()`. See [Initial Data Management](initial_data_management.md) and the [MADR](../04_design_decisions/2025-05-16_default_objects_and_initial_data.madr.md).

---

*For detailed data flow, see [architecture/data_flow.md](architecture/data_flow.md). For deployment, see [architecture/deployment.md](architecture/deployment.md).*

_Last updated: 2025-05-02_
