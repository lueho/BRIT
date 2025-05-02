# Data Flow & Request Lifecycle

This document explains how data moves through the BRIT system, from user request to response, and how background processing is handled.

## Web Request Lifecycle
1. **User Action:**
   - User interacts with the web UI or API client.
2. **Request Handling:**
   - Request is routed via Nginx (prod) or directly to Django (dev).
   - Django URL dispatcher routes to the appropriate view.
3. **View Logic:**
   - View processes input, interacts with models, and prepares data.
   - May call external APIs or perform validation.
4. **Database Access:**
   - Django ORM queries or updates PostgreSQL/PostGIS.
5. **Response:**
   - View renders a template or returns JSON (API).
   - Response sent back to the user.

## Background Tasks (Celery)
- Long-running or async tasks (e.g., imports, notifications) are queued via Celery.
- Celery workers process tasks using Redis as the broker.
- Results or status updates are stored in the database or sent to users.

## Static & Media Files
- In development: served by Django.
- In production: served by Nginx or cloud storage.

---

*For architectural context, see [../architecture.md](../architecture.md). For deployment details, see [deployment.md](deployment.md).*

_Last updated: 2025-05-02_
