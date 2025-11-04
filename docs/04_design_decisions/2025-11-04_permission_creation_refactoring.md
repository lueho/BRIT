# Permission Creation Refactoring - November 4, 2025

## Status: IMPLEMENTED

## Context

The BRIT project automatically creates `can_moderate_<model>` permissions for all `UserCreatedObject` subclasses to support the review workflow. Previously, this logic had redundancy and inconsistency issues:

### Problems with Previous Implementation

1. **Triple Redundancy**: Permissions were created in three different places:
   - `utils/object_management/signals.py` (post_migrate signal)
   - `utils/object_management/utils.py` (ensure_initial_data function)
   - `bibliography/models.py` (explicit Meta.permissions for Source model)

2. **Inconsistent Test Behavior**: The signal had a `TESTING` check that prevented permission creation during tests, but tests explicitly created permissions, causing:
   - Duplication of logic between signal and tests
   - Potential for drift between production and test behavior
   - IntegrityError when tests tried to create permissions that already existed (after removing TESTING check)

3. **Execution Order Issues**: The `ensure_initial_data` function ran after every app's migrations during tests, performing redundant work

## Decision

Centralize permission creation in **one place only**: the `post_migrate` signal in `utils/object_management/signals.py`.

### Implementation Details

1. **Signal-based creation (ONLY)**:
   - Removed `TESTING` check from signal handler
   - Signal now runs in ALL environments (dev, production, tests)
   - Uses `get_or_create()` for idempotency

2. **Removed duplication**:
   - Deleted permission creation logic from `utils.py`
   - Removed explicit `Meta.permissions` from `Source` model
   - Deleted migration `bibliography/migrations/0004_add_can_moderate_source_permission.py`

3. **Updated tests**:
   - Changed all tests from `Permission.objects.create()` to `Permission.objects.get()`
   - Tests now fetch auto-created permissions instead of creating them
   - Files updated:
     - `utils/object_management/tests/test_models.py`
     - `utils/object_management/tests/test_permissions.py`
     - `utils/object_management/tests/test_views.py`
     - `utils/object_management/tests/test_modal_views.py`

4. **Test runner optimization**:
   - Added module-level flag `_initial_data_loaded` in `testrunner.py`
   - Prevents `ensure_initial_data` from running multiple times during test setup
   - `ensure_initial_data` now only creates the default owner user

## Benefits

### 1. Single Source of Truth
- Permission creation happens in exactly one place
- No confusion about where permissions come from
- Easier to maintain and debug

### 2. Consistent Behavior
- Same permission creation logic in all environments
- No special cases for tests
- Production and test environments are identical

### 3. Better Test Reliability
- No race conditions or timing issues
- Permissions guaranteed to exist when tests need them
- No IntegrityError from duplicate creation attempts

### 4. Follows DRY Principle
- Eliminated duplicate permission creation code
- Tests don't need to know HOW permissions are created
- Clear separation of concerns

### 5. Automatic for New Models
- Any new `UserCreatedObject` subclass automatically gets moderation permissions
- No manual setup required
- No migrations needed for permissions

## Changes Made

### Code Changes

| File | Change | Reason |
|------|--------|--------|
| `utils/object_management/signals.py` | Removed `TESTING` check | Permissions now created in all environments |
| `utils/object_management/utils.py` | Removed permission creation logic | Eliminated duplication |
| `utils/tests/testrunner.py` | Added `_initial_data_loaded` flag | Prevent multiple executions |
| `bibliography/models.py` | Removed `Meta.permissions` | Rely on signal instead |
| `utils/object_management/tests/test_*.py` | Changed `.create()` to `.get()` | Fetch auto-created permissions |

### Documentation Changes

| File | Change | Purpose |
|------|--------|---------|
| `utils/object_management/README.md` | **NEW** | Comprehensive permission system documentation |
| `docs/02_developer_guide/user_created_objects.md` | Updated "Per-model moderator permission" section | Reflect new behavior, add testing guidance |
| `utils/object_management/signals.py` | Added module docstring | Inline documentation for developers |
| `utils/object_management/utils.py` | Updated docstring | Clarify it only handles default owner |
| `docs/04_design_decisions/2025-11-04_permission_creation_refactoring.md` | **NEW** | This decision record |

## Test Results

All 4,266 tests pass successfully after the refactoring:

```bash
$ docker compose exec web python manage.py test --noinput --settings=brit.settings.testrunner --parallel 4
Ran 4266 tests in 88.029s
OK (skipped=1051)
```

No errors related to permission creation or integrity constraints.

## Migration Path

### For Existing Code

No changes required to existing code that uses permissions. The system remains backward compatible:

- `UserCreatedObjectPermission._is_moderator()` works the same
- Template tags (`can_moderate`) work the same
- Permission checking in views works the same

### For New Tests

When writing new tests for `UserCreatedObject` models:

```python
# ✅ CORRECT: Fetch the auto-created permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Permission

content_type = ContentType.objects.get_for_model(MyModel)
permission = Permission.objects.get(
    codename="can_moderate_mymodel",
    content_type=content_type,
)
user.user_permissions.add(permission)

# ❌ WRONG: Don't try to create it
# Will cause IntegrityError!
permission = Permission.objects.create(
    codename="can_moderate_mymodel",
    name="Can moderate my models",
    content_type=content_type,
)
```

### For New Models

No setup needed! When you create a new model that inherits from `UserCreatedObject`:

```python
from utils.object_management.models import UserCreatedObject

class MyNewModel(UserCreatedObject):
    name = models.CharField(max_length=255)
```

The `can_moderate_mynewmodel` permission is automatically created during the next migration.

## Technical Details

### Signal Flow

```
1. Django migrations run (migrate command or test setup)
   ↓
2. post_migrate signal fires for each app
   ↓
3. ensure_moderation_permissions() executes
   ↓
4. _iter_user_created_models() discovers all UserCreatedObject subclasses
   ↓
5. For each model:
   - Get or create can_moderate_<model> permission
   - Assign to moderators group
   ↓
6. Ready for use in views, templates, and tests
```

### Idempotency

The signal is safe to run multiple times:
- Uses `Permission.objects.get_or_create()` (no duplicate creation)
- Uses `Group.objects.get_or_create()` (no duplicate groups)
- Uses `group.permissions.add()` (no duplicate assignments)

### Performance

- Runs once per migration
- Cached by Django's permission framework
- Minimal overhead (~milliseconds for dozens of models)

## Related Documentation

- [UserCreatedObject Permission System](../02_developer_guide/user_created_objects.md)
- [Object Management Package](../../utils/object_management/README.md)
- [Initial Data Management](../02_developer_guide/initial_data_management.md)

## Authors

- Implementation: Cascade AI Assistant
- Review: Phillipp Lüssenhop
- Date: November 4, 2025
