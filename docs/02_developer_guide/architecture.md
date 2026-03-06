# Architecture Overview

This document provides a durable, high-level view of BRIT architecture. It is intended to explain system shape and boundaries, not to serve as a workflow runbook.

## System Context

- **Application type**
  BRIT is a modular Django application.

- **Primary services**
  PostgreSQL with PostGIS stores relational and geospatial data. Redis and Celery support asynchronous tasks.

- **Execution model**
  BRIT is developed and operated in a containerized environment.

## Major Building Blocks

- **Django apps**
  Domain functionality is split across apps. See [Applications Overview](applications.md).

- **Shared utilities**
  Cross-cutting patterns live in `utils/`.

- **Frontend layer**
  The UI is based on Bootstrap, Django templates, and JavaScript. New frontend work should avoid jQuery.

- **Background processing**
  Long-running or asynchronous work is delegated to Celery tasks.

- **APIs**
  BRIT exposes resource-oriented endpoints for internal and external integrations.

## Architectural Patterns

- **Modular domains**
  Keep domain logic inside app boundaries.

- **Reusable base abstractions**
  Shared object lifecycle, ownership, permissions, and export behavior are implemented centrally and reused across apps.

- **Class-based views**
  Views favor composition and inheritance for consistency.

- **Signals and initial data hooks**
  Signals and `ensure_initial_data()` patterns are used where cross-cutting setup must stay centralized. See [Initial Data Management](initial_data_management.md).

## Documentation Boundaries

- **Development commands**
  See [Guidelines](guidelines.md).

- **Deployment and runtime operations**
  See [Deployment Overview](architecture/deployment.md) and [Operations](../03_operations/operations.md).

- **Detailed data flow**
  See [architecture/data_flow.md](architecture/data_flow.md).

_Last updated: 2026-03-06_
