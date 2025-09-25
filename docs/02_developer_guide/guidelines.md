# Developer Guidelines

## Build & Configuration

- Use Docker Compose for all environments (dev, test, prod).
- Manage environment variables via environment variables. For development only, use `brit/settings/.env` (never commit real secrets); ship an `.env.example` with placeholders.
- PostgreSQL with PostGIS and Redis are required.
- Run migrations and collectstatic as part of deployment.

## Initial Data & Default Objects

- All initial data creation is centralized in per-app, idempotent `ensure_initial_data()` functions (never in migrations). See [Initial Data Management](initial_data_management.md) and the ADR [Default Objects & Initial Data](../04_design_decisions/2025-05-16_default_objects_and_initial_data.madr.md).
- All ForeignKey defaults must use fetch-only helpers from their app's `utils.py` (never from `models.py`).
- These helpers only fetch, never create, and raise if missing. This pattern is required for all new development and enforced by code review.

## Creating a Superuser
```sh
docker compose exec web python manage.py createsuperuser
```

## Accessing the Application
- Application: http://localhost:8000
- Admin: http://localhost:8000/admin
- Flower (Celery monitoring): http://localhost:5555

## Production Deployment

The project is configured for deployment on Heroku:

1. **Heroku Configuration**:
   - Set all required environment variables in the Heroku dashboard.
   - Ensure PostgreSQL with PostGIS is enabled.
   - Configure Redis for caching and Celery.

2. **Deployment**:
   ```sh
   git push heroku main
   ```

## Testing Information

### Running Tests
Run tests inside the Docker container using `exec` and the test settings module:

```sh
# Run all tests (parallel, no prompts, keep DB)
docker compose exec web python manage.py test \
  --keepdb \
  --no-input \
  --parallel 4 \
  --settings=brit.settings.testrunner

# Run tests for a specific app
docker compose exec web python manage.py test utils \
  --keepdb --no-input --settings=brit.settings.testrunner

# Run a specific test class
docker compose exec web python manage.py test utils.tests.test_example.ExampleTestCase \
  --keepdb --no-input --settings=brit.settings.testrunner

# Run a specific test method
docker compose exec web python manage.py test utils.tests.test_example.ExampleTestCase.test_addition \
  --keepdb --no-input --settings=brit.settings.testrunner
```

Use `--no-input` to prevent prompts and `--keepdb` to speed up tests when no DB changes have occurred.

### Test Configuration

- Settings module: `brit/settings/testrunner.py` (sets `TESTING=True`, configures DB, sessions, middleware).
- Test runner class: `utils/tests/testrunner.py:SerialAwareTestRunner` (supports `@serial_test` and post-migrate `ensure_initial_data`).
- Static files use Django's `StaticFilesStorage` during tests; cookie consent is disabled.

Always pass the settings explicitly:

```sh
docker compose exec web python manage.py test --settings=brit.settings.testrunner
```

### Writing Tests

1. **Test Structure:**
   - Organize tests by app in a `tests` directory.
   - Each test file should focus on a specific component (models, views, forms, etc.).
   - Use descriptive method names.

2. **Base Test Classes:**
   - `TestCase`: Django's standard test case.
   - `UserLoginTestCase`: For tests requiring authentication.
   - `ViewWithPermissionsTestCase`: For permissioned views.
   - `AbstractTestCases.UserCreatedObjectCRUDViewTestCase`: For CRUD on user-created objects.

3. **Example Test:**
```python
from django.test import TestCase

class ExampleTestCase(TestCase):
    """A simple test case."""
    def test_addition(self):
        self.assertEqual(1 + 1, 2)
```

4. **Factory Boy:**
   - Used for creating test data.
   - Factories in `tests/factories.py` of each app.
   - Use `mute_signals` to prevent unwanted signals.

## Code Style
- Follow PEP 8 and enforce via Ruff.
- Use 4 spaces for indentation.
- Max line length: 88 characters (Ruff config in `pyproject.toml`).
- Use docstrings for public classes and methods.
- Template style via `djlint` (see `pyproject.toml`).

## Project Structure
- Organized into multiple Django apps:
  - `brit`: Core application and settings
  - `utils`: Shared utilities
  - `maps`: GIS and mapping
  - `case_studies`: Case studies as separate apps
  - `materials`: Material definitions
  - `distributions`: Temporal/spatial distributions
  - `users`: User management
  - `layer_manager`, `sources`, `interfaces.simucf`, `utils.file_export`, `utils.properties`

## Key Components
1. **GIS Integration:**
   - Uses GeoDjango and Leaflet; requires PostGIS.
2. **Celery Tasks:**
   - Celery for background tasks; Redis as broker.
   - Tasks in `tasks.py` of each app.
3. **User-Created Objects:**
   - Many models inherit from `UserCreatedObject`.
   - Views inherit from `UserCreatedObjectCreateView`, etc.
4. **Frontend:**
   - Bootstrap 5 for UI; Crispy Forms for forms; Bootstrap Modal Forms for dialogs.
   - Long-term goal: phase out jQuery; write new JS without jQuery unless required by dependencies.
