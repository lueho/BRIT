# Processes Module

The `processes` app documents process technologies, their categories, material flows, operating parameters, links, supporting resources, and literature references.

This file is the current source of truth for how the module works today.
For planned future work, see `PRODUCTION_ROADMAP.md`.

## Current user-facing behavior

### Main entry points

- Dashboard: `processes:dashboard`
- Explorer alias: `processes:processes-explorer`
- Category list: `processes:processcategory-list`
- Process list: `processes:process-list`
- Process type alias: `processes:processtype-list`

### Process categories

Users can:

- Browse published process categories
- Browse their own private categories
- Browse categories in review if they can moderate
- Create, update, and delete categories
- Open category detail views and modal detail/update views
- Use category autocomplete and owned-object option lists in forms

### Processes

Users can:

- Browse published processes with filters
- Browse their own private processes with filters
- Browse processes in review if they can moderate
- Create and update processes with inline related objects
- Open detail and modal detail views
- Delete processes through modal views
- Add materials and operating parameters through dedicated helper views
- Use process autocomplete in forms

### Process detail content

The main process detail view aggregates the current process data model, including:

- Parent/variant relationships
- Categories
- Input and output materials
- Operating parameters grouped by parameter type
- External links and supporting resources
- Literature references and derived `sources`

### Review and moderation workflow

The module uses the shared BRIT object-management workflow.

Moderators and staff can access review scopes and moderation actions through the standard templates and policy helpers.
The module defines custom moderation permissions for:

- `processes.can_moderate_process`
- `processes.can_moderate_processcategory`

This follows the shared four-eyes review pattern used across BRIT.

## Current data model

### Core models

- `ProcessCategory`
- `Process`
- `ProcessMaterial`
- `ProcessOperatingParameter`
- `ProcessLink`
- `ProcessInfoResource`
- `ProcessReference`

### Important model behavior

- `Process` supports parent/child variant relationships
- `Process` groups materials through the `ProcessMaterial` through-model
- `Process` exposes convenience accessors such as `input_materials`, `output_materials`, and `sources`
- `ProcessOperatingParameter` stores typed parameters with optional nominal and range values
- `ProcessLink` and `ProcessInfoResource` validate internal and external URLs
- `ProcessReference` normalizes bibliography links without requiring duplicate direct source relations on `Process`

## Forms and autocomplete

The module uses TomSelect-based form fields for related-object selection.
Current autocomplete-backed fields include:

- Parent process
- Process categories
- Materials
- Units
- Bibliography sources

The main forms live in `processes/forms.py` and follow the shared BRIT `SimpleModelForm` and inline-formset patterns.

## Templates

The canonical current templates are:

- `processes/dashboard.html`
- `processes/processcategory_list.html`
- `processes/processcategory_detail.html`
- `processes/processcategory_form.html`
- `processes/process_list.html`
- `processes/process_detail.html`
- `processes/process_form.html`

These templates follow the common BRIT base-template patterns for list, filtered-list, and detail pages.

## API surface

The module exposes REST endpoints under `processes/api/`.
The router currently registers:

- `api/processes/`
- `api/categories/`

Current custom API actions include:

- Category processes
- Process materials
- Process parameters
- Process parameters grouped by type
- Process variants
- Process sources
- Processes grouped by category
- Processes grouped by mechanism

## Developer guide

### Main implementation files

- `processes/models.py`
- `processes/forms.py`
- `processes/filters.py`
- `processes/views.py`
- `processes/serializers.py`
- `processes/viewsets.py`
- `processes/router.py`
- `processes/urls.py`

### Shared framework dependencies

The module relies on the project-wide object management stack for:

- ownership and publication status
- review and moderation behavior
- CRUD base views
- template policy helpers

### Tests

Current test modules include:

- `processes/tests/test_models.py`
- `processes/tests/test_forms.py`
- `processes/tests/test_filters.py`
- `processes/tests/test_views.py`
- `processes/tests/test_serializers.py`
- `processes/tests/test_viewsets.py`

Run the module test suite inside Docker:

```bash
docker compose exec web python manage.py test processes --noinput --settings=brit.settings.testrunner
```

## Documentation policy for this module

- `README.md` documents current behavior only
- `PRODUCTION_ROADMAP.md` documents future work only
- superseded historical implementation notes should not be kept as parallel docs
