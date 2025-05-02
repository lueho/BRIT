# Architecture Overview

_Last updated: 2025-05-02_

---

## System Context
BRIT is a modular Django platform designed for extensibility and robust data management. It integrates with PostgreSQL/PostGIS, Redis, and is typically deployed using Docker Compose and Gunicorn.

**Key technologies:**
- Python 3.11, Django 5.1
- PostgreSQL 15 + PostGIS 3.4
- Redis 7 (caching, task queues)
- Gunicorn (WSGI server)
- Docker & Docker Compose

---

## High-Level Diagram
```
+-------------------------+
|      User/Browser       |
+-----------+-------------+
            |
            v
+-----------+-------------+
|       Django App        |
|  (brit + sub-apps)      |
+-----------+-------------+
            |
   +--------+--------+
   |                 |
   v                 v
PostgreSQL        Redis
(DB + GIS)   (Cache/Queue)
```

---

## Major Components
- **Core Django App (`brit/`)**: Main settings, URLs, shared logic
- **Sub-Apps**: Each feature domain as a Django app (see docs/Applications)
- **Celery**: For async/background tasks (uses Redis)
- **Static/Media**: Served via Django/Whitenoise or external storage

---

## Data Flow
1. **Web requests** handled by Gunicorn → Django
2. **Django** routes to appropriate app/view
3. **Database** access via Django ORM (PostgreSQL/PostGIS)
4. **Async tasks** dispatched via Celery/Redis
5. **Static/media** files served from static_root or CDN

---

## Deployment
- Use Docker Compose for local/dev/test environments
- Gunicorn as the WSGI server in production
- Environment-specific settings managed via `.env` (never committed)

---

## Extending the System
- Add new Django apps for new domains/features
- Use signals, Celery tasks, and custom management commands for extensibility
- Document all architecture decisions in `notes/02_design_decisions/`

---

For more details, see sub-sections on data flow, models, and deployment in this documentation.
