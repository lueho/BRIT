# API Overview

This document describes the main API endpoints and usage patterns for the BRIT project.

## Principles
- All APIs use RESTful conventions and JSON for data exchange.
- Authentication is required for most endpoints (token or session-based).
- Use standard HTTP methods: GET, POST, PUT/PATCH, DELETE.

## Main Endpoints
- `/api/`: Root for all API endpoints.
- `/api/users/`: User registration, login, profile management.
- `/api/maps/`: Access to spatial data, features, and map layers.
- `/api/materials/`: Material definitions and queries.
- `/api/distributions/`: Distribution data and queries.

## Example Usage

**Get all materials:**
```http
GET /api/materials/
Authorization: Token <token>
```

**Create a new map feature:**
```http
POST /api/maps/features/
Content-Type: application/json
Authorization: Token <token>
{
  "name": "New Feature",
  "geometry": {...},
  ...
}
```

## Authentication
- Obtain a token via login endpoint or use session authentication.
- Include `Authorization: Token <token>` header for authenticated requests.

## Error Handling
- Standard HTTP status codes are used.
- Error responses include a message and details.

## Best Practices
- Paginate large result sets.
- Validate all input data.
- Handle errors gracefully on the client side.

---

_Last updated: 2025-05-02_
