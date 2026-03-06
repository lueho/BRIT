# Developer Guidelines

This page is the canonical source for day-to-day development workflow in BRIT.

## Scope of This Page

- **Use this page for**
  Local setup, container usage, development commands, testing, and migration workflow.

- **Do not duplicate here**
  Detailed architecture belongs in [Architecture Overview](architecture.md). Deployment and runtime operations belong in [Operations](../03_operations/operations.md).

## Core Workflow Rules

- **Docker first**
  Run BRIT through Docker Compose.

- **Use the web container for Django commands**
  Run management commands in the `web` service.

- **Do not use host Python for app commands**
  Do not run `python manage.py ...` directly on the host when the containerized app is available.

- **Keep secrets out of the repository**
  Use `.env` for local development only and never commit it.

## Local Development

### Start the stack

```sh
docker compose up
```

### Access local services

- **Application**
  `http://localhost:8000`

- **Admin**
  `http://localhost:8000/admin`

- **Flower**
  `http://localhost:5555`

### Common Django commands

```sh
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate
docker compose exec web python manage.py shell
```

## Testing

Run tests inside Docker with the dedicated test settings.

### Default test command

```sh
docker compose exec web python manage.py test --keepdb --noinput --settings=brit.settings.testrunner --parallel 4
```

### Targeted test runs

```sh
docker compose exec web python manage.py test utils --keepdb --noinput --settings=brit.settings.testrunner --parallel 4
docker compose exec web python manage.py test utils.tests.test_example.ExampleTestCase --keepdb --noinput --settings=brit.settings.testrunner --parallel 4
docker compose exec web python manage.py test utils.tests.test_example.ExampleTestCase.test_addition --keepdb --noinput --settings=brit.settings.testrunner --parallel 4
```

### When to omit `--keepdb`

- **Use `--keepdb` by default**
  This keeps repeated test runs fast.

- **Omit `--keepdb` when the test database is suspected to be broken**
  Use a clean test database if database state or migrations look inconsistent.

## Migrations and Data Changes

- **Schema changes**
  Use Django migrations for schema changes.

- **Data changes and backfills**
  Prepare SQL to be run manually instead of shipping data migrations.

- **Initial data and default objects**
  Keep initial data creation in per-app idempotent `ensure_initial_data()` functions. See [Initial Data Management](initial_data_management.md).

- **ForeignKey defaults**
  Use fetch-only helpers from app `utils.py` modules rather than creating data from `models.py` defaults. See [Default Objects & Initial Data](../04_design_decisions/2025-05-16_default_objects_and_initial_data.madr.md).

## Code Quality

- **Formatting and linting**
  Follow Ruff formatting and linting expectations.

- **Python style**
  Follow PEP 8.

- **Docstrings**
  Add Google-style docstrings to public functions and classes.

- **Tests**
  Use Django's test framework.

## Deployment Handoff

- **Deployment path**
  BRIT is deployed through GitHub-based workflow.

- **Do not push directly to Heroku**
  Use the repository workflow that promotes changes through GitHub. The `deploy` branch is reserved for deployment automation.

- **Where deployment instructions live**
  See [Operations](../03_operations/operations.md) for canonical deployment and runtime guidance.

_Last updated: 2026-03-06_
