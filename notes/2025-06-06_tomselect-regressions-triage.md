# TomSelect Migration Regressions - Triage & Fix

Date: 2025-06-06  
Goal: Systematically address test failures introduced by TomSelect migration

## Test Results Summary
Total: 4169 tests run
**FAILURES: 10, ERRORS: 7, SKIPPED: 1039**

## Critical Regressions Identified

### 1. Form Initialization Error (TypeError)
**Files Affected**: `utils/forms.py`
**Error**: `BaseModelForm.__init__() got an unexpected keyword argument 'region_id'`
**Failing Tests**:
- `inventories.tests.test_views.ScenarioCRUDViewsTestCase.*`
- Multiple scenario CRUD operations failing

**Root Cause**: TomSelect migration likely changed form initialization signature
**Priority**: HIGH - Blocks all form operations

### 2. Autocomplete API Response Format Change
**Files Affected**: Autocomplete views, particularly Hamburg catchment tests
**Error**: JSON response structure changed from Select2 to TomSelect format
**Expected**: `{'id': '812', 'selected_text': 'Hamburg', 'text': 'Hamburg'}`
**Actual**: `{'id': 812, 'name': 'Hamburg', 'can_view': True, ...}`

**Failing Tests**:
- `case_studies.flexibi_hamburg.tests.test_views.HamburgRoadsideTreeCatchmentAutocompleteViewTests.*`

**Root Cause**: TomSelect uses different JSON field names than Select2
**Priority**: MEDIUM - Breaks autocomplete functionality

### 3. URL Redirect Scope Parameter Issues  
**Files Affected**: Various CRUD views with publication workflow
**Error**: Missing or incorrect `?scope=published/private` parameters in redirects
**Examples**:
- Expected: `/waste_collection/collections/user/?scope=private`
- Actual: `/waste_collection/collections/user/`

**Failing Tests**:
- `case_studies.soilcom.tests.test_views.Collection*CRUDViewsTestCase.test_delete_*`

**Priority**: MEDIUM - Affects post-action navigation

### 4. View Configuration Error
**Files Affected**: `maps/views.py` 
**Error**: `NutsRegionPublishedMapView is missing a QuerySet`
**Failing Tests**:
- `maps.tests.test_views.NutsRegionMapViewTestCase.test_get_http_200_ok_for_anonymous`

**Priority**: LOW - Specific to one view

## Action Plan

### Phase 1: Form Initialization Fix (HIGH)
- [ ] Investigate `utils/forms.py` changes during TomSelect migration
- [ ] Fix `BaseModelForm.__init__()` signature/parameter handling
- [ ] Test scenario CRUD operations

### Phase 2: Autocomplete API Alignment (MEDIUM)  
- [ ] Review TomSelect autocomplete response format requirements
- [ ] Update autocomplete views to use correct field names (`name` vs `text`, etc.)
- [ ] Update test expectations to match TomSelect format

### Phase 3: URL Redirect Scope Parameters (MEDIUM)
- [ ] Review CRUD view redirect logic changes
- [ ] Ensure scope parameters are preserved in post-action redirects
- [ ] Update failing redirect tests

### Phase 4: View Configuration (LOW)
- [ ] Fix `NutsRegionPublishedMapView` QuerySet configuration
- [ ] Test map view functionality

## Focus Order
1. **Form initialization** - Critical blocker
2. **Autocomplete API** - Core functionality  
3. **Redirect scope** - User experience
4. **View config** - Specific edge case

## Next Steps
Start with Phase 1 form initialization to unblock CRUD operations.
