---
title: ADR: Decoupling file_export into a Generic, Reusable Package
date: 2025-05-08
author: LLM + USER
status: Accepted
---

# Context

The `utils.file_export` module was originally tightly coupled to BRIT-specific logic (e.g., owner/publication_status checks, list_type, LoginRequiredMixin). This made it difficult to reuse in other Django projects and led to hard-coded permission rules.

# Decision

We refactored `utils.file_export` to become a fully generic, permission-agnostic package. All BRIT-specific logic was moved to thin wrappers in the BRIT codebase. The new structure is:

- **Generic base view**: `BaseFileExportView` (permission-agnostic)
- **Generic Celery task**: `export_user_created_object_to_file` (no project-specific filtering)
- **BRIT wrapper view**: `BritGenericUserCreatedObjectExportView` and task in `brit/`, which reintroduce project-specific filtering and permissions
- **Tests**: Split into generic (in package) and BRIT-specific (in BRIT codebase)

# Consequences

- The `file_export` package can now be installed and used in any Django project.
- All project-specific filtering, permission, and business logic must be handled outside the generic package, via wrappers or subclassing.
- This pattern increases maintainability, testability, and reusability.

# Example Pattern

**Generic usage:**
```python
class MyExportView(BaseFileExportView):
    task_function = my_export_task
```

**Project-specific wrapper:**
```python
from brit.export_views import BritGenericUserCreatedObjectExportView
class CollectionListFileExportView(BritGenericUserCreatedObjectExportView):
    model_label = "soilcom.Collection"
```

# Status

This ADR documents the rationale and outcome of the decoupling. All code, tests, and docs have been updated accordingly.
