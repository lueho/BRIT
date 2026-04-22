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

This section is the authoritative **operational reference** for breadcrumb navigation in BRIT. The design rationale and decision record live in `docs/04_design_decisions/2026-04-22_breadcrumb_navigation_contract.madr.md`.

### Rendering path

```
BRIT > <parent module> > <module> > <section> > <object> > <action>
```

Each slot is optional. The deepest populated slot is the active crumb. Browser titles are derived from the same label metadata so they track the breadcrumbs.

### Shared contract slots

All shared pages populate context via `utils.views.build_breadcrumb_context` or `BreadcrumbContextMixin`:

| Slot | Purpose |
|---|---|
| `breadcrumb_parent_module_label` / `breadcrumb_parent_module_url` | Parent module (e.g. `Sources` for nested plugins). |
| `breadcrumb_module_label` / `breadcrumb_module_url` | Top-level module. |
| `breadcrumb_section_label` / `breadcrumb_section_url` | Entity plural within the module. |
| `breadcrumb_object_label` / `breadcrumb_object_url` | Current object; defaults to `object.get_breadcrumb_object_label()` (i.e. `str(self)`). |
| `breadcrumb_action_label` | Trailing action (`Create`, `Update`, …). |
| `breadcrumb_page_title` | Browser-title contribution; defaults to the deepest populated breadcrumb label. |

The legacy `object` / `header` / `title` / `breadcrumb_page_title` fallback chain in `base.html` is retained only as a safety net for pages that do not yet adopt the contract and is regression-guarded by `BreadcrumbContractFallbackPrecedenceTests`.

### Default module and plugin registry

`utils/object_management/views.py::DEFAULT_BREADCRUMB_MODULES` maps each Django app label to its `label`, `url_name`, and optional `parent_label` / `parent_url_name`. Shared CRUD views consume this mapping to populate the contract automatically. Current registry:

| App label | Module label | Module URL name | Parent |
|---|---|---|---|
| `bibliography` | Bibliography | `bibliography-explorer` | — |
| `inventories` | Inventories | `inventories-explorer` | — |
| `maps` | Maps | `maps-dashboard` | — |
| `materials` | Materials | `materials-explorer` | — |
| `processes` | Processes | `processes-dashboard` | — |
| `properties` | Properties | `properties-dashboard` | — |
| `sources` | Sources | `sources-explorer` | — |
| `utils` | Utilities | `utils-dashboard` | — |
| `waste_collection` | Waste Collection | `wastecollection-explorer` | `Sources` → `sources-explorer` |
| `greenhouses` | Greenhouses | *(none — plain text)* | `Sources` → `sources-explorer` |
| `roadside_trees` | Roadside Trees | *(none — plain text)* | `Sources` → `sources-explorer` |

To nest a new plugin under an existing module, add an entry with `parent_label` / `parent_url_name` pointing at the parent module; no per-view template changes are needed. Setting `url_name` to `None` causes the module crumb to render as plain text (no link), which is the current pattern for plugins without a dashboard page.

### How pages adopt the contract

- **Shared CRUD views** — subclass the `UserCreatedObject*` views in `utils/object_management/views.py`; they populate the contract automatically from the model and the registry.
- **Custom views** — mix in `BreadcrumbContextMixin` and override `get_breadcrumb_*` methods or set the matching class attributes.
- **One-off pages** — call `build_breadcrumb_context(...)` directly in `get_context_data` and update the context.
- **Custom detail experiences** — render the shared rail (do not override `{% block page_chrome %}` as empty) and layer any page-level toolbar below it. `materials/templates/materials/sample_detail_v2.html` is the canonical example: the shared rail owns `BRIT > Materials > Samples > <Sample>` while the `sdv2-rail` stacks below it with sample-specific actions (status pill, mode toggle, quick-actions palette, export, classic-view link).

### Deliberate rail suppression

- The home page and 403/404/500 error pages override `{% block page_chrome %}` as empty. Suppression pages are expected to compensate in-content (inline header or a "← Back to Home" link) so users are never stranded.

### Sticky offsets (CSS)

`brit/static/css/filtered-list.css` defines the canonical sticky offsets:

```css
--brit-topnav-height: 56px;
--brit-breadcrumb-rail-height: 3rem;
--brit-sticky-offset: calc(var(--brit-topnav-height)
                         + var(--brit-breadcrumb-rail-height) + 1rem);
```

Any sticky sibling of the breadcrumb rail (filter sidebars, the `sdv2-rail`, the sample-detail related aside) derives its `top` from these variables rather than hardcoding `56px`. `StickyFilterOffsetAssetTests` regression-guards the CSS contract.

### Test coverage

Regression tests live in `brit/tests/test_templates.py`, organized into:

- `BreadcrumbContractFallbackPrecedenceTests` — contract slots win over the legacy fallback chain.
- `BreadcrumbModuleLandingTests` — per-module landing-page breadcrumbs.
- `BreadcrumbNestedSourcesDomainTests` — nested `Sources > <Plugin>` path across list, detail, create, and update pages for `waste_collection` and `greenhouses`.
- `BreadcrumbNonNameDetailObjectTests` — detail crumbs for models without a `name` field.
- `SampleDetailV2BreadcrumbHarmonizationTests` — `sample_detail_v2` participates in the shared contract.
- `ErrorPageBreadcrumbTests` — deliberate suppression on error pages.
- `StickyFilterOffsetAssetTests` — sticky offset CSS variables.

New breadcrumb-affecting changes must add or extend a focused regression test in the appropriate class.

### Current known limitations

- **Fallback leakage on non-contract pages** — pages that do not use `BreadcrumbContextMixin` or the shared CRUD base classes may still fall back to `title` or route-name humanization. Adopt the contract to remove the weak label.
- **Greenhouses and Roadside Trees have no plugin dashboard** — their nested module crumb renders as plain text (no link). The parent crumb (`Sources`) still links back to the Sources explorer.

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