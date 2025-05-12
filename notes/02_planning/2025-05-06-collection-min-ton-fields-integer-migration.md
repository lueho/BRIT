# Migration: min_ton_volume_per_inhabitant to PositiveIntegerField

## Date
2025-05-06

## Context
- The field `min_ton_volume_per_inhabitant` in the Collection model was previously a `DecimalField`.
- It is now a `PositiveIntegerField` to match the requirements for integer-only container volumes per inhabitant.
- All forms, serializers, and filters have been updated to use integer handling.

## Steps Taken
- Updated model field to `PositiveIntegerField` (nullable, blank allowed).
- Updated serializer to use `IntegerField`.
- Updated form to use `IntegerField` with `min_value=0`.
- Updated filter to use integer step size.
- Confirmed all relevant duplication/versioning logic passes the value correctly.

## Migration Required
Run the following commands in your dev environment to apply the database schema change:

```
docker compose exec web python manage.py makemigrations case_studies.soilcom
docker compose exec web python manage.py migrate case_studies.soilcom
```

**NOTE:** Review any data in this field for non-integer values before migrating. Non-integer values will be truncated or may cause errors.

## Verification
- After migration, test creation, duplication, and versioning of collections with various values for `min_ton_volume_per_inhabitant`.
- Check UI for correct field rendering and validation.

## Related Issues
- Ensures consistency for all code paths using this field.
- No mock data or stubbing was introduced.

---

**This note supersedes any earlier docs about the field type for `min_ton_volume_per_inhabitant`.**
