# Plan: Add minimum ton size and minimum ton volume per inhabitant to Collection model

## Background
Capture for each `Collection` the minimum ton size and minimum ton volume per inhabitant to support reporting and calculations.

## Data & UI Considerations

- **min_ton_size**: store as `models.PositiveIntegerField` (unit: liters). Use `verbose_name="Minimum container size (L)"` and help_text.
- **min_ton_volume_per_inhabitant**: store as `models.DecimalField(max_digits=8, decimal_places=2)` (unit: liters per inhabitant). Use `verbose_name="Minimum container volume per inhabitant (L/person)"`.
- **Input widget**: initially use `forms.NumberInput` for free numeric entry; later migrate to `forms.ChoiceField` with dropdown of common values when enough data is gathered.
- **Future work**: consider separate model or lookup table for standard container sizes if `min_ton_size` options grow.

## Proposed Changes
1. **Models**: Add two new fields to `Collection` in `case_studies/soilcom/models.py`:
   - `min_ton_size`
   - `min_ton_volume_per_inhabitant`
2. **Migrations**: Generate and apply a migration for the new fields.
3. **Serializers**: Update `case_studies/soilcom/serializers.py` to include the new fields in `CollectionSerializer`.
4. **Forms**: Update `case_studies/soilcom/forms.py` (e.g., `CollectionModelForm`) to include the new fields.
5. **Filters**: Extend `case_studies/soilcom/filters.py` to allow filtering by the new fields.
6. **Views/ViewSets**: Ensure `case_studies/soilcom/viewsets.py` (or `views.py`) supports create/update of the new fields.
7. **Admin**: Optionally adjust `case_studies/soilcom/admin.py` to display/edit the new fields.
8. **Templates**: Update templates under `case_studies/soilcom/templates/` to render inputs for the new fields where collections are created/edited.
9. **Tests**: Update or add tests in:
   - `tests/test_models.py`
   - `tests/test_serializers.py`
   - `tests/test_forms.py`
   - `tests/test_filters.py`
   - `tests/test_views.py`
10. **Documentation**: Update any docs or README to mention the new fields.
11. **CI/Tests**: Run full test suite and update expected outputs if needed.
12. **Export**: Update export tasks (`case_studies/soilcom/tasks.py`) and renderers (`case_studies/soilcom/renderers.py`) to include the new fields in exported outputs.

## Affected Code Checklist
- [ ] case_studies/soilcom/models.py (Collection model)
- [ ] case_studies/soilcom/migrations (new migration)
- [ ] case_studies/soilcom/serializers.py (CollectionSerializer)
- [ ] case_studies/soilcom/forms.py (CollectionModelForm)
- [ ] case_studies/soilcom/filters.py (filter sets)
- [ ] case_studies/soilcom/viewsets.py or views.py (CollectionViewSet)
- [ ] case_studies/soilcom/admin.py (admin for Collection)
- [ ] case_studies/soilcom/tasks.py (export tasks)
- [ ] case_studies/soilcom/renderers.py (export renderers)
- [ ] case_studies/soilcom/templates/... (collection create/edit templates)
- [ ] case_studies/soilcom/tests/test_models.py
- [ ] case_studies/soilcom/tests/test_serializers.py
- [ ] case_studies/soilcom/tests/test_forms.py
- [ ] case_studies/soilcom/tests/test_filters.py
- [ ] case_studies/soilcom/tests/test_views.py
- [ ] docs/ or README.md if applicable
