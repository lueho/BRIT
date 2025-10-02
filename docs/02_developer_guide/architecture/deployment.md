# Deployment Overview

This document outlines how to deploy the BRIT project in both local and production environments.

## Local Development
- Use Docker Compose to run all services (web, db, redis, celery, etc.):
  ```sh
  docker compose up
  ```
- Services:
  - Django app (web)
  - PostgreSQL with PostGIS
  - Redis
  - Celery worker and beat
- Access the app at: http://localhost:8000

## Production Deployment
- Deploy to Heroku or any compatible PaaS.
- Set all required environment variables (never commit `.env`).
- Ensure PostgreSQL with PostGIS and Redis are provisioned.
- Run migrations and collectstatic as part of the release process:
  ```sh
  python manage.py migrate
  python manage.py collectstatic --noinput
  ```
- Use Gunicorn as the WSGI server.
- Static/media files served via Nginx or cloud storage.

## Environment Variables
- All secrets and configuration are managed via environment variables.
- Never commit sensitive data to the repository.

## CI/CD
- Use GitHub Actions or similar for automated testing and deployment.
- Run tests with `--noinput` and `--keepdb` flags for efficiency.
- Review test output before merging or releasing.

---

*For architecture context, see [../architecture.md](../architecture.md). For data flow, see [data_flow.md](data_flow.md).*

_Last updated: 2025-05-02_
