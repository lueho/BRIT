# Operations & Deployment Guide

This guide covers essential operational tasks, deployment instructions, and environment management for BRIT.

## Deployment
- Use Docker Compose for local development and testing:
  ```sh
  docker compose up
  ```
- For production, deploy to Heroku or a compatible PaaS.
- Set all required environment variables (never commit `.env`).
- Run migrations and collectstatic as part of deployment:
  ```sh
  python manage.py migrate
  python manage.py collectstatic --noinput
  ```
- Use Gunicorn as the WSGI server in production.

## Environment Management
- Manage secrets and configuration via environment variables.
- Use `.env` only for local development; never commit it.
- Separate settings for dev, test, and prod in `brit/settings/`.

## Database
- Uses PostgreSQL with PostGIS for geospatial data.
- For local dev, DB runs as a Docker service.
- For prod, use a managed PostgreSQL/PostGIS service.
- Run migrations after any model changes.

## Monitoring & Logs
- View logs with:
  ```sh
  docker compose logs web
  ```
- Monitor Celery tasks with Flower at http://localhost:5555 (if enabled).
- In production, aggregate logs using a cloud provider or external service.

## Backups & Restore
- Regularly back up the PostgreSQL database (automate in production).
- Store backups securely and test restores periodically.

---

*For deployment details, see the [Developer Guide](../02_developer_guide/architecture/deployment.md). For troubleshooting, see the How-Tos.*

_Last updated: 2025-05-02_
