# Developer Guidelines

## Build & Configuration

- Use Docker Compose for all environments (dev, test, prod).
- Manage environment variables in `.env` (never committed).
- PostgreSQL with PostGIS and Redis are required.
- Run migrations and collectstatic as part of deployment.

## Initial Data & Default Objects

- All initial data creation is centralized in per-app, idempotent `ensure_initial_data()` functions (never in migrations). See [Initial Data Management](initial_data_management.md).
- For deep design rationale, see [Default Objects & Initial Data ADRs](../04_design_decisions/2025-05-16_default_objects_and_initial_data.madr.md).
- All ForeignKey defaults must use fetch-only helpers from their app's `utils.py` (never from `models.py`).
- These helpers only fetch, never create, and raise if missing. See the [canonical note](../../notes/default_objects_and_initial_data_review.md) and [MADR](../../notes/02_design_decisions/2025-05-16_default_objects_and_initial_data.madr.md) for details.
- This pattern is required for all new development and enforced by code review.

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
Run tests inside Docker containers using the `run` command:

```sh
# Run all tests
docker compose run web python manage.py test

# Run tests for a specific app
docker compose run web python manage.py test utils

# Run a specific test class
docker compose run web python manage.py test utils.tests.test_example.ExampleTestCase

# Run a specific test method
docker compose run web python manage.py test utils.tests.test_example.ExampleTestCase.test_addition
```

Use `--noinput` to prevent prompts and `--keepdb` to speed up tests when no DB changes have occurred:

```sh
# Run tests with --noinput and --keepdb
docker compose run web python manage.py test --noinput --keepdb

# Run tests for a specific app with flags
docker compose run web python manage.py test utils --noinput --keepdb
```

### Test Configuration

- Uses a custom test runner: `brit/settings/testrunner.py`.
- Static files are served using Django's StaticFilesStorage.
- Cookie consent is disabled during tests.
- Tests use local settings with test-specific overrides.

To use the test runner settings:

```sh
# Run tests with test runner settings
DJANGO_SETTINGS_MODULE=brit.settings.testrunner python manage.py test

# Or with Docker
docker compose run -e DJANGO_SETTINGS_MODULE=brit.settings.testrunner web python manage.py test
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
- Follow PEP 8.
- Use 4 spaces for indentation.
- Max line length: 120 characters.
- Use docstrings for all classes and methods.

## Project Structure
- Organized into multiple Django apps:
  - `brit`: Core application and settings
  - `utils`: Shared utilities
  - `maps`: GIS and mapping
  - `case_studies`: Case studies as separate apps
  - `materials`: Material definitions
  - `distributions`: Temporal/spatial distributions
  - `users`: User management

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
   - Planned upgrade to Bootstrap 5.
   - Long-term goal: phase out jQuery; write new code with this in mind.
