# Moderation Permissions Implementation

## Overview
This document explains the moderation permission system in the processes module and how it aligns with other BRIT modules.

## What Was Checked

### 1. **System-Wide Permission Pattern**
The BRIT framework uses a standardized permission pattern for object moderation:
- Permission name format: `can_moderate_<modelname>`
- Checked via: `UserCreatedObjectPermission().is_moderator(user, obj)`
- Location: `/utils/object_management/permissions.py` (lines 157-168)

### 2. **Other Modules Reviewed**
- **soilcom**: Templates use `perms.soilcom.can_moderate_collection` for Collection model
- **bibliography**: Source model doesn't define custom moderation permissions (relies on staff-only)
- **materials**: Material model doesn't define custom moderation permissions (relies on staff-only)
- **maps**: Catchment model doesn't define custom moderation permissions (relies on staff-only)

### 3. **Base Template Integration**
Base templates (`filtered_list.html`, `simple_list_card.html`) use:
```django
{% if user|can_moderate:object_list.model %}
```
This filter delegates to `UserCreatedObjectPermission.is_moderator()` which checks:
```python
user.is_staff or user.has_perm(f"{app_label}.can_moderate_{model_name}")
```

## What Was Missing

The `Process` and `ProcessCategory` models did **not** have moderation permissions defined in their Meta classes.

### Before
```python
class ProcessCategory(NamedUserCreatedObject):
    class Meta:
        verbose_name = "Process category"
        verbose_name_plural = "Process categories"
        # ❌ No permissions defined

class Process(NamedUserCreatedObject):
    class Meta:
        ordering = ["name", "id"]
        # ❌ No permissions defined
```

## What Was Fixed

### 1. **Added Permissions to Models**

#### ProcessCategory
```python
class ProcessCategory(NamedUserCreatedObject):
    class Meta:
        verbose_name = "Process category"
        verbose_name_plural = "Process categories"
        permissions = [
            ("can_moderate_processcategory", "Can moderate process categories"),
        ]
```

#### Process
```python
class Process(NamedUserCreatedObject):
    class Meta:
        ordering = ["name", "id"]
        permissions = [
            ("can_moderate_process", "Can moderate processes"),
        ]
```

### 2. **Created Migration**
- Migration: `0005_add_moderation_permissions.py`
- Registers the new permissions in the database
- Alters model options for both Process and ProcessCategory

### 3. **Verified Permissions**
```bash
$ python manage.py shell -c "..."
Process permissions: 
  - add_process
  - can_moderate_process ✅ NEW
  - change_process
  - delete_process
  - view_process

ProcessCategory permissions:
  - add_processcategory
  - can_moderate_processcategory ✅ NEW
  - change_processcategory
  - delete_processcategory
  - view_processcategory
```

## How Moderation Works

### Permission Hierarchy
1. **Staff users**: Always have moderation rights (bypass permission checks)
2. **Moderators**: Users with `processes.can_moderate_process` or `processes.can_moderate_processcategory`
3. **Regular users**: No moderation rights

### Moderation Capabilities
Users with moderation permissions can:
- ✅ View objects in review status
- ✅ Approve objects for publication (four-eyes principle: cannot approve own objects)
- ✅ Reject objects in review with feedback
- ✅ Archive published objects
- ✅ View private objects from other users (in review/moderation context)
- ❌ Cannot edit object content (only change publication_status)
- ❌ Cannot approve their own objects

### Four-Eyes Principle
The system enforces that:
- Owners cannot approve/reject their own objects
- Moderators who are also the owner cannot publish directly
- At least two people must be involved: creator and moderator

### Template Integration
The base templates automatically show/hide UI elements based on moderation rights:

**Scope Switcher**
```django
{% if user|can_moderate:object_list.model %}
  <a href="{{ review_url }}">Review</a>
{% endif %}
```

**Action Buttons** (via `object_policy` tag)
```django
{% object_policy object as policy %}
{% if policy.can_approve %}
  <button>Approve</button>
{% endif %}
{% if policy.can_reject %}
  <button>Reject</button>
{% endif %}
```

## Assigning Moderators

### Via Django Admin
1. Go to **Admin > Users** > Select user
2. Under **User permissions**, add:
   - `processes | process | Can moderate processes`
   - `processes | process category | Can moderate process categories`

### Via Management Command (Future)
```python
from django.contrib.auth.models import User, Permission

user = User.objects.get(username='moderator_name')
perms = Permission.objects.filter(
    codename__in=['can_moderate_process', 'can_moderate_processcategory']
)
user.user_permissions.add(*perms)
```

### Via Groups (Recommended)
Create a "Process Moderators" group with these permissions and assign users to the group.

## Testing Moderation

### Test Scenarios
1. **Anonymous user**: Cannot see review scope, cannot access review items
2. **Authenticated user**: Can see own private objects, cannot see others' private/review objects
3. **Process moderator**: Can see review scope, access review items, approve/reject
4. **Staff user**: Full access, acts as super-moderator

### Test Commands
```bash
# Check user permissions
python manage.py shell -c "
from django.contrib.auth.models import User
user = User.objects.get(username='testuser')
print('Has process moderation:', user.has_perm('processes.can_moderate_process'))
print('Has category moderation:', user.has_perm('processes.can_moderate_processcategory'))
"

# Check if permission exists
python manage.py shell -c "
from django.contrib.auth.models import Permission
print(Permission.objects.filter(codename__startswith='can_moderate').values('codename', 'name'))
"
```

## Integration Points

### 1. **Views**
All CRUD views inherit from `UserCreatedObjectPermission` which automatically:
- Filters querysets based on user permissions
- Checks object-level permissions
- Enforces review workflow rules

### 2. **Viewsets (DRF)**
```python
class ProcessViewSet(UserCreatedObjectViewSet):
    permission_classes = [UserCreatedObjectPermission]
    # Automatically handles moderation permissions
```

### 3. **Templates**
- Use `{% if user|can_moderate:object %}` for moderation checks
- Use `{% object_policy object as policy %}` for detailed action permissions
- Base templates automatically show/hide review scope toggle

### 4. **Permissions Module**
- `UserCreatedObjectPermission._is_moderator(user, obj)` - Core check
- `user_is_moderator_for_model(user, model_class)` - Helper function
- `get_object_policy(user, obj)` - Full policy dictionary for templates

## Migration Notes

### When to Run
```bash
python manage.py migrate processes
```

### Safe to Run
- ✅ Non-destructive (only adds permissions)
- ✅ No data changes
- ✅ No schema changes (only Meta options)
- ✅ Can be run in production

### Rollback (if needed)
```bash
python manage.py migrate processes 0004
```

## Best Practices

### 1. **Don't Hardcode Staff Checks**
❌ Bad:
```django
{% if user.is_staff %}
```

✅ Good:
```django
{% if user|can_moderate:object %}
```

### 2. **Use Policy Dictionaries**
❌ Bad:
```django
{% if user == object.owner or user.is_staff %}
  <button>Edit</button>
{% endif %}
```

✅ Good:
```django
{% object_policy object as policy %}
{% if policy.can_edit %}
  <button>Edit</button>
{% endif %}
```

### 3. **Delegate to Permission Classes**
Views and viewsets should use `UserCreatedObjectPermission` rather than implementing custom permission logic.

## Future Enhancements

1. **Group-based moderation**: Create "Process Moderators" group
2. **Audit logging**: Track who approved/rejected what
3. **Notification system**: Alert moderators of new review items
4. **Moderation dashboard**: Dedicated view for review queue
5. **Batch operations**: Approve/reject multiple items at once

## Related Documentation

- `/utils/object_management/permissions.py` - Permission framework
- `/utils/object_management/templatetags/moderation_tags.py` - Template filters
- `/brit/templates/filtered_list.html` - List template with review scope
- `/brit/templates/detail_with_options.html` - Detail template with actions
