# Operations & Deployment Guide

This page is the canonical source for BRIT deployment and runtime operations.

## Scope of This Page

- **Use this page for**
  Deployment flow, release preparation, runtime commands, logs, environment handling, and backup expectations.

- **Do not duplicate here**
  Day-to-day development workflow belongs in [Developer Guidelines](../02_developer_guide/guidelines.md).

## Deployment Flow

- **Source of truth**
  Deployments go through the GitHub repository workflow.

- **Reserved branch**
  The `deploy` branch triggers automatic deployment and must not be deleted.

- **Direct Heroku pushes**
  Do not push directly to Heroku from local development.

## Release Preparation

- **Review environment configuration**
  Production secrets must come from environment variables or platform configuration, never from committed `.env` files.

- **Confirm database readiness**
  Ensure PostgreSQL with PostGIS and Redis are available in the target environment.

- **Run Django release commands in the containerized app environment**
  Use the application container or release environment, not host Python.

```sh
docker compose exec web python manage.py migrate
docker compose exec web python manage.py collectstatic --noinput
```

## Environment Management

- **Local development**
  `.env` is for local development only.

- **Production**
  Store secrets in Compose, container orchestration, or platform-managed environment variables.

- **Settings separation**
  Keep development, test, and production concerns separated under `brit/settings/`.

## Runtime Operations

- **Starting local services**
  See [Developer Guidelines](../02_developer_guide/guidelines.md).

### View logs

```sh
docker compose logs web
docker compose logs celery
```

### Access monitoring

- **Flower**
  `http://localhost:5555` when enabled.

## Database Operations

- **Schema changes**
  Apply migrations through Django in the `web` container.

- **Data corrections**
  Prefer explicit SQL run manually on the target database for one-off backfills and corrections.

- **Backups**
  Back up PostgreSQL regularly in production and test restore procedures periodically.

## Operational Notes

- **Static files**
  Collect static assets as part of the release process.

- **App server**
  Use Gunicorn in production.

- **Logs**
  In production, rely on platform/container log aggregation rather than writing ad-hoc log files into the repository.

## Related Documentation

- **Development workflow**
  See [Developer Guidelines](../02_developer_guide/guidelines.md).

- **Deployment architecture context**
  See [Deployment Overview](../02_developer_guide/architecture/deployment.md).

_Last updated: 2026-03-06_
