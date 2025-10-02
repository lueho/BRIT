# Plan: Updating `CollectionModelForm` Fields – Impact Analysis

## 1. Directly Affected Code

### a. `CollectionModelForm` (forms.py)
- The form class itself and its `Meta` fields, custom fields, and `save()` logic will need updating.

### b. `CollectionModelFormHelper` (forms.py)
- The layout and field order for crispy-forms must be updated to include new fields.

### c. Model: `Collection` (models.py)
- If the new fields do not exist on the `Collection` model, the model and database migrations will be required.
- If fields are related to other models (FKs, M2M), check their existence and relationships.

## 2. Views
- Any view using `CollectionModelForm` as `form_class`, e.g., create/update views for collections.
- Example: likely in `views.py` as `CollectionCreateView`, `CollectionUpdateView`, or similar.
- Check modal or inline views if present.

## 3. Templates
- Templates rendering the form: e.g., `collection_form.html`, `form_and_formset.html`, or any modal forms.
- Templates displaying collection details: `collection_detail.html`, `waste_collection_map.html`, etc. These may need to display new fields.
- Filter/list templates: `collection_filter.html` (if new fields are filterable or shown in lists).

## 4. Serializers
- If there is a DRF serializer for `Collection` or a `CollectionModelForm`-based serializer, update its fields.
- Example: `CollectionModelSerializer`, `CollectionFlatSerializer`.

## 5. Tests
- Form tests: e.g., `CollectionModelFormTestCase` in `test_forms.py`.
- View tests: e.g., `CollectionCRUDViewsTestCase`, `CollectionCreateNewVersionViewTestCase` in `test_views.py`.
- Serializer tests: e.g., `CollectionFlatSerializerTestCase` in `test_serializers.py`.
- Add/modify test data to include new fields.

## 6. Other Forms/Helpers
- Any forms or helpers that reference or subclass `CollectionModelForm`.
- Inline or modal forms.

## 7. Data Migration
- If adding non-nullable fields to the model, plan for a data migration or set default values.

## 8. Documentation
- Update user/developer documentation if form usage or semantics change.

## 9. File Export Logic (CSV/XLSX)

### Files/Classes to Update
- `renderers.py`:
  - `CollectionCSVRenderer` (update `header`, `labels`, and row data logic)
  - `CollectionXLSXRenderer` (update `labels`, columns, and row data logic)
- `tasks.py`:
  - `export_collections_to_file` (ensure new fields are included in export data)
- `serializers.py`:
  - `CollectionFlatSerializer` (add new fields to serializer output)
- `tests/test_renderers.py`:
  - Add/update tests to verify export of new fields

### What to do
- Add new fields to the serializer used for export.
- Add new fields to the `header` and `labels` in both renderers.
- Adjust row formatting if the new fields require special handling (e.g., formatting, lookups).
- Update or add tests to ensure the new fields are present in the exported files.

### Potential Issues
- If the new fields are required but missing in existing data, exports may break or produce incomplete rows.
- Formatting or value mapping may be needed for non-primitive fields.

---

# Checklist for Adding Fields to `CollectionModelForm`

- [ ] Update `CollectionModelForm` fields and logic
- [ ] Update `CollectionModelForm.Meta.fields` and labels/widgets if needed
- [ ] Update `CollectionModelFormHelper` layout
- [ ] Update the `Collection` model (and create migrations) if fields are new to the model
- [ ] Update all views using `CollectionModelForm`
- [ ] Update all relevant templates (form rendering, detail, list, filter)
- [ ] Update serializers for `Collection` if exposed via API
- [ ] Update/extend all relevant tests (form, view, serializer)
- [ ] Plan and implement data migration if required
- [ ] Update documentation
- [ ] Update file export logic (CSV/XLSX): renderers, serializer, tests

---

# Potential Issues
- **Model changes:** Adding required fields to the model may break existing data or forms if not handled with defaults/migrations.
- **Templates:** Missing new fields in templates can cause confusion or incomplete data entry.
- **Tests:** Tests will fail if new required fields are not provided in test data.
- **Serializers:** API clients may break if new fields are required but not supplied.
- **Cascading logic:** If `save()` or custom logic depends on the new fields, ensure all usages are updated.
- **Exports:** Missing fields in export logic will result in incomplete data in CSV/XLSX outputs.

---

# References
- `forms.py`: `CollectionModelForm`, `CollectionModelFormHelper`
- `models.py`: `Collection`
- `views.py`: All views using `CollectionModelForm`
- `templates/soilcom/collection_form.html`, `collection_detail.html`, `collection_filter.html`, etc.
- `serializers.py`: `CollectionModelSerializer`, `CollectionFlatSerializer`
- `renderers.py`: `CollectionCSVRenderer`, `CollectionXLSXRenderer`
- `tasks.py`: `export_collections_to_file`
- `tests/test_forms.py`, `tests/test_views.py`, `tests/test_serializers.py`, `tests/test_renderers.py`

---

# Next Steps
1. Confirm which fields to add and whether they exist on the model.
2. Update the model if necessary and run migrations.
3. Update the form, helper, views, templates, serializers, renderers, and tests as outlined.
4. Run all tests to ensure correctness.
5. Document changes for future maintenance.
