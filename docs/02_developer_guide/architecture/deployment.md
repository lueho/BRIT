# Deployment Overview

This page describes BRIT deployment architecture and boundaries. It is not the step-by-step operations runbook.

## Scope of This Page

- **Use this page for**
  Understanding which services exist, how local and production deployments differ, and where configuration belongs.

- **Do not duplicate here**
  Release steps and runtime commands belong in [Operations](../../03_operations/operations.md).

## Local Deployment Topology

- **Application service**
  Django runs in the `web` container.

- **Database**
  PostgreSQL with PostGIS backs relational and geospatial data.

- **Background processing**
  Redis and Celery support asynchronous tasks.

- **Supporting services**
  Flower may be enabled for task monitoring.

## Production Deployment Topology

- **Application runtime**
  BRIT runs as a containerized Django application served by Gunicorn.

- **Stateful services**
  Production requires PostgreSQL with PostGIS and Redis.

- **Static assets**
  Static files are collected during release and served through the deployment platform or a dedicated static/media layer.

- **Configuration**
  Secrets and environment-specific settings must come from environment variables or platform configuration, not committed files.

## Release Responsibilities

- **Development workflow**
  Code changes, tests, and migrations are prepared during normal development. See [Developer Guidelines](../guidelines.md).

- **Operations workflow**
  Release execution, runtime commands, and operational checks are described in [Operations](../../03_operations/operations.md).

- **Deployment branch**
  Deployment automation is tied to the repository workflow and the reserved `deploy` branch.

## Related Documentation

- **Architecture overview**
  See [../architecture.md](../architecture.md).

- **Data flow**
  See [data_flow.md](data_flow.md).

- **Operations runbook**
  See [../../03_operations/operations.md](../../03_operations/operations.md).

_Last updated: 2026-03-06_
