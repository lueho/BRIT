# Applications Overview

This document is a high-level map of BRIT apps and their responsibilities. App-specific behavior and domain details should be documented in the relevant app `README.md` files.

## Core Project Layer

### `brit`
- Project settings, root URL configuration, templates, and shared static assets.

### `utils`
- Shared infrastructure such as object lifecycle handling, exports, properties, and reusable cross-app patterns.

### `users`
- Authentication, profile-related functionality, and user management.

## Domain Apps

### `maps`
- Catchments, regional data, GIS behavior, and map-oriented views.

### `materials`
- Material catalogues, samples, compositions, measurements, and related laboratory metadata.

### `distributions`
- Temporal distributions and timesteps used by other apps.

### `bibliography`
- Sources, authors, licensing metadata, and supporting bibliographic workflows.

### `inventories`
- Inventory and scenario tooling.

### `case_studies`
- Project-specific or domain-specific extensions such as Soilcom and Flexibi.

## Documentation Boundaries

- **Architecture-level descriptions**
  Keep in [architecture.md](architecture.md).

- **Module-specific detail**
  Keep in app `README.md` files.

- **Workflow commands**
  Keep in [guidelines.md](guidelines.md) or [../03_operations/operations.md](../03_operations/operations.md), depending on whether they are development or runtime tasks.

_Last updated: 2026-03-06_
