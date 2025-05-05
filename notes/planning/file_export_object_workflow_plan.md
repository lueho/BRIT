# Plan: Generalized Export Flow for UserCreatedObject Models

---

# Status: COMPLETE (2025-05-05)

All code, tests, and documentation for the generic file export flow are now production-ready. Legacy code has been removed, and all usages are migrated. The new pattern is in place for all UserCreatedObject-derived models. No further action is required unless new models or requirements arise.

## Checklist
- [x] Plan and rationale documented here
- [x] View and Celery task refactored to use filter parameters and context
- [x] All usages migrated to new pattern
- [x] Legacy code and tests removed
- [x] Documentation updated
- [x] Tests updated and passing

## If new models are added
- Register them in the export registry
- Ensure their views and filtersets follow this pattern

---

*This plan is now archived. No further work is needed unless new requirements emerge.*

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
### 1. Pass Filter Parameters and Context, Not IDs
- When triggering an export, the backend view should pass the same base queryset restriction (e.g., published/owned/other) as filter parameters and context (such as user ID and list type) to the export task.
- The export task should reconstruct the queryset using these parameters, ensuring the queryset matches the originating list view's restrictions and any UI filters.

### 2. Implementation Steps
#### a. Refactor Export Task Signature
- Change the export task to accept filter parameters (dict) and context (dict) instead of a list of IDs.
- Example:
  ```python
  export_collections_to_file.apply_async(args=[file_format, filter_params, {'user_id': request.user.pk, 'list_type': params.get('list_type', ['public'])[0]}])
  ```
- In the task:
  ```python
  def export_task(file_format, filter_params, context):
      from case_studies.soilcom.models import Collection
      user_id = context['user_id']
      list_type = context['list_type']
      if list_type == 'private':
          base_qs = Collection.objects.filter(owner_id=user_id)
      else:
          base_qs = Collection.objects.filter(publication_status='published')
      # Apply filter_params as needed...
  ```

#### b. Extract Queryset Logic
- Move queryset-building logic to a shared function to avoid duplication and ensure maintainability.

#### c. Update All Usages
- Update views, tasks, and tests to use the new pattern.

#### d. Clean Up
- Remove any code that builds or passes allowed IDs for this purpose.

## Open Questions (Resolved)

### 1. What is the best way to serialize complex queryset restrictions for Celery (IDs, filter dicts, etc)?
- **Resolution:**
  - For most cases, pass filter parameters and context (e.g., user ID, list type) to the export task. This is robust, simple to serialize, and avoids leaking filter logic to the task layer.
  - The view should resolve the base queryset (e.g., published, owned) and pass the necessary parameters to the task.
  - The export task then uses these parameters to reconstruct the queryset before applying any filterset logic.

### 2. Should we pass user ID to the task for ownership checks, or resolve IDs in the view?
- **Resolution:**
  - Always pass user ID and other context to the task, and let it reconstruct the queryset.
  - This avoids any ambiguity about user context in the async task, and ensures the task cannot escalate privileges or see more than intended.

### 3. How to handle edge cases (e.g., objects deleted between export start and finish)?
- **Resolution:**
  - If objects are deleted between export start and finish, they will simply be missing from the export (since the task uses a dynamic queryset).
  - This is acceptable for most business cases and is consistent with how filtered list views behave.
  - If strict consistency is needed, snapshotting or versioning would be required, but is out of scope for most exports.

## Progress Update (2025-05-02)

- The new export flow for Collection was implemented and tested:
    - Export views now resolve and pass filter parameters and context to the Celery export task.
    - The export task reconstructs the queryset using these parameters.
- Legacy export code and old task functions have been removed.
- Export modal links and all relevant templates now always pass the correct list_type, ensuring private/public context is preserved for exports.
- All debug logging and print statements have been cleaned up from production code.
- Codebase and templates have been tidied and are ready for release.

## Next Steps
- Monitor for any edge cases or new model integrations.
- Ensure all new UserCreatedObject-derived models follow the same export registration and workflow pattern.
- Review and update documentation as new requirements arise.

---

**Release ready: All code and templates for the file export workflow are now production-ready.**

## Updated Implementation Steps

1. **In the export view:**
    - Compute the base queryset restriction (e.g., published, owned by user).
    - Pass filter parameters and context (e.g., user ID, list type) to the export task.
2. **In the export task:**
    - Use the passed parameters to reconstruct the queryset.
    - Apply the filterset to this queryset with the user-supplied filter params.
3. **Generalization:**
    - The same pattern applies for any UserCreatedObject-derived model.
    - The export task can be made generic by accepting the model and filterset class as arguments (or via a registry).
4. **Security:**
    - The task must never expand the queryset beyond the given parameters.
    - All privilege checks are enforced in the view before passing parameters to the task.

**This approach is robust, secure, and easy to maintain.**

---

*Plan refined and open questions resolved as of 2025-05-02.*

## Legacy Code to Refactor/Remove After Manual Testing

- [x] Remove obsolete `task_function = ...` lines from export views now using the generic system (e.g., CollectionListFileExportView, HamburgRoadsideTreesListFileExportView).
- [x] Remove model-specific export Celery tasks (e.g., `export_collections_to_file`, `export_hamburg_roadside_trees_to_file`) once all consumers are migrated.
- [x] Remove model-specific export view classes that are now replaced by the generic export view.
- [x] Remove any model-specific test code that only tests old, non-generic export logic.
- [x] Update or remove documentation and comments referencing the old export flow.
- [x] Ensure all URLs and client code are updated to use the new generic export endpoints.

_Removed export_collections_to_file and all related legacy code/tests on 2025-05-02 after full migration to the generic export workflow._

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
