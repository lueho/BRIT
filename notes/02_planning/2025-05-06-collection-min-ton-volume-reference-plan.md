# Plan: Add Reference Point for Minimum Ton Volume Field in Collection

## Background
The `min_ton_volume_per_inhabitant` field in the `Collection` model currently assumes the value is per person. However, some data sources specify minimum ton volume per household or per property. To ensure clarity and flexibility, we need to explicitly capture the reference point for each minimum ton volume value.

## Goals
- Add a field to the `Collection` model to specify the reference point for minimum ton volume (e.g., per person, per household, per property).
- Ensure all forms, serializers, admin, exports, and tests are updated to use this field.
- Maintain backwards compatibility and data integrity.
- Document the change for future maintainers.

## Design
- Add a new field to `Collection`, e.g. `min_ton_volume_reference`, as a `CharField` with choices:
  - "person" (default, current behavior)
  - "household"
  - "property"
- Update help texts and verbose names for clarity.
- Document the meaning of each choice in the model docstring.

## Code Paths to Update (based on original field introduction)
- `case_studies/soilcom/models.py` (add field, docstring)
- `case_studies/soilcom/migrations/` (schema migration)
- `case_studies/soilcom/serializers.py` (add to `CollectionSerializer`)
- `case_studies/soilcom/forms.py` (add to `CollectionModelForm`)
- `case_studies/soilcom/filters.py` (add to filter sets if needed)
- `case_studies/soilcom/viewsets.py` or `views.py` (ensure create/update support)
- `case_studies/soilcom/admin.py` (admin interface)
- `case_studies/soilcom/tasks.py` (export logic)
- `case_studies/soilcom/renderers.py` (export logic)
- `case_studies/soilcom/templates/` (forms/templates for collection create/edit)
- `case_studies/soilcom/tests/test_models.py`
- `case_studies/soilcom/tests/test_serializers.py`
- `case_studies/soilcom/tests/test_forms.py`
- `case_studies/soilcom/tests/test_filters.py`
- `case_studies/soilcom/tests/test_views.py`
- `docs/` or `README.md` (if documented)

## Migration & Data Integrity
- Set default to "person" for all existing records.
- Review any code that assumes the reference is always per person and update logic if needed.

## Testing
- Add/extend tests to cover all allowed reference points.
- Verify UI, API, and export correctness for each reference type.

## Documentation
- Document rationale, field usage, and migration steps in `notes/` and reference in code docstrings.
- Update or supersede any earlier docs regarding the meaning of the min ton volume field.

## Additional Affected Code: Copying and Versioning Collections

- The following code paths must be updated to ensure the new `min_ton_volume_reference` field is correctly handled when duplicating or versioning collections:
  - `case_studies/soilcom/views.py`:
    - `CollectionCopyView` (handles duplicating collections)
    - `CollectionCreateNewVersionView` (handles creating new versions of collections)
    - Both classes use `get_initial()` to populate form data for the new object. Update these methods to include the new field, ensuring it is copied from the source collection.
- Review any other utility functions or management commands that copy or clone `Collection` instances to ensure the new field is handled.

- Update the Collection detail view template(s) (e.g., in `case_studies/soilcom/templates/`) to display the new `min_ton_volume_reference` field alongside the minimum ton volume, ensuring users can always see the reference point for each collection.

---

**This update ensures the reference point is always preserved and correctly set when collections are copied or versioned, and is clearly visible in the UI.**

## Updated Requirements: Optional Fields and Null Reference

- Neither `min_ton_volume_per_inhabitant` nor `min_ton_volume_reference` should be required. Both must allow null/blank values in the model, forms, admin, and serializers.
- The reference point field (`min_ton_volume_reference`) must include a null/empty answer choice (e.g., "—" or "unspecified") in all forms and UI. This should be implemented with `null=True, blank=True` in the model and `required=False` in forms.
- Templates and exports must display a clear indication (such as “—”) if the value or reference is unset.
- All validation and help texts should clarify that both fields are optional and what the null choice means.

## Open Questions
- Are there any other reference points needed?
  - **No. Only person, household, property, and null are required.**
- Should this be extensible beyond the given choices?
  - **No. Fixed set only.**
- Are there downstream consumers that require updates?
  - **No. No downstream consumer.**

---
**This plan is based on the original checklist for min ton volume fields and ensures all affected code paths are updated.**

## Progress Update (2025-05-06 11:52)

### Model
- Added `min_ton_volume_reference` to `Collection` model. Optional, allows null/blank, with fixed choices and a null/empty option.

### Forms
- Updated `CollectionModelForm` to include the new field as an optional choice. Null/blank option included. Help text and label clarified.

### Templates
- Updated `collection_detail.html` to display the new field with human-readable output and null handling.

### Next Steps
- Update admin to support the new field.
- Update serializers to include the field.
- Update views (copy/version) if not already done.
- Add/adjust tests for model, form, serializer, and views.
- Create and apply migration for the model change.

---

# Next Implementation Steps

1. Update Django admin for `Collection` to include the new field.
2. Update serializers to ensure API/export includes the field.
3. Ensure views and duplication/versioning logic handle the field.
4. Add/extend tests for all relevant code paths.
5. Create and apply migration for the schema change.
6. Summarize and clean up notes after completion.

---

## Status & Outcome (Updated 2025-05-06)

### Field Renaming & Consistency Review
- All references to the following fields were updated across the codebase:
  - `min_bin_volume_per_inhabitant` → `required_bin_capacity`
  - `min_bin_volume_reference` → `required_bin_capacity_reference`
  - `min_bin_size` (no change)
- Removed legacy fields: `min_ton_size`, `min_ton_volume_per_inhabitant`, `min_ton_volume_reference`.
- Updates were made in models, forms, filters, serializers, templates, and all related tests.
- User-facing labels and help texts were clarified for each field.

### Next Steps
- User will run the Django test suite to confirm all changes pass.
- Migration review and documentation update are complete for this round.

### Decision
- This plan is now **complete** and can be marked as resolved, pending successful test run.

---
