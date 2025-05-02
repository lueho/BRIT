# Applications Overview

This document provides a summary of the core and sub-applications in the BRIT project, their responsibilities, and relationships.

## Core Applications

### brit
- Main Django project and configuration.
- Global settings, URLs, and WSGI/ASGI entry points.

### utils
- Shared utilities and helper functions used across the project.

### users
- User authentication, registration, and management.

## Domain Applications

### maps
- GIS and mapping features using GeoDjango and Leaflet.
- Handles spatial data, map views, and related models.

### materials
- Material definitions, properties, and related logic.

### distributions
- Temporal and spatial distribution models and logic.

### case_studies
- Encapsulates individual case studies as separate Django apps.
- Each case study may have its own models, views, and admin.

## Application Structure Guidelines
- Each app should have its own `models.py`, `views.py`, `admin.py`, `tests/`, and `templates/` as needed.
- Place reusable logic in `utils/` or app-specific helpers.
- Keep apps focused and modular.

---

*For detailed architecture, see [architecture.md](architecture.md). For API details, see [api.md](api.md).*

_Last updated: 2025-05-02_
