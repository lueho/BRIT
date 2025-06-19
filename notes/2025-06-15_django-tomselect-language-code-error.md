# Django TomSelect LANGUAGE_CODE Filter Error Investigation

**Date:** 2025-06-15  
**Status:** UNRESOLVED - Root cause partially identified  
**Priority:** High - Affects test runs and app functionality

## Problem Summary

Django TomSelect autocomplete widgets are incorrectly receiving the `LANGUAGE_CODE` value ('en-us') as a filter parameter for the 'scope' field during test runs and normal usage. This causes the following error:

```
Error in get_queryset: 'en-us', falling back to EmptyModel.objects.none()
```

The error originates from `django-tomselect`'s `TomSelectModelWidget.get_queryset()` method when it tries to apply the scope filter with 'en-us' instead of the expected values ("published" or "private").

## Root Cause Analysis

### Key Findings

1. **Filter Definition Issue**: The `UserCreatedObjectScopedFilterSet` defines a `scope` field as a hidden `ChoiceFilter` with choices "published" and "private", but it has a hardcoded `initial="published"` value.

2. **View Context Mismatch**: Both `PublishedObjectFilterView` and `PrivateObjectFilterView` use the same filter set, but:
   - `PublishedObjectFilterView` should use `scope="published"` 
   - `PrivateObjectFilterView` should use `scope="private"`

3. **FilterDefaultsMixin Logic**: The `FilterDefaultsMixin.get_default_filters()` method simply reads the `initial` value from each filter, providing no mechanism for views to override based on context.

4. **Partial Fix Attempted**: Added `get_default_filters()` override to `PrivateObjectFilterView` to set scope to "private", but the LANGUAGE_CODE error persists.

5. **TomSelect Widget Behavior**: The issue appears to be in how the TomSelect JavaScript or widget resolves dependent field values, particularly for hidden fields.

### Technical Details

- **Filter Location**: `utils/object_management/filters.py` - `UserCreatedObjectScopedFilterSet`
- **Affected Views**: 
  - `utils/object_management/views.py` - `PublishedObjectFilterView`, `PrivateObjectFilterView`
- **Widget Usage**: Various autocomplete views using `filter_by=("scope", "name")` configuration
- **Error Origin**: `django-tomselect` package's `TomSelectModelWidget.get_queryset()` method

## Investigation Steps Taken

1. ✅ Traced widget instantiation and parameter flow to `get_queryset`
2. ✅ Audited filter_by usage and dependent field value resolution
3. ✅ Added debugging to TomSelect widget (reverted - package installed via pip)
4. ✅ Investigated FilterDefaultsMixin and view context handling
5. ✅ Added `get_default_filters()` override to `PrivateObjectFilterView`
6. ✅ Confirmed no template/DOM conflicts with `id_scope` elements
7. ✅ Ruled out TraceOnceStr wrapper as root cause

## Current Status

- **Partial Fix**: `PrivateObjectFilterView` now correctly overrides scope to "private"
- **Persistent Issue**: LANGUAGE_CODE ('en-us') error still occurs despite the fix
- **Root Cause**: Likely in TomSelect JavaScript value resolution for hidden fields or fallback logic when expected values are missing

## Potential Solutions (Untested)

1. **Server-Side Logging**: Add debugging to `UserCreatedObjectAutocompleteView.apply_filters()` to trace incoming parameters
2. **Widget Type Change**: Temporarily change scope field widget from `HiddenInput` to visible input for debugging
3. **Custom TomSelect Build**: Create custom django-tomselect build with debugging for widget value resolution
4. **JavaScript Inspection**: Add client-side logging to trace how TomSelect JS resolves dependent field values

## Impact

- Repeated error messages during test runs
- Potential autocomplete functionality failures in views using scope filtering
- Reduced query performance due to fallback to empty querysets

## Files Modified

- `utils/object_management/views.py`: Added `get_default_filters()` override to `PrivateObjectFilterView`

## Next Steps

1. Add server-side logging to autocomplete view to trace parameter passing
2. Investigate TomSelect JavaScript value resolution logic
3. Consider temporary workarounds (e.g., different widget types)
4. If necessary, create custom django-tomselect build for debugging

---

**Note**: This issue may be related to the broader jQuery/Select2 to TomSelect migration effort tracked in `2025-06-06_jquery-select2-to-tomselect-migration.md`.
