# Utils App Refactoring: UserCreatedObject and GlobalObject Submodule

## Overview
Refactor the utils app to move UserCreatedObject and GlobalObject abstract base models and their related logic into a dedicated submodule for better organization and separation of concerns.

## Current State Analysis
- **UserCreatedObject**: Abstract base model with ownership, publication status workflow (private → review → published → archived)
- **GlobalObject**: Simple abstract base model for global objects with name/description
- Related components scattered across utils app:
  - Models: `UserCreatedObject`, `GlobalObject`, `NamedUserCreatedObject` in `models.py`
  - Permissions: `UserCreatedObjectPermission` in `permissions.py`
  - ViewSets: `UserCreatedObjectViewSet`, `GlobalObjectViewSet` in `viewsets.py`
  - Views: Multiple mixins and views in `views.py`
  - Tests: Comprehensive test coverage in `tests/`

## Target Structure
```
utils/
├── object_management/           # New submodule
│   ├── __init__.py
│   ├── models.py               # UserCreatedObject, GlobalObject, NamedUserCreatedObject
│   ├── permissions.py          # UserCreatedObjectPermission 
│   ├── viewsets.py            # UserCreatedObjectViewSet, GlobalObjectViewSet
│   ├── views.py               # All related view mixins and classes
│   └── tests/                 # All related tests
│       ├── __init__.py
│       ├── test_models.py
│       ├── test_permissions.py
│       ├── test_viewsets.py
│       └── models.py          # Test models
├── [other existing files...]
```

## Task Checklist

### Phase 1: Create Submodule Structure
- [ ] Create `utils/object_management/` directory
- [ ] Create `utils/object_management/__init__.py` with proper imports
- [ ] Create empty files for the new module structure

### Phase 2: Move Models
- [ ] Move `UserCreatedObject`, `GlobalObject`, `NamedUserCreatedObject` from `utils/models.py` to `utils/object_management/models.py`
- [ ] Move related functions: `get_default_owner`, `get_default_owner_pk`, `STATUS_CHOICES`
- [ ] Move `UserCreatedObjectQuerySet`, `UserCreatedObjectManager`
- [ ] Update imports in `utils/models.py` to re-export from new location
- [ ] Verify all existing imports still work

### Phase 3: Move Permissions
- [ ] Move `UserCreatedObjectPermission` from `utils/permissions.py` to `utils/object_management/permissions.py`
- [ ] Update imports in `utils/permissions.py` to re-export
- [ ] Verify all permission usage still works

### Phase 4: Move ViewSets
- [ ] Move `UserCreatedObjectViewSet`, `GlobalObjectViewSet` from `utils/viewsets.py` to `utils/object_management/viewsets.py`
- [ ] Update imports in `utils/viewsets.py` to re-export
- [ ] Verify API endpoints still work

### Phase 5: Move Views
- [ ] Move all UserCreatedObject-related view mixins and classes from `utils/views.py` to `utils/object_management/views.py`
- [ ] Update imports in `utils/views.py` to re-export
- [ ] Verify all view functionality still works

### Phase 6: Move Tests
- [ ] Create `utils/object_management/tests/` directory
- [ ] Move related test files to new location
- [ ] Update test imports and references
- [ ] Verify all tests pass

### Phase 7: Clean Up and Validation
- [ ] Remove old code from original files (keep only re-exports)
- [ ] Update documentation and docstrings
- [ ] Run full test suite: `docker compose exec web python manage.py test --keepdb --noinput --settings=brit.settings.testrunner --parallel 4`
- [ ] Run deployment checks: `docker compose exec web python manage.py check --deploy`
- [ ] Verify no circular imports
- [ ] Clean up any dead code or unused imports

### Phase 8: Documentation
- [ ] Update `utils/README.md` to document new structure
- [ ] Create ADR for this architectural change
- [ ] Update any developer documentation

## Notes
- Maintain backward compatibility through re-exports
- Keep all existing functionality intact
- Ensure comprehensive test coverage remains
- Follow the principle of minimal disruption to existing code

## Risk Mitigation
- All original imports will continue to work through re-exports
- Tests will validate functionality is preserved
- Incremental approach allows for rollback at any step
