# BRIT Codebase Refactoring Plan

## Overview
This document outlines a comprehensive refactoring plan for the BRIT (Bioresource Inventory Tool) codebase. The plan identifies code that is overly complicated, doesn't follow project conventions, or is obsolete and can be removed.

## 1. Code Organization Issues

### 1.1 Large Files
Several files in the codebase are excessively large and would benefit from being split into smaller, more focused modules:

- **maps/views.py** (917 lines): This file contains many view classes and should be split into multiple files based on functionality:
  - `region_views.py` for Region-related views
  - `catchment_views.py` for Catchment-related views
  - `location_views.py` for Location-related views
  - `attribute_views.py` for Attribute-related views
  - `api_views.py` for API views

- **maps/serializers.py** (361 lines): Should be split into:
  - `map_config_serializers.py` for MapConfiguration-related serializers
  - `region_serializers.py` for Region-related serializers
  - `catchment_serializers.py` for Catchment-related serializers

- **maps/tests/test_views.py** (1240 lines): Should be split to match the view file organization:
  - `test_region_views.py`
  - `test_catchment_views.py`
  - `test_location_views.py`
  - `test_attribute_views.py`
  - `test_api_views.py`

### 1.2 Duplicate Code Sections
There are several instances of duplicate code or comment blocks:

- Duplicate comment blocks in maps/views.py (lines 246-247, 309-310, 367-368, 409-410, etc.)
- Duplicate comment blocks in maps/serializers.py (lines 114-115 and 131-132)
- Duplicate comment blocks in maps/tests/test_views.py (lines 179-180 and 251-252)

## 2. Code Complexity Issues

### 2.1 Complex Methods
Several methods have high cyclomatic complexity and should be refactored:

- **MapMixin.get_map_configuration()** in maps/views.py: This method has multiple nested conditions and fallback logic. It should be refactored to use a strategy pattern or a more declarative approach.

- **MapConfigurationSerializer.to_representation()** in maps/serializers.py: This method has complex logic for building the map configuration. It should be refactored to use helper methods for different parts of the configuration.

- **NutsRegionPedigreeAPI.get()** in maps/views.py: This method has complex logic for building the pedigree data. It should be refactored to use helper methods.

### 2.2 Redundant Conditional Checks
There are several instances of redundant conditional checks:

- In maps/views.py, the `get_catchment_feature_id()` and `get_region_feature_id()` methods have nested `hasattr()` checks that could be simplified.

- In maps/models.py, the `__str__()` method of the Region class has multiple try-except blocks that could be simplified.

## 3. Inconsistent Code Patterns

### 3.1 Inconsistent URL Generation
There are inconsistent approaches to URL generation:

- Some views use `reverse_lazy()` for URL attributes, while others use `reverse()` in methods.
- Some views hardcode URL patterns, while others use the URL naming system.

### 3.2 Inconsistent API Response Formats
The API views return inconsistent response formats:

- Some return `JsonResponse({'geoJson': serializer.data})`, while others return `Response({'summaries': serializer.data})`.
- Some wrap the data in a dictionary, while others return it directly.

### 3.3 Inconsistent Permission Handling
There are inconsistent approaches to permission handling:

- Some views use `permission_required = 'maps.add_location'`, while others use `permission_required = set()`.
- Some views check permissions in the view, while others rely on mixins.

## 4. Obsolete Code

### 4.1 TODO Comments
There are several TODO comments that indicate obsolete or incomplete code:

- In maps/views.py:
  - Line 287: `model_name = None  # TODO: Remove this for pk`
  - Line 306-307: `# def get_dataset(self): # return GeoDataset.objects.get(pk=self.kwargs.get('pk')) # TODO: Implement this functionality`
  - Lines 312 and 319: `# TODO: Implement method to get the model, so that the create_url can be retrieved from the CRUDUrlsMixin`

- In maps/models.py:
  - Line 450: `model_name = models.CharField(max_length=56, choices=GIS_SOURCE_MODELS, null=True)  # TODO remove when switch to generic view is done`
  - Line 463: `# TODO: Check if this should be moved to utils app`

### 4.2 Commented-Out Code
There are instances of commented-out code that should be removed:

- In maps/views.py, lines 306-307: `# def get_dataset(self): # return GeoDataset.objects.get(pk=self.kwargs.get('pk')) # TODO: Implement this functionality`

## 5. Refactoring Recommendations

### 5.1 File Organization
1. Split large files into smaller, more focused modules as outlined in section 1.1.
2. Remove duplicate comment blocks.

### 5.2 Code Simplification
1. Refactor complex methods using helper methods or design patterns.
2. Simplify redundant conditional checks.
3. Use consistent patterns for URL generation, API responses, and permission handling.

### 5.3 Code Cleanup
1. Address TODO comments by either implementing the functionality or removing the comment.
2. Remove commented-out code.
3. Add proper docstrings to classes and methods.

### 5.4 Specific Improvements

#### MapMixin Refactoring
Refactor the MapMixin class to use a more declarative approach:
```python
def get_map_configuration(self):
    """
    Retrieves the appropriate MapConfiguration instance using a prioritized strategy.
    """
    strategies = [
        self._get_map_config_from_object,
        self._get_map_config_from_model,
        self._get_map_config_from_filterset,
        self._get_map_config_from_request,
        self._get_default_map_config
    ]
    
    for strategy in strategies:
        config = strategy()
        if config:
            return config
```

#### Region.__str__() Refactoring
Simplify the Region.__str__() method:
```python
def __str__(self):
    for attr in ['nutsregion', 'lauregion']:
        try:
            return getattr(self, attr).__str__()
        except (AttributeError, Region.DoesNotExist):
            pass
    return self.name
```

#### Consistent API Response Format
Standardize API response format:
```python
def get_response_data(self, serializer, key='data'):
    """Helper method to standardize API response format."""
    return Response({key: serializer.data})
```

## 6. Implementation Priority

1. **High Priority**:
   - Split large files
   - Refactor complex methods
   - Remove obsolete code

2. **Medium Priority**:
   - Standardize API response formats
   - Improve URL generation consistency
   - Simplify redundant conditional checks

3. **Low Priority**:
   - Add comprehensive docstrings
   - Improve test organization
   - Enhance error handling

## 7. Conclusion

This refactoring plan addresses the major issues in the BRIT codebase. Implementing these changes will improve code maintainability, readability, and consistency, making it easier for developers to work with the codebase in the future.