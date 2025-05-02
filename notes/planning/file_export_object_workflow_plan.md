# Plan: Generalized Export Flow for UserCreatedObject Models

## Context
- There are now two types of filter views for collections:
  - `CollectionCurrentPublishedListView`: should only export published collections.
  - `CollectionCurrentPrivateListView`: should only export collections owned by the current user.
- Both use the same export function, but with different queryset restrictions.
- This pattern will repeat for other UserCreatedObject-derived models.

## Problem
The export process must always respect the base queryset restrictions of the originating list view (published/owned/etc), **in addition to** any filter parameters applied by the user in the UI.

## Requirements
1. **Exports from PublishedListView**: Only published objects (e.g., `published=True`).
2. **Exports from PrivateListView**: Only objects owned by the current user.
3. **Generalization**: The export mechanism should work for any UserCreatedObject-derived model, not just collections.
4. **Maintain Filter Consistency**: Exported data should always match what the user sees in the list view.

## Current Flow (Summary)
- Export modal builds URL with all filter params from UI.
- Export view receives URL, starts a Celery task with the filter params.
- Task reconstructs the queryset using `CollectionFilterSet` and all objects.
- **Problem**: The task uses `Collection.objects.all()`, so it ignores any base queryset restrictions (published/owned/etc) from the originating view.

## Proposed Solution
### 1. Pass the Base Queryset Restriction
- When triggering an export, the backend view should pass the same base queryset restriction (published/owned/other) to the export task.
- The export task should apply the filterset to the **restricted** queryset, not to all objects.

### 2. Implementation Steps
#### a. Refactor Export Task Signature
- Change the export task to accept a base queryset restriction (e.g., a filter dict, or a resolved list of IDs).
- Example:
  ```python
  export_collections_to_file.apply_async(args=[file_format, query_params, allowed_ids])
  ```
- In the task:
  ```python
  base_qs = Collection.objects.filter(pk__in=allowed_ids)
  qs = CollectionFilterSet(qdict, base_qs).qs
  ```
- For more complex restrictions (e.g., ownership), consider passing a list of allowed IDs.

#### b. Update Export Views
- In each export view, determine the base queryset restriction:
  - For published: `{"published": True}` or use `.currently_valid()`
  - For private: `{"owner": request.user}`
- Pass these restrictions to the export task as `allowed_ids = list(base_qs.values_list('pk', flat=True))`.

#### c. Generalize for All UserCreatedObject Models
- Make the export task generic (accept model, filterset, base restriction).
- Use a registry or factory pattern to resolve the correct model/filterset for each export.

#### d. Security
- Double-check in the export task that the restriction is enforced, to prevent privilege escalation.

## Open Questions (Resolved)

### 1. What is the best way to serialize complex queryset restrictions for Celery (IDs, filter dicts, etc)?
- **Resolution:**
  - For most cases, pass a list of allowed primary keys (IDs) to the export task. This is robust, simple to serialize, and avoids leaking filter logic to the task layer.
  - The view should resolve the base queryset (e.g., published, owned) and pass `list(qs.values_list('pk', flat=True))` as `allowed_ids` to the task.
  - The export task then uses `Model.objects.filter(pk__in=allowed_ids)` as the base queryset before applying any filterset logic.
  - For very large exports, consider passing a filter dict, but default to IDs for clarity and security.

### 2. Should we pass user ID to the task for ownership checks, or resolve IDs in the view?
- **Resolution:**
  - Always resolve ownership (or other base restrictions) in the view and pass the list of allowed IDs to the task.
  - This avoids any ambiguity about user context in the async task, and ensures the task cannot escalate privileges or see more than intended.

### 3. How to handle edge cases (e.g., objects deleted between export start and finish)?
- **Resolution:**
  - If objects are deleted between export start and finish, they will simply be missing from the export (since the task uses a static list of IDs).
  - This is acceptable for most business cases and is consistent with how filtered list views behave.
  - If strict consistency is needed, snapshotting or versioning would be required, but is out of scope for most exports.

## Progress Update (2025-05-02)

- The new export flow for Collection was implemented and tested:
    - Export views now resolve and pass allowed IDs to the Celery export task.
    - The export task restricts the queryset to these IDs before applying filters.
    - All relevant tests were updated and now pass, confirming correct and secure behavior.
- Next: Generalize this pattern for all UserCreatedObject-derived models and refactor the export task and view logic to be generic.

## Updated Implementation Steps

1. **In the export view:**
    - Compute the base queryset restriction (e.g., published, owned by user).
    - Pass `allowed_ids = list(base_qs.values_list('pk', flat=True))` to the export task.
2. **In the export task:**
    - Use `Model.objects.filter(pk__in=allowed_ids)` as the base queryset.
    - Apply the filterset to this queryset with the user-supplied filter params.
3. **Generalization:**
    - The same pattern applies for any UserCreatedObject-derived model.
    - The export task can be made generic by accepting the model and filterset class as arguments (or via a registry).
4. **Security:**
    - The task must never expand the queryset beyond the given IDs.
    - All privilege checks are enforced in the view before passing IDs to the task.

**This approach is robust, secure, and easy to maintain.**

---

*Plan refined and open questions resolved as of 2025-05-02.*

## Legacy Code to Refactor/Remove After Manual Testing

- Remove obsolete `task_function = ...` lines from export views now using the generic system (e.g., CollectionListFileExportView, HamburgRoadsideTreesListFileExportView).
- Remove model-specific export Celery tasks (e.g., `export_collections_to_file`, `export_hamburg_roadside_trees_to_file`) once all consumers are migrated.
- Remove model-specific export view classes that are now replaced by the generic export view.
- Remove any model-specific test code that only tests old, non-generic export logic.
- Update or remove documentation and comments referencing the old export flow.
- Ensure all URLs and client code are updated to use the new generic export endpoints.

## Example for Collections
- In `CollectionCurrentPublishedListView`, export view passes only published collections.
- In `CollectionCurrentPrivateListView`, export view passes only collections owned by the user.
- The export task applies the filterset to this restricted queryset.

## Documentation and Next Steps
- Document this plan and the rationale in `notes/planning/file_export_object_workflow_plan.md`.
- Update the export views and task accordingly.
- Test for both published and private flows.
- Generalize for other models as needed.

---

**This plan will ensure that all exports for UserCreatedObject-derived models respect the originating view's queryset restrictions, are secure, and are maintainable as new models/views are added.**
