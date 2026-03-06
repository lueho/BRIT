# BRIT Documentation

This index is the entry point for project documentation. Each topic has a clear home so workflow instructions do not drift across multiple pages.

## Where to Look

- **User-facing tasks**
  Start with [How-Tos](01_user_guide/howtos.md).

- **Development workflow and day-to-day commands**
  Use the [Developer Guide](02_developer_guide/README.md), especially [Guidelines](02_developer_guide/guidelines.md).

- **Deployment and operations**
  Use [Operations](03_operations/operations.md) as the canonical source for deployment, runtime operations, logs, and backups.

- **Architecture and app boundaries**
  Use [Architecture Overview](02_developer_guide/architecture.md), [Deployment Overview](02_developer_guide/architecture/deployment.md), and [Applications Overview](02_developer_guide/applications.md).

- **Design rationale and historical decisions**
  Use [Design Decisions](04_design_decisions/README.md).

## Documentation Rules

- **Commands live in one place**
  Development commands belong in the developer workflow docs. Deployment and runtime commands belong in operations docs.

- **Module details live with the module**
  App-specific overviews belong in app `README.md` files.

- **Reference docs should link, not duplicate**
  Overview pages should point to canonical instructions instead of repeating them.

_Last updated: 2026-03-06_
