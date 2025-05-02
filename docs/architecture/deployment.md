# Deployment Architecture

This section describes the deployment setup for BRIT.

---

## Local/Development
- Use Docker Compose for local development:
  ```sh
  docker compose up
  ```
- All services (Django, PostgreSQL, Redis) run in containers
- Static and media files are mounted locally

## Production
- Gunicorn as the WSGI server
- PostgreSQL and Redis run as managed services or containers
- Static/media files served via CDN or object storage
- Environment variables managed via `.env` (never committed)

## Environment Separation
- Separate settings for dev, test, prod in `brit/settings/`
- Use `.env` files for secrets/configuration

---

## Diagram
```
+-------------------+
|    User/Client    |
+---------+---------+
          |
          v
   +------+------+
   |   Gunicorn   |
   +------+------+
          |
   +------+------+
   |   Django     |
   +------+------+
    |         |
    v         v
Postgres   Redis
(DB/GIS)  (cache/queue)
```

---

_Last updated: 2025-05-02_
