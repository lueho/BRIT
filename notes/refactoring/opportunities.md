# BRIT Project Refactoring Opportunities

This document outlines refactoring opportunities identified in the BRIT (Bioresource Inventory Tool) codebase, along with recommendations for addressing them.

## 1. View Classes Refactoring

### 1.1 Duplicate and Overlapping View Classes

**Issue:** There are multiple view classes with similar functionality and overlapping responsibilities.

**Examples:**
- `OwnedObjectCreateView` and `UserCreatedObjectCreateView` in utils/views.py
- `CreateOwnedObjectMixin` (marked with TODO: EOL) and `CreateUserObjectMixin`
- Multiple modal view classes that could be consolidated

**Recommendation:**
- Deprecate `OwnedObjectCreateView` in favor of `UserCreatedObjectCreateView`
- Remove `CreateOwnedObjectMixin` as it's marked for EOL
- Consolidate modal view classes to reduce duplication

### 1.2 Long View Files

**Issue:** View files are extremely long (e.g., soilcom/views.py is 962 lines, materials/views.py is 860 lines).

**Recommendation:**
- Split view files by model or functionality
- Create separate files for list views, detail views, create/update views, etc.
- Example structure:
  ```
  app/
    views/
      __init__.py  # Re-exports all views
      list_views.py
      detail_views.py
      create_update_views.py
      modal_views.py
      utility_views.py
  ```

### 1.3 Hardcoded Template Paths

**Issue:** Some views have hardcoded template paths.

**Examples:**
- `template_name = '../../brit/templates/modal_form.html'` in flexibi_nantes/views.py

**Recommendation:**
- Use template name resolution based on app and model names
- Define template paths in settings or constants

## 2. Code Duplication

### 2.1 Duplicate CRUD Views

**Issue:** Each model has its own set of CRUD views with similar code.

**Recommendation:**
- Create a factory function or class to generate CRUD views for a model
- Example:
  ```python
  def create_crud_views(model, form_class, **options):
      """Generate CRUD views for a model."""
      return {
          'list_view': PublishedObjectListView.as_view(model=model, **options.get('list', {})),
          'private_list_view': PrivateObjectListView.as_view(model=model, **options.get('private_list', {})),
          'create_view': UserCreatedObjectCreateView.as_view(form_class=form_class, **options.get('create', {})),
          'detail_view': UserCreatedObjectDetailView.as_view(model=model, **options.get('detail', {})),
          'update_view': UserCreatedObjectUpdateView.as_view(model=model, form_class=form_class, **options.get('update', {})),
          'delete_view': UserCreatedObjectModalDeleteView.as_view(model=model, **options.get('delete', {})),
      }
  ```

### 2.2 Duplicate Context Data

**Issue:** Many views have similar `get_context_data` methods with duplicated code.

**Examples:**
- Setting form_title, submit_button_text, etc. in multiple views

**Recommendation:**
- Create a mixin for common context data
- Use class attributes for common context values

### 2.3 Duplicate Form Handling

**Issue:** Many views have similar `form_valid` methods with duplicated code.

**Recommendation:**
- Create mixins for common form handling patterns
- Use class attributes for customization

## 3. Outdated Patterns and TODOs

### 3.1 Marked TODOs

**Issue:** Several TODOs in the codebase indicate areas that need attention.

**Examples:**
- `# TODO: EOL` for CreateOwnedObjectMixin in utils/views.py
- `# TODO: Improve or EOL` for CompositionModalUpdateView in materials/views.py
- `# TODO: Is this still required?` for UpdateGreenhouseGrowthCycleValuesView in flexibi_nantes/views.py
- `# TODO: This is out of use - Decide to fix or remove` for CatchmentSelectView in soilcom/views.py

**Recommendation:**
- Address each TODO by either implementing the improvement or removing the code
- Document decisions for future reference

### 3.2 Inconsistent Permission Handling

**Issue:** Permission handling is inconsistent across views.

**Examples:**
- Some views use `PermissionRequiredMixin`, others use `UserPassesTestMixin`
- Some views check permissions in `has_permission()`, others in `test_func()`

**Recommendation:**
- Standardize permission handling across all views
- Create dedicated mixins for common permission patterns

## 4. Architecture Improvements

### 4.1 View Hierarchy

**Issue:** The view hierarchy is complex and not always clear.

**Recommendation:**
- Simplify the view hierarchy
- Document the view hierarchy and inheritance patterns
- Consider using composition over inheritance where appropriate

### 4.2 Modal vs. Regular Views

**Issue:** There are separate view classes for modal and regular views with duplicated logic.

**Recommendation:**
- Use a single view class with a parameter to determine if it's a modal view
- Use template inheritance to handle modal vs. regular rendering

### 4.3 Formset Handling

**Issue:** Formset handling is complex and duplicated across views.

**Recommendation:**
- Create dedicated mixins for formset handling
- Standardize formset initialization and processing

## 5. Testing Improvements

### 5.1 Test Coverage

**Issue:** While there are comprehensive test cases, it's not clear if all code paths are covered.

**Recommendation:**
- Add test coverage reporting
- Ensure all views and edge cases are tested

### 5.2 Test Duplication

**Issue:** Test cases have some duplication.

**Recommendation:**
- Use parameterized tests where appropriate
- Extract common test setup and assertions into helper methods

## 6. Documentation

### 6.1 Code Documentation

**Issue:** Some code lacks documentation or has outdated documentation.

**Recommendation:**
- Add docstrings to all classes and methods
- Document class hierarchies and design patterns
- Keep documentation up-to-date with code changes

### 6.2 Architecture Documentation

**Issue:** The overall architecture is not well-documented.

**Recommendation:**
- Create architecture diagrams
- Document design decisions and patterns
- Create a developer guide for common tasks

## Implementation Progress

### Completed Refactoring

1. **View Classes Refactoring**
   - Created a new `UserCreatedObjectCreateView` class in utils/views.py based on `OwnedObjectCreateView`
   - Marked `OwnedObjectCreateView` as deprecated with a notice in the docstring
   - Fixed hardcoded template paths in case_studies/flexibi_nantes/views.py:
     - Changed `template_name = '../../brit/templates/modal_form.html'` to `template_name = 'modal_form.html'` in:
       - `CultureModalUpdateView`
       - `GreenhouseModalUpdateView`
       - `GrowthCycleCreateView`

2. **Outdated Patterns and TODOs**
   - Marked classes with "TODO: EOL" as deprecated:
     - `HasModelPermission` in utils/permissions.py
     - `FieldLabelMixin` in utils/serializers.py

## Implementation Plan

1. **Phase 1: Clean up TODOs and deprecated code**
   - Remove code marked with EOL
   - Address simple TODOs
   - Document decisions

2. **Phase 2: Consolidate duplicate view classes**
   - Merge similar view classes
   - Create mixins for common functionality
   - Update references to deprecated classes

3. **Phase 3: Restructure view files**
   - Split large view files by functionality
   - Standardize imports and organization
   - Update URL configurations

4. **Phase 4: Improve architecture**
   - Implement view factories
   - Standardize permission handling
   - Improve formset handling

5. **Phase 5: Enhance testing and documentation**
   - Add test coverage reporting
   - Improve test organization
   - Update documentation

Each phase should include thorough testing to ensure no regressions are introduced.
