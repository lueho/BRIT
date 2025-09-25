# Testing

All tests must run inside the Docker containers. The project depends on services (PostGIS, Redis, Celery) that are only present in the compose stack. Do not run tests on the host.

## Recommended command
Use the dedicated test settings module and run in parallel workers for speed:

```bash
docker compose exec web python manage.py test \
    --keepdb \
    --no-input \
    --parallel 4 \
    --settings=brit.settings.testrunner
```

- `--keepdb` reuses the test database between runs (faster).
- `--no-input` avoids interactive prompts.
- `--parallel 4` runs tests across 4 workers; adjust to your CPU.
- `--settings=brit.settings.testrunner` loads the test configuration (see below).

## Test settings and runner
- Settings module: `brit/settings/testrunner.py`
  - Sets `TESTING=True` and configures DB, middleware, and safe email backend.
  - Uses DB-backed sessions for parallel safety.
- Test runner: `utils/tests/testrunner.py:SerialAwareTestRunner`
  - Supports `@serial_test` for classes or methods that must run serially.
  - Prints optional timing stats when `--stats` is passed.

### Parallel‑safe initial data
During test DB setup, a `post_migrate` signal in `utils/tests/testrunner.py` calls the `ensure_initial_data` management command once after migrations complete. Django then clones this populated database for parallel workers. This eliminates race conditions and missing initial data in `--parallel N` runs.

Relevant files:
- `utils/tests/testrunner.py`
- `brit/management/commands/ensure_initial_data.py`
- `brit/settings/testrunner.py`

## Running a subset
- Single app:
  ```bash
  docker compose exec web python manage.py test materials --keepdb --no-input --settings=brit.settings.testrunner
  ```
- Single module or class:
  ```bash
  docker compose exec web python manage.py test materials.tests.test_models --keepdb --no-input --settings=brit.settings.testrunner
  docker compose exec web python manage.py test materials.tests.test_models.SampleModelTests --keepdb --no-input --settings=brit.settings.testrunner
  ```

## Troubleshooting
- Ensure the stack is up: `docker compose up -d`
- If schema changed, drop the cached test DB by omitting `--keepdb` once.
- Some caching tests are marked `@serial_test` to avoid parallel race conditions; this is expected.
- Always use the test settings module; anonymous users should 302 to login in tests (middleware matters).

## Policy
- Use Django’s built‑in test runner (unittest). Pytest is not required in this project.
- All backend tests and system checks must run inside the `web` container.
