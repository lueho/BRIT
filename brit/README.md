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
  - The contract-driven rendering path is:
    - `BRIT > <parent module> > <module> > <section> > <object> > <action>`
  - Each slot is optional. The last populated slot is rendered as the active crumb. When none of the slots are set, the rail falls back to the active label from `object.get_breadcrumb_object_label`, `header`, `title`, or `breadcrumb_page_title`.

- **Shared breadcrumb contract**
  - `utils.views.build_breadcrumb_context` and `BreadcrumbContextMixin` expose the slots
    `breadcrumb_parent_module_label/url`, `breadcrumb_module_label/url`,
    `breadcrumb_section_label/url`, `breadcrumb_object_label/url`,
    `breadcrumb_action_label`, and `breadcrumb_page_title`.
  - Shared CRUD views (`utils/object_management/views.py`) inject sensible defaults from
    `DEFAULT_BREADCRUMB_MODULES`, the model's plural label, and `object.get_breadcrumb_object_label`.

- **Shared filtered lists**
  - `brit/templates/filtered_list.html` delegates its breadcrumb rendering to the base template through the shared contract.
  - For a published list the shared pattern is:
    - `BRIT > <module> > <entity plural>`

- **Shared detail pages**
  - `brit/templates/detail_with_options.html` delegates its breadcrumb rendering to the base template through the shared contract.
  - For a detail page the shared pattern is:
    - `BRIT > <module> > <entity plural> > <object>`

- **Source-domain plugins (nested hierarchy)**
  - `waste_collection`, `greenhouses`, and `roadside_trees` are configured as children of `Sources` in `DEFAULT_BREADCRUMB_MODULES`, so their CRUD pages render as:
    - `BRIT > Sources > <Plugin> > <Entity plural> > <Object> > <Action>`
  - The Waste Collection explorer landing page itself renders as `BRIT > Sources > Waste Collection` using the parent slot.

- **Explicit page overrides**
  - Module landing pages and static pages (about, learning, privacy policy) set explicit `breadcrumb_module_label`, `breadcrumb_section_label`, and/or `breadcrumb_page_title` via `BreadcrumbContextMixin`.
  - The home page and 403/404/500 error pages deliberately suppress the sticky breadcrumb rail by overriding `{% block page_chrome %}` as empty.
  - `materials/templates/materials/sample_detail_v2.html` participates in the shared breadcrumb contract: the shared sticky rail renders `BRIT > Materials > Samples > <Sample>` through the contract, while the `sdv2-rail` stacks below the shared rail and holds only sample-specific actions (status pill, mode toggle, quick-actions palette, export, classic-view link).

### Current known limitations

- **Fallback leakage on non-contract pages**
  - Pages that do not use `BreadcrumbContextMixin` or the shared CRUD base classes may still fall back to `title` or route-name humanization, which can produce awkward labels. The fallback chain in `base.html` is retained as a safety net and is regression-guarded by `BreadcrumbContractFallbackPrecedenceTests`.

- **Greenhouses and Roadside Trees have no plugin dashboard**
  - Their nested module crumb renders as plain text (no link) because the plugins do not expose a dashboard URL; the parent crumb (`Sources`) still links back to the Sources explorer.

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