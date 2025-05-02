# Data Flow

This section provides a detailed walkthrough of the data flow in the BRIT system.

---

## Request Lifecycle
1. **User/Client** sends HTTP request (web or API)
2. **Gunicorn** forwards the request to Django
3. **Django** processes the request via URL routing and middleware
4. **View** logic interacts with models, services, and external APIs as needed
5. **Database** queries performed via Django ORM (PostgreSQL/PostGIS)
6. **Async Tasks** (if any) are dispatched to Celery/Redis
7. **Response** is returned to the client

---

## Diagram
```
User/Browser/API
      |
      v
  Gunicorn
      |
      v
   Django
      |
      +----> Database (PostgreSQL/PostGIS)
      |
      +----> Redis (cache, Celery tasks)
      v
   Response
```

---

## Notes
- Static and media files are served directly or via CDN, not through Django in production.
- Celery tasks are used for time-consuming or background work.

_Last updated: 2025-05-02_
