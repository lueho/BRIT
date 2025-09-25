# Excel Import (Admin-only)

The Excel data import workflow is now available only via the Django admin UI. The legacy CLI management command path has been deprecated.

## Summary
- The previous `materials.management.commands.import_excel_data` command now raises a `CommandError` instructing users to use the admin interface.
- The admin UI provides detailed feedback:
  - Success messages with created counts
  - Error messages for processing failures
  - Warnings for skipped data or formatting issues
  - Informative messages when no measurements are created due to data issues

## How to import via admin
1. Log in to the Django admin (`/admin`).
2. Navigate to the relevant Materials admin section.
3. Use the import action (or dedicated admin view) to upload the Excel file and select a sheet when applicable.
4. Submit and review the feedback messages.

## Implementation notes
- Unit creation fixes: Avoid using non-existent fields such as `symbol` when creating `Unit` objects.
- Measurement validation: Parameter group membership is validated before measurement creation.
- Database constraints: Optional `reference_parameter` is supported to avoid constraint violations.
- Data model: Measurements are grouped under `MeasurementSet` and displayed on `SampleDetailView`, which prioritizes measurements over compositions when present.
- Source handling: `_get_or_create_source` ensures Sources are created correctly using `abbreviation` and `title` with safe length truncation.

## Developer tips
- For performance debugging, a `--sheet` option exists in the deprecated command, but the supported path is the admin UI.
- When adding new import logic, ensure all validation and object creation is idempotent and respects model constraints.
- Keep user feedback comprehensive: report counts, warnings, and reasons for skipped rows.

## Related files
- `materials/admin.py` (admin integration points)
- `materials/views.py` (where applicable)
- `materials/models.py` (MeasurementSet, Measurement, Composition)
- `materials/serializers.py`
- `utils/file_export/*` (for exports)
