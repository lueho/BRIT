# BRIT Core Module

## Overview
The BRIT Core Module is the central component of the Bioresource Inventory Tool (BRIT). It serves as the main Django project module that integrates all other modules and provides the core functionality and configuration for the entire application.

## Features
- Main project configuration and settings
- URL routing for all modules
- Core views for main pages (Home, About, Learning, Privacy Policy)
- Integration of all other modules
- Authentication and authorization management
- Caching configuration
- Static and media file handling
- REST API configuration

## Components

### Settings
The settings package contains the main configuration for the entire application, including:
- Database configuration
- Installed apps
- Middleware
- Authentication settings
- Caching (Redis)
- AWS S3 storage configuration
- REST framework settings
- Email settings

### URLs
The urls.py file defines the URL routing for the entire application, connecting all modules and their respective URL patterns.

### Views
The core views include:
- HomeView - The main landing page
- AboutView - Information about the project
- LearningView - Educational content
- PrivacyPolicyView - Privacy policy information
- CacheTestView - Testing caching functionality
- Session management utilities

### Templates
The module includes templates for the core pages of the application, providing a consistent user interface.

## Breadcrumb Navigation

This section is the authoritative **current-state** reference for breadcrumb navigation in BRIT.

### Shared implementation

- **Base page chrome**
  - `brit/templates/base.html` provides the shared sticky breadcrumb rail through the `page_chrome` and `breadcrumbs` blocks.
  - The default fallback path is currently:
    - `BRIT`
    - active label from `object.name`, `header`, `title`, or `request.resolver_match.url_name|title`

- **Shared filtered lists**
  - `brit/templates/filtered_list.html` provides the generic list breadcrumb path.
  - When `dashboard_url` is present, the shared pattern is currently:
    - `BRIT > Explorer > <current list label>`
  - The current list label comes from `header` when available, otherwise from the model's plural label.

- **Shared detail pages**
  - `brit/templates/detail_with_options.html` provides the generic detail breadcrumb path.
  - The shared pattern is currently:
    - `BRIT > <object list label> > <current object>`
  - The list label is derived from `object.list_url` and `object.get_verbose_name_plural`.
  - The current object label is currently derived from `object.name`.

- **Explicit page overrides**
  - Many explorer and dashboard pages now define explicit `breadcrumbs` blocks so the sticky rail shows a human-chosen label instead of only the fallback path.
  - `materials/templates/materials/sample_detail_v2.html` intentionally suppresses the shared base breadcrumb rail and keeps its own custom sticky sample-detail rail.

### Current known limitations

- **Generic module crumb**
  - Shared filtered lists still use the generic label `Explorer` rather than a module-specific label such as `Materials`, `Maps`, or `Inventories`.

- **Weak object-label assumption**
  - Shared detail breadcrumbs assume the current object can always be rendered as `object.name`.
  - This is not valid for every model.

- **Fallback leakage**
  - Static or exceptional pages can still fall back to `title` or route-name humanization, which can produce awkward labels.

- **Page-title drift**
  - Some shared title paths are still weak enough that pages can render `BRIT | None` if the expected title/header context is missing.

- **Nested-domain inconsistency**
  - Some source-domain and plugin-mounted pages expose only a local entity crumb, while others expose a higher-level parent path.

### Planned changes

- The authoritative breadcrumb target state, rollout phases, and progress tracking live in:
  - `docs/04_design_decisions/2026-04-21_breadcrumb_navigation_target_state_plan.md`

## Integration
The BRIT Core Module integrates all other modules of the application:
- bibliography
- case_studies
- distributions
- interfaces
- inventories
- layer_manager
- maps
- materials
- sources
- users
- utils

## Dependencies
The application relies on several key technologies:
- Django web framework
- PostgreSQL database
- Redis for caching
- AWS S3 for file storage
- Django REST framework for API functionality