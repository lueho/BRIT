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
- **Frontend:** Bootstrap 4, some jQuery (being phased out), and vanilla JS.
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
- **Modular Apps:** Each domain is a separate Django app.
- **Reusable Utilities:** Shared logic in `utils/`.
- **Class-Based Views:** Preferred for clarity and extensibility.
- **Signals:** Used for decoupled event handling.
- **Canonical Initial Data & Default Objects:** All initial data and ForeignKey defaults are managed via fetch-only helpers in `utils.py` and per-app `ensure_initial_data()`. See the [canonical note](../../notes/default_objects_and_initial_data_review.md) and [MADR](../../notes/02_design_decisions/2025-05-16_default_objects_and_initial_data.madr.md).

---

*For detailed data flow, see [architecture/data_flow.md](architecture/data_flow.md). For deployment, see [architecture/deployment.md](architecture/deployment.md).*

_Last updated: 2025-05-02_
