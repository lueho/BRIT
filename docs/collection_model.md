# Collection Model: Minimum Container Volume Field (Integer Migration)

_Last major update: 2025-05-06_

## Overview
The `Collection` model's `min_ton_volume_per_inhabitant` field now uses a positive integer type. This change ensures that only whole-number values (liters per person) are accepted and displayed throughout the application.

## Details
- **Field type:** `PositiveIntegerField` (nullable, optional)
- **Affected UI/logic:**
    - All forms, serializers, filters, and API endpoints now require integer input for this field.
    - All exports (CSV/XLSX) and API responses output integer values for this field.
- **Help text:** Minimum available container volume per inhabitant (in liters per person).

## Rationale
- Aligns with real-world data collection and reporting practices, which use whole liters for this metric.
- Prevents user confusion and data inconsistencies that arose from float/decimal input.

## Migration & Compatibility
- No fake or mock data was introduced outside of tests.
- If upgrading from a previous decimal-based version, ensure that all legacy data is cleaned to use integer values only.
- All related forms, filters, and serializers have been updated to reject non-integer input.

## Testing
- All relevant tests (forms, serializers, filters, renderers) have been updated and now use integer values for this field.
- The test suite passes completely as of this update.

## Related Files
- `case_studies/soilcom/models.py`
- `case_studies/soilcom/forms.py`
- `case_studies/soilcom/serializers.py`
- `case_studies/soilcom/filters.py`
- `case_studies/soilcom/views.py`
- `case_studies/soilcom/tests/`

## Further Reading
- See `notes/2025-05-06-collection-integer-fields-upgrade.md` for a detailed planning and migration log.

---

**This documentation reflects the current production state of the Collection model and related logic.**
