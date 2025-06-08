# Task: Migrate from jQuery/Select2 to TomSelect and django-tomselect

Date: 2025-06-06  
Goal: Remove jQuery dependency by replacing select2 with TomSelect and django-tomselect

## Background
- The project currently uses django-autocomplete-light (3.12.1) with Select2 for autocomplete fields
- Multiple bootstrap-styled Select2 widgets exist in utils/widgets.py
- There are compatibility issues between django-autocomplete-light and django-crispy-forms (documented in previous tasks)
- The goal is to maintain the same UI/UX with minimal code changes while removing jQuery dependency

## Scope Analysis
Based on codebase search, the main components to refactor:

### Core Files to Update:
- **utils/widgets.py**: Contains BSModelSelect2, BSModelSelect2Multiple, BSListSelect2 classes
- **utils/forms.py**: Contains apply_select2_theme function and autocomplete form integration
- **utils/filters.py**: Uses Select2WidgetMixin for filter forms
- **requirements.txt**: Add django-tomselect, remove django-autocomplete-light
- **All app views with autocomplete**: Various *AutocompleteView classes across apps

### Templates/Media:
- **base.html**: Remove django-autocomplete-light JS/CSS includes  
- **SCSS files**: Remove Select2 styling, add TomSelect styling
- **Form media handling**: Update for TomSelect

## Migration Checklist

### Phase 1: Setup and Dependencies
- [x] Add django-tomselect to requirements.txt
- [x] Install and configure django-tomselect in settings
- [x] Update INSTALLED_APPS and URL patterns
- [x] Test basic installation

### Phase 2: Widget Migration
- [x] Create TomSelect equivalent widgets in utils/widgets.py
- [x] Update BSModelSelect2 → BSTomSelectModel
- [x] Update BSModelSelect2Multiple → BSTomSelectModelMultiple  
- [x] Update BSListSelect2 → BSTomSelectList
- [x] Maintain same API/interface for minimal form changes

### Phase 3: Form Integration
- [x] Update utils/forms.py to handle TomSelect widgets instead of Select2
- [x] Replace apply_select2_theme with apply_tomselect_theme
- [x] Update AutocompleteFormMixin and related form classes
- [x] Test form rendering and validation

### Phase 4: View Migration
- [ ] Replace django-autocomplete-light views with django-tomselect equivalents
- [ ] Update all *AutocompleteView classes across apps:
  - maps/views.py: CatchmentAutocompleteView, RegionAutocompleteView, NutsRegionAutocompleteView
  - Other app autocomplete views
- [ ] Update URL patterns in urlpatterns

### Phase 5: Frontend/Templates
- [ ] Remove django-autocomplete-light JS/CSS from base.html
- [ ] Add TomSelect JS/CSS resources
- [ ] Update SCSS to remove Select2 styles, add TomSelect styles
- [ ] Test responsive behavior and Bootstrap 5 integration

### Phase 6: Testing and Cleanup
- [ ] Run full test suite to ensure functionality
- [ ] Test autocomplete behavior across all forms
- [ ] Test multiple select functionality
- [ ] Verify styling consistency with Bootstrap 5
- [ ] Remove django-autocomplete-light from requirements.txt
- [ ] Clean up obsolete Select2 references in code/comments
- [ ] Update documentation and README files

### Phase 7: Final Validation
- [ ] Run python manage.py check --deploy
- [ ] Verify no jQuery dependencies remain (except essential Bootstrap JS)
- [ ] Performance testing - compare autocomplete speed
- [ ] Cross-browser testing
- [ ] Mobile/responsive testing

## Implementation Strategy
- **Minimal API changes**: Keep the same widget interfaces so forms don't need major updates
- **Backward compatibility**: Support gradual migration if needed
- **Testing-first**: Create test cases for autocomplete functionality before migration
- **Documentation**: Update inline comments and docstrings for new widgets

## Notes
- django-tomselect is the recommended Django package for TomSelect integration
- TomSelect is a lightweight, vanilla JS alternative to Select2
- Focus on maintaining existing UX while removing jQuery dependency
- This supports the broader goal of removing sb-admin-2 theme dependencies

## Related Tasks
- Bootstrap 5 migration: notes/2025-06-03_bootstrap5-migration-task.md
- jQuery UI removal: notes/2025-06-06_jquery-ui-removal.md
- Select2 Bootstrap 5 fixes: notes/2025-06-04_select2-bootstrap5-fix.md
