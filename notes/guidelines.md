# BRIT Project Development Guidelines

This document provides essential information for developers working on the BRIT (Bioresource Inventory Tool) project.

## Build/Configuration Instructions

### Local Development Setup

1. **Prerequisites**:
   - Docker and Docker Compose
   - Git

2. **Environment Configuration**:
   - Copy the example environment file: `cp brit/settings/.env.example brit/settings/.env`
   - Update the environment variables in `.env` with your local configuration
   - Key environment variables include:
     - Database credentials (POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD)
     - Redis URL
     - AWS S3 credentials (if using S3 for storage)

3. **Building and Starting the Application**:
   ```bash
   # Build and start all services
   docker-compose up -d

   # Run migrations
   docker-compose exec web python manage.py migrate

   # Create a superuser
   docker-compose exec web python manage.py createsuperuser
   ```

4. **Accessing the Application**:
   - The application will be available at http://localhost:8000
   - The Django admin interface is at http://localhost:8000/admin
   - Flower (Celery monitoring) is available at http://localhost:5555

### Production Deployment

The project is configured for deployment on Heroku:

1. **Heroku Configuration**:
   - Set all required environment variables in Heroku dashboard
   - Ensure the PostgreSQL with PostGIS extension is enabled
   - Configure Redis for caching and Celery

2. **Deployment**:
   ```bash
   git push heroku main
   ```

## Testing Information

### Running Tests

Tests must be run inside the Docker container using the `run` command:

```bash
# Run all tests
docker-compose run web python manage.py test

# Run tests for a specific app
docker-compose run web python manage.py test utils

# Run a specific test class
docker-compose run web python manage.py test utils.tests.test_example.ExampleTestCase

# Run a specific test method
docker-compose run web python manage.py test utils.tests.test_example.ExampleTestCase.test_addition
```

When running tests, it's recommended to use the `--noinput` flag to prevent interactive prompts and the `--keepdb` flag when no database changes have been made in the last commit to speed up test execution:

```bash
# Run tests with --noinput and --keepdb flags
docker-compose run web python manage.py test --noinput --keepdb

# Run tests for a specific app with flags
docker-compose run web python manage.py test utils --noinput --keepdb
```

### Test Configuration

The project uses a custom test runner configured in `brit/settings/testrunner.py`. When running tests:

- Static files are served using Django's standard StaticFilesStorage
- Cookie consent is disabled
- Tests use the local settings with specific overrides for testing

To use the special settings file for tests, you can set the DJANGO_SETTINGS_MODULE environment variable:

```bash
# Run tests with the test runner settings
DJANGO_SETTINGS_MODULE=brit.settings.testrunner python manage.py test

# Or with Docker
docker-compose run -e DJANGO_SETTINGS_MODULE=brit.settings.testrunner web python manage.py test
```

The testrunner.py settings file imports all settings from the local configuration and then applies specific overrides needed for testing.

### Writing Tests

1. **Test Structure**:
   - Tests are organized by app in a `tests` directory
   - Each test file should focus on a specific component (models, views, forms, etc.)
   - Use descriptive test method names that explain what is being tested

2. **Base Test Classes**:
   - `TestCase`: Django's standard test case
   - `UserLoginTestCase`: For tests requiring user authentication
   - `ViewWithPermissionsTestCase`: For testing views with permission requirements
   - `AbstractTestCases.UserCreatedObjectCRUDViewTestCase`: For testing CRUD operations on user-created objects

3. **Example Test**:
   ```python
   from django.test import TestCase

   class ExampleTestCase(TestCase):
       """
       A simple test case to demonstrate how to write tests in this project.
       """

       def test_addition(self):
           """Test that 1 + 1 = 2"""
           self.assertEqual(1 + 1, 2)
   ```

4. **Factory Boy**:
   - The project uses Factory Boy for creating test data
   - Factory classes are typically defined in `tests/factories.py` within each app
   - Use `mute_signals` from Factory Boy when creating objects to prevent unwanted signal processing

## Additional Development Information

### Code Style

- The project follows PEP 8 style guidelines for Python code
- Use 4 spaces for indentation
- Maximum line length is 120 characters
- Use docstrings for all classes and methods

### Project Structure

- The project is organized into multiple Django apps:
  - `brit`: Core application and settings
  - `utils`: Shared utilities and common functionality
  - `maps`: GIS and mapping functionality
  - `case_studies`: Different case studies as separate apps
  - `materials`: Material definitions and properties
  - `distributions`: Temporal and spatial distributions
  - `users`: User management

### Key Components

1. **GIS Integration**:
   - The project uses GeoDjango for GIS functionality
   - Leaflet is used for map visualization
   - PostGIS is required for the database

2. **Celery Tasks**:
   - Celery is used for background task processing
   - Tasks are defined in `tasks.py` files within each app
   - Redis is used as the message broker

3. **User-Created Objects**:
   - Many models inherit from `UserCreatedObject` which provides ownership and publication status
   - Views for these objects typically inherit from `UserCreatedObjectCreateView`, `UserCreatedObjectDetailView`, etc.

4. **Frontend**:
   - Bootstrap 4 is used for UI components
   - Crispy Forms is used for form rendering
   - Bootstrap Modal Forms is used for modal dialogs
   - There is a planned upgrade to Bootstrap 5
   - In the long run, we aim to phase out jQuery
   - All new code should be written with these future changes in mind

5. **Utils App Components**:
   - **Core Models**:
     - `CRUDUrlsMixin`: Provides URL generation methods for CRUD operations
     - `GlobalObject`: Base model for globally accessible objects
     - `UserCreatedObject`: Base model for objects created by users with publication status
     - `NamedUserCreatedObject`: Extension of UserCreatedObject with a name field
     - `Redirect`: Model for handling redirects

   - **Views**:
     - List views: `PublishedObjectListView`, `PrivateObjectListView`, `FilterView` variants
     - CRUD views: `UserCreatedObjectCreateView`, `DetailView`, `UpdateView`, `DeleteView`
     - Modal views: Modal versions of CRUD operations
     - Access control mixins: `UserCreatedObjectReadAccessMixin`, `UserCreatedObjectWriteAccessMixin`
     - Utility views: `ModelSelectOptionsView`, `DynamicRedirectView`

   - **Forms**:
     - Base forms: `SimpleForm`, `SimpleModelForm`
     - Modal forms: `ModalForm`, `ModalModelForm`
     - Autocomplete forms: `AutoCompleteForm`, `AutoCompleteModelForm`
     - Formset helpers: `DynamicTableInlineFormSetHelper`
     - M2M formsets: `M2MInlineFormSet`, `M2MInlineModelFormSet`

   - **Filters**:
     - `BaseCrispyFilterSet`: Base filter set with Crispy Forms integration
     - `CrispyAutocompleteFilterSet`: Filter set with autocomplete functionality
     - `NullableRangeFilter`: Filter for ranges that can include null values
     - `NullablePercentageRangeFilter`: Specialized range filter for percentages

   - **Widgets**:
     - `RangeSliderWidget`: Widget for selecting ranges with a slider
     - `NullableRangeSliderWidget`: Range slider that can include null values
     - `BSModelSelect2`: Bootstrap-styled select2 widgets for autocomplete

   - **Submodules**:
     - `file_export`: Handles exporting data in different formats (CSV, Excel)
     - `properties`: Manages property definitions and values
     - `templatetags`: Custom template tags for user-created objects

### Debugging

- Django Debug Toolbar is available in development mode
- Celery tasks can be monitored using Flower at http://localhost:5555
- Redis Commander is available for inspecting Redis data

### Common Issues

1. **Database Migrations**:
   - If you encounter database errors, try running migrations:
     ```bash
     docker-compose exec web python manage.py migrate
     ```

2. **Static Files**:
   - If static files are not loading, collect static files:
     ```bash
     docker-compose exec web python manage.py collectstatic --noinput
     ```

3. **Docker Issues**:
   - If services fail to start, check logs:
     ```bash
     docker-compose logs
     ```
   - Try rebuilding the containers:
     ```bash
     docker-compose down
     docker-compose up --build
     ```
