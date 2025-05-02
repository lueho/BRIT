# API Overview

This section documents the main API endpoints and usage patterns in BRIT.

---

## REST API
- All core resources are exposed via Django REST Framework (DRF) endpoints.
- API root: `/api/`
- Authentication: [describe method, e.g., Token, JWT, Session]
- Example endpoints:
  - `/api/users/` — user management
  - `/api/maps/` — geospatial data
  - `/api/materials/` — materials catalog

## Usage Example
```http
GET /api/users/
Authorization: Token <your-token>
```

## OpenAPI/Swagger
- Interactive documentation available at `/api/docs/` if enabled.

---

## GraphQL (if applicable)
- [Document GraphQL endpoints if used]

---

_Last updated: 2025-05-02_
