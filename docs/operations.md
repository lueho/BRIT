# Operations & Deployment

This section covers deployment, environment setup, and operational best practices for BRIT.

---

## Deployment
- Use Docker Compose for local/dev/test environments:
  ```sh
  docker compose up
  ```
- Gunicorn as the WSGI server in production:
  ```sh
  docker compose exec web gunicorn brit.wsgi
  ```

## Environment Management
- Environment variables managed via `.env` (never committed)
- Use separate settings for dev, test, and prod in `brit/settings/`

## Database
- PostgreSQL 15 with PostGIS 3.4
- Migrations via Django management commands

## Static & Media Files
- Served via Whitenoise or external storage (S3, CDN)

## Scaling
- Use multiple Gunicorn workers
- Redis for cache and Celery task queue

---

_Last updated: 2025-05-02_
