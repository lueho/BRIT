# Deployment Overview

This page describes BRIT deployment architecture and boundaries. It is not the step-by-step operations runbook.

## Scope of This Page

- **Use this page for**
  Understanding which services exist, how local and production deployments differ, and where configuration belongs.

- **Do not duplicate here**
  Release steps and runtime commands belong in [Operations](../../03_operations/operations.md).

## Local Deployment Topology

- **Application service**
  Django runs in the `web` container.

- **Database**
  PostgreSQL with PostGIS backs relational and geospatial data.

- **Background processing**
  Redis and Celery support asynchronous tasks.

- **Supporting services**
  Flower may be enabled for task monitoring.

## Production Deployment Topology

- **Application runtime**
  BRIT runs as a containerized Django application served by Gunicorn.

- **Stateful services**
  Production requires PostgreSQL with PostGIS and Redis.

- **Static assets**
  Static files are collected during release and served through the deployment platform or a dedicated static/media layer.

- **Configuration**
  Secrets and environment-specific settings must come from environment variables or platform configuration, not committed files.

## Environment Configuration

### Local Docker Compose

Copy the committed example before starting the stack:

```sh
cp brit/settings/.env.example brit/settings/.env
```

The copied file is ignored by Git. Keep real credentials only in that local file or
an external secret manager.

| Variable | Requirement | Purpose |
|---|---|---|
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Required | Create and authenticate the local PostgreSQL database. |
| `POSTGRES_HOST`, `POSTGRES_PORT` | Required | Connect Django and helper containers to PostgreSQL; the example uses `db:5432`. |
| `REDIS_URL` | Required | Back cache, sessions, and Celery; the example uses the Compose Redis service. |
| `ADMIN_USERNAME` | Required | Create or locate the administrator during initial-data setup. |
| `SECRET_KEY` | Recommended | Keep local sessions stable across process restarts. Use a development-only value. |
| `DB_HOST_PORT`, `WEB_HOST_PORT`, `UID`, `GID` | Optional | Override published ports or asset-builder file ownership in Docker Compose. |
| `TEST_REDIS_URL` | Optional | Point tests at a dedicated Redis database; test settings otherwise derive one from `REDIS_URL`. |
| Remaining example variables | Optional | Enable email, storage, bot protection, monitoring, analytics, PDF parsing, or override defaults. |

### Production

The deployment platform may inject service URLs automatically, but the following
values must exist at runtime:

| Variable | Requirement | Purpose |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | Required | Use `brit.settings.heroku` for both web and Celery processes. |
| `SECRET_KEY` | Required | Sign sessions and CSRF data; PR #280 adds fail-fast startup validation. |
| `ALLOWED_HOSTS` | Required | Comma-separated public hostnames accepted by Django. |
| `DATABASE_URL` | Required | Connect to production PostgreSQL/PostGIS. |
| `REDIS_URL` | Required | Back cache, sessions, Celery broker, and Celery results. |
| `ADMIN_USERNAME` | Required | Create or locate the administrator during initial-data setup. |
| `AWS_STORAGE_BUCKET_NAME`, `AWS_DEFAULT_REGION` | Required | Configure production static and media storage. |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Conditional | Required when the runtime does not supply an AWS role or workload identity. |

Optional production configuration:

| Variables | Purpose |
|---|---|
| `DEFAULT_OBJECT_OWNER_USERNAME` | Override the owner assigned to initial shared objects; defaults to `ADMIN_USERNAME`. |
| `ADMIN_NAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Configure error-report recipients and initial administrator details. |
| `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_PORT`, `EMAIL_USE_SSL`, `DEFAULT_FROM_EMAIL`, `SERVER_EMAIL` | Enable SMTP delivery and sender identities. |
| `TURNSTILE_SITEKEY`, `TURNSTILE_SECRET` | Enable production Cloudflare Turnstile keys for registration. |
| `SENTRY_DSN` | Enable Django and Celery error monitoring. |
| `GOOGLE_ANALYTICS_KEY` | Enable Google Analytics. |
| `SAMPLE_SUBSTRATE_CATEGORY_NAME` | Override the default `Bioresource` sample category. |
| `ENABLE_PDF_PARSING` | Enable PDF parsing when the image includes the optional dependencies. |
| `AUTO_ENQUEUE_URL_CHECKS` | Control automatic bibliography URL checks; defaults to `true`. |
| `WORKERS` | Override the container's default of three Gunicorn workers. |
| `PORT`, `DJANGO_WSGI` | Override container runtime defaults; deployment platforms normally manage these. |

Do not copy the example's placeholder values into production. Provision production
secrets through the deployment platform or a dedicated secret manager.

## Release Responsibilities

- **Development workflow**
  Code changes, tests, and migrations are prepared during normal development. See [Developer Guidelines](../guidelines.md).

- **Operations workflow**
  Release execution, runtime commands, and operational checks are described in [Operations](../../03_operations/operations.md).

- **Deployment branch**
  Deployment automation is tied to the repository workflow and the reserved `deploy` branch.

## Related Documentation

- **Architecture overview**
  See [../architecture.md](../architecture.md).

- **Data flow**
  See [data_flow.md](data_flow.md).

- **Operations runbook**
  See [../../03_operations/operations.md](../../03_operations/operations.md).

_Last updated: 2026-07-11_
