# Object Management Package

This package provides the core infrastructure for managing user-created objects in BRIT, including base models, views, permissions, and the review workflow.

## Table of Contents

- [Base Models](#base-models)
- [Permission System](#permission-system)
- [Review Workflow](#review-workflow)
- [Views and ViewSets](#views-and-viewsets)
- [Testing](#testing)

## Base Models

### UserCreatedObject

The base model for all objects created by users. Provides:

- **Owner tracking**: Every object has an `owner` (ForeignKey to User)
- **Publication status**: Objects can be `private`, `in_review`, `published`, `declined`, or `archived`
- **Timestamps**: Automatic tracking of creation and modification times
- **Approval workflow**: Fields for tracking approval/rejection by moderators

### NamedUserCreatedObject

Extends `UserCreatedObject` with a `name` field and automatic slug generation.

### GlobalObject

Base model for globally accessible objects that don't require ownership tracking.

## Permission System

### Overview

BRIT uses a centralized permission system for `UserCreatedObject` models with automatic permission creation and management.

### Automatic Permission Creation

**How it works:**

1. **Signal-based creation**: A `post_migrate` signal handler in `utils/object_management/signals.py` automatically creates `can_moderate_<model>` permissions for all `UserCreatedObject` subclasses.

2. **Runs everywhere**: The signal runs in all environments (development, production, and **tests**) to ensure consistent behavior.

3. **Idempotent**: Uses `get_or_create()` to safely handle multiple executions without errors.

4. **Group assignment**: Permissions are automatically assigned to the moderators group (configurable via `settings.REVIEW_MODERATORS_GROUP_NAME`, defaults to `"moderators"`).

**Example:**

For a model `Collection(UserCreatedObject)`:
- Permission codename: `can_moderate_collection`
- Permission name: `"Can moderate collections"`
- Content type: Links to the `Collection` model
- Assigned to: The `moderators` group

### Permission Naming Convention

All moderation permissions follow this pattern:
- **Codename**: `can_moderate_<model_name>` (lowercase model name)
- **Name**: `"Can moderate <verbose_name_plural>"`

### Configuration

**Settings:**

```python
# settings.py
REVIEW_MODERATORS_GROUP_NAME = "moderators"  # Default group for moderators
```

**No manual setup required** - permissions are created automatically during migrations.

### Usage in Code

**Checking if a user is a moderator:**

```python
from utils.object_management.permissions import UserCreatedObjectPermission

permission = UserCreatedObjectPermission()
is_moderator = permission._is_moderator(user, obj)
```

**In views:**

```python
# CBV mixins handle this automatically
class MyDetailView(UserCreatedObjectReadAccessMixin, DetailView):
    model = MyModel  # Permissions checked automatically
```

**In templates:**

```django
{% load moderation_tags %}

{# Check if user can moderate this object #}
{% if user|can_moderate:object %}
  <a href="{% url 'approve' object.pk %}">Approve</a>
{% endif %}
```

**In DRF viewsets:**

```python
from utils.object_management.viewsets import UserCreatedObjectViewSet

class MyViewSet(UserCreatedObjectViewSet):
    # Permissions handled automatically
    queryset = MyModel.objects.all()
```

### Testing

**Important**: Tests should **fetch** permissions, not create them.

```python
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Permission

def setUp(self):
    # ✅ CORRECT: Fetch the auto-created permission
    content_type = ContentType.objects.get_for_model(MyModel)
    permission = Permission.objects.get(
        codename="can_moderate_mymodel",
        content_type=content_type,
    )
    user.user_permissions.add(permission)
    
    # ❌ WRONG: Don't try to create it
    # permission = Permission.objects.create(...)  # Will cause IntegrityError!
```

The signal creates all `can_moderate_<model>` permissions during test database setup, so they're guaranteed to exist.

## Review Workflow

### States

Objects can be in one of five publication states:

1. **private**: Only visible to owner and staff
2. **in_review**: Submitted for moderation review
3. **published**: Publicly visible
4. **declined**: Rejected by moderators with feedback
5. **archived**: No longer active but preserved

### Actions

| Action | Who can perform | State transition |
|--------|----------------|------------------|
| Submit for review | Owner | private/declined → in_review |
| Withdraw | Owner | in_review → private |
| Approve | Moderator (not owner) | in_review → published |
| Reject | Moderator (not owner) | in_review → declined |
| Archive | Owner/Moderator/Staff | published → archived |

### Four-Eyes Principle

Moderators cannot approve or reject their own submissions. This ensures independent review.

## Views and ViewSets

### Class-Based Views (CBVs)

**List Views:**
- `PublishedObjectListView`: Public objects
- `PrivateObjectListView`: User's private objects
- `ReviewObjectListView`: Objects under review (moderators only)

**CRUD Views:**
- `UserCreatedObjectCreateView`
- `UserCreatedObjectDetailView`
- `UserCreatedObjectUpdateView`
- `UserCreatedObjectDeleteView`

**Review Views:**
- `ReviewItemDetailView`: Special view for reviewing objects
- `UserCreatedObjectModalSubmitView`: Submit for review
- `UserCreatedObjectModalWithdrawView`: Withdraw from review
- `UserCreatedObjectModalApproveView`: Approve submission
- `UserCreatedObjectModalRejectView`: Reject submission

#### Review detail routing and runtime delegation

- URL routing always targets `ReviewItemDetailView.as_view()` via
  `object_management:review_item_detail`.
- `ReviewItemDetailView.dispatch()` resolves the object first, then checks the
  internal `_model_view_registry`.
- If a model-specific subclass was registered with `register_for_model()`,
  dispatch delegates to that specialized class at runtime.
- Example: `CollectionReviewItemDetailView.register_for_model(Collection)` keeps
  URL routing unchanged while enabling collection-specific context handling.

This is why tools that inspect URL resolution (for example Debug Toolbar) may
show `ReviewItemDetailView` as the endpoint even though specialized logic runs.

### DRF ViewSets

```python
from utils.object_management.viewsets import UserCreatedObjectViewSet

class MyViewSet(UserCreatedObjectViewSet):
    queryset = MyModel.objects.all()
    serializer_class = MySerializer
    
    # Inherited actions:
    # - register_for_review
    # - withdraw_from_review  
    # - approve
    # - reject
    # - archive
```

## Architecture

### Signal Flow

```
1. Django migrations run
   ↓
2. post_migrate signal fires
   ↓
3. ensure_moderation_permissions() executes
   ↓
4. Iterates all UserCreatedObject subclasses
   ↓
5. Creates can_moderate_<model> permissions
   ↓
6. Assigns to moderators group
```

### Files

- **`signals.py`**: Permission creation signal handler
- **`permissions.py`**: Permission classes and policy helpers
- **`models.py`**: Base models (UserCreatedObject, etc.)
- **`views.py`**: CBVs for CRUD and review workflow
- **`viewsets.py`**: DRF viewsets with permission checks
- **`utils.py`**: Initial data management (default owner creation)

## Migration from Old Pattern

**Before (deprecated):**
```python
# ❌ Manual permission creation in tests
permission = Permission.objects.create(
    codename="can_moderate_collection",
    name="Can moderate collections",
    content_type=content_type,
)
```

**After (current):**
```python
# ✅ Fetch auto-created permission
permission = Permission.objects.get(
    codename="can_moderate_collection",
    content_type=content_type,
)
```

**Why the change:**
- Ensures permissions exist consistently across all environments
- Eliminates duplication between signal creation and test setup
- Makes tests more reliable (no race conditions)
- Follows DRY principle

## See Also

- [UserCreatedObject Permission System](../../docs/02_developer_guide/user_created_objects.md) - Detailed permission rules
- [Initial Data Management](../../docs/02_developer_guide/initial_data_management.md) - How initial data is created
- `permissions.py` - Source code for permission logic
- `signals.py` - Source code for automatic permission creation
