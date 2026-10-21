# Object Management Package

This package provides the core infrastructure for managing user-created objects in BRIT, including base models, views, permissions, and the review workflow.

> **Migration status — legacy runtime reference:** The permission provisioning and action summaries below describe the pre-migration implementation at the start of the authorization review stack, not the target authorization rules. Later stacked parts migrate these paths incrementally. Follow the [canonical authorization contract](../../docs/02_developer_guide/security_permission_validation.md); staff status alone must not grant application moderation. Update or replace each legacy summary with its runtime migration rather than copying it into new code.

## Table of Contents

- [Base Models](#base-models)
- [Permission System](#permission-system)
- [Review Workflow](#review-workflow)
- [Views and ViewSets](#views-and-viewsets)
- [Testing](#testing)

## Django Admin Adapter Checkpoint

Part 8 of the draft authorization stack adds `PolicyAdminMixin` and
`PolicyOwnedInlineMixin` in `admin.py`; governed registrations must use them.
They delegate visibility, authority, reference checks and root revisions to
the shared policy/services rather than treating staff or child model grants
as application bypasses. Runtime configuration's administrator-only
specialization remains additive to parent authority and lifecycle checks.

The standard delete action now uses confirmation, cascade-safe previews,
fresh per-record authorization and accurate results. Review history is
read-only, including for superusers; approval goes through the application's
revision-bound review workspace, not an admin bulk approval action.

See the [implementation map](../../docs/02_developer_guide/user_created_objects.md#django-admin-migration-part-8-draft)
and [user workflow](../../docs/01_user_guide/admin_workflows.md). This checkpoint
does not complete domain writers, generated-data activation or release
hardening. The explicitly labelled legacy guidance below is not a competing
authorization contract.

## Base Models

### UserCreatedObject

The base model for all objects created by users. Provides:

- **Owner tracking**: Every object has an `owner` (ForeignKey to User)
- **Publication status**: Objects can be `private`, `review`, `published`, `declined`, or `archived`
- **Timestamps**: Automatic tracking of creation and modification times
- **Approval workflow**: Fields for tracking approval/rejection by moderators

### NamedUserCreatedObject

Extends `UserCreatedObject` with a `name` field and automatic slug generation.

### GlobalObject

Base model for globally accessible objects that don't require ownership tracking.

## Permission System

### Overview

BRIT uses a centralized permission system for `UserCreatedObject` models with automatic permission creation and management.

### Permission Rows and Role Provisioning

**How it works:**

1. **Signal-based creation**: A `post_migrate` signal handler in `utils/object_management/signals.py` creates `can_moderate_<model>` permission rows for every reviewable model in the explicit policy registry (`utils/object_management/registry.py`).

2. **Runs everywhere**: The signal runs in all environments (development, production, and **tests**) to ensure consistent behavior.

3. **Idempotent**: Uses `get_or_create()` to safely handle multiple executions without errors.

4. **No group assignment**: The signal never creates groups or assigns permissions. Managed roles (`registered`, `editors`, `librarians`, the moderators group named by `settings.REVIEW_MODERATORS_GROUP_NAME`, and `administrators`) are reconciled from the manifest in `users/roles.py` by `python manage.py sync_roles` (dry-run report), `sync_roles --apply` (add missing grants) or `sync_roles --check` (fail on drift).

**Example:**

For a model `Collection(UserCreatedObject)`:
- Permission codename: `can_moderate_collection`
- Permission name: `"Can moderate collections"`
- Content type: Links to the `Collection` model
- Granted to: The moderators group after `sync_roles --apply`

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

**Setup:** migrations create the permission rows; run `python manage.py sync_roles --apply` after migrating to grant them to the managed roles.

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

> Canonical policy source: [security_permission_validation.md](../../docs/02_developer_guide/security_permission_validation.md)

### States

Objects can be in one of five publication states:

1. **private**: Draft state before review
2. **review**: Submitted for moderation review
3. **published**: Publicly visible
4. **declined**: Rejected by moderators with feedback
5. **archived**: No longer active but preserved

### Legacy action checks (pre-migration)

The staff entries in this table describe legacy checks only. They are not permissions promised by the target contract: `is_staff` means Django-admin eligibility, while application administration/moderation uses explicit capabilities. This table must be replaced when the action adapters migrate.

| Action | Who can perform | State transition |
|--------|----------------|------------------|
| Submit for review | Owner or staff | private/declined → review |
| Withdraw | Owner or staff | review/declined → private |
| Approve | Moderator/staff (not owner) | review → published |
| Reject | Moderator/staff (not owner) | review → declined |
| Archive | Owner/Moderator/Staff | published → archived |

### Four-Eyes Principle

Moderators cannot approve or reject their own submissions. This ensures independent review.

### Review Notifications

Creating a `ReviewAction` queues e-mails to the object's owner and to
everyone who previously commented on the object, via a `post_save` signal
(`enqueue_review_notifications` in `signals.py`). The signal captures the
owner at review time and passes their user id to the Celery task
`send_review_action_notifications` (`tasks.py`), so an ownership transfer
before delivery does not redirect the owner notification (if that owner was
deleted meanwhile, only past commenters are notified). Past commenters are
users with a comment that precedes the action; later comments do not
qualify. The task fans out one `send_review_action_notification_to_user`
task per recipient, and only that delivery task retries transient mail
errors, so a failure for one recipient never resends to the others. Recipients who can
no longer open the review detail page (they are neither the current owner
nor a moderator) are skipped rather than sent an unusable link.
Sending is deferred to `transaction.on_commit`; if the broker is
unavailable the signal falls back to sending synchronously. Transient mail
delivery failures are retried with backoff (up to 3 retries).

Users are only notified about actions performed by other users (e.g.
moderator approval, decline, or comments); their own actions send nothing.
Recipients without an e-mail address are skipped. The e-mail contains a
link to the object's review detail page. Links use the configured `Site`;
if no `Site` row exists for `SITE_ID` (e.g. on a fresh production
deployment), the domain falls back to `CANONICAL_HOST` or the first
`ALLOWED_HOSTS` entry. The link scheme is `https` when
`SECURE_SSL_REDIRECT` is enabled.

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
4. Iterates registered reviewable models
   ↓
5. Creates can_moderate_<model> permissions
```

Group grants are applied separately by `python manage.py sync_roles --apply`.

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
