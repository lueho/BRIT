# Local Setup (Docker)

This guide explains how to set up a local BRIT development environment using Docker. All development, tests, and checks should run inside the containers.

## Prerequisites
- Docker and Docker Compose installed
- Git

## Quick start
1. Clone the repository
   ```bash
   git clone https://github.com/lueho/BRIT.git
   cd BRIT
   ```

2. Create your environment file for local development
   - Create `brit/settings/.env` with your local credentials and settings.
   - Do not commit real secrets; for production, use environment variables in the platform (Heroku, etc.).
   - The project is configured to read settings from `brit/settings/.env` in development (`DJANGO_SETTINGS_MODULE=brit.settings.local`).

3. Build and start the stack
   ```bash
   docker compose up --build
   ```
   - Services started:
     - `web` (Django app) → http://localhost:8000
     - `db` (PostgreSQL with PostGIS) → mapped to localhost:5433
     - `redis`
     - `celery` worker
     - `flower` (optional) → http://localhost:5555

4. Initialize data (optional but recommended)
   ```bash
   docker compose exec web python manage.py ensure_initial_data --show-dependencies
   ```
   - The command is implemented in `brit/management/commands/ensure_initial_data.py`.
   - It autodiscovers each app’s `ensure_initial_data()` function (in `<app>/utils.py`) and executes them in dependency order.

5. Create a superuser (for local admin login)
   ```bash
   docker compose exec web python manage.py createsuperuser
   ```

## Running management commands
Always run management commands inside the `web` container, not on the host:
```bash
docker compose exec web python manage.py check
```

## Environment & secrets
- Development: `brit/settings/.env` contains only dev‑only values. Never commit real secrets.
- Production: Secrets come from environment variables (Heroku or equivalent). Do not rely on `.env` in production.

## Build variants (dev vs. prod)
- The Dockerfile supports a build arg `INSTALL_DEV`.
- In `compose.yml`, `web.build.args.INSTALL_DEV` is set to `true`, so dev dependencies (debug toolbar, linters, docs tooling) are available locally.
- Production builds set `INSTALL_DEV=false` (see `heroku.yml`).

## Linting & formatting
Run linters inside the container. Tools are configured in `pyproject.toml`.
- Ruff (Python):
  ```bash
  docker compose exec web ruff format .
  docker compose exec web ruff check .
  ```
- Djlint (Django templates):
  ```bash
  docker compose exec web djlint --reformat --lint brit/templates utils/**/templates materials/**/templates
  ```

## Useful URLs
- App: http://localhost:8000
- Admin: http://localhost:8000/admin
- Flower (Celery monitoring): http://localhost:5555

## Troubleshooting
- View app logs:
  ```bash
  docker compose logs -f web
  ```
- Rebuild if Python dependencies changed:
  ```bash
  docker compose build web && docker compose up -d
  ```
- Database connection issues: confirm `brit/settings/.env` matches the `db` service and that the DB is healthy.
