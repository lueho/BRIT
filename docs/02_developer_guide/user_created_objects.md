# UserCreatedObject Permission System

This document outlines the permission system for UserCreatedObject models across both class-based views and viewsets.

## Single source of truth

All permission checks and button visibility are centralized in `utils/object_management/permissions.py`:

- `UserCreatedObjectPermission` — backend permission class used by DRF and enforced in CBVs via mixins and explicit checks.
- `get_object_policy(user, obj, request=None, review_mode=False)` — computes a unified policy dict consumed by templates and views for button visibility and UI behavior.

Templates should consume the policy via templatetags in `utils/object_management/templatetags/moderation_tags.py`:

- `{% object_policy object as policy %}` returns the policy dict.
- `{{ user|can_moderate:object }}` checks per‑model moderator rights.

Avoid ad‑hoc permission logic elsewhere; do not reimplement checks in views or templates.

## Roles and states

- Anonymous — not authenticated.
- Authenticated — logged in but neither owner, moderator, nor staff.
- Owner — `obj.owner == request.user`.
- Moderator — per‑model permission `can_moderate_<model>` or staff.
- Staff — `is_staff=True`.

Publication states (`obj.publication_status` and convenience flags):

- `private`, `review`, `published`, `declined`, `archived`.

## Read access (views vs API)

### HTML Class‑Based Views (CBVs)

Source: `UserCreatedObjectReadAccessMixin.test_func()` in `utils/object_management/views.py`.

| Object state | Anonymous | Authenticated (not owner/staff) | Owner | Staff |
|--------------|-----------|---------------------------------|-------|-------|
| published    | ✅        | ✅                              | ✅    | ✅    |
| review       | ❌        | ❌                              | ✅    | ✅    |
| private      | ❌        | ❌                              | ✅    | ✅    |
| declined     | ❌        | ❌                              | ✅    | ✅    |
| archived     | ❌        | ❌                              | ✅    | ✅    |

Note: Non‑staff moderators (users with `can_moderate_<model>`) can access the dedicated review UI, see “Review UI access” below, but not the regular detail view of private/declined items via this mixin.

### Django REST Framework (API, safe methods)

Source: `UserCreatedObjectPermission._check_safe_permissions()` in `utils/object_management/permissions.py`.

| Object state | Anonymous | Authenticated (not owner/moderator/staff) | Owner | Moderator/Staff |
|--------------|-----------|-------------------------------------------|-------|------------------|
| published    | ✅        | ✅                                        | ✅    | ✅               |
| review       | ❌        | ❌                                        | ✅    | ✅               |
| private      | ❌        | ❌                                        | ✅    | ✅               |
| archived     | ❌        | ❌                                        | ✅    | ✅               |

Notes:

- “declined” is not explicitly handled in the API safe‑method checker and currently defaults to deny; use the Review UI for owner feedback visibility. If API read‑access to declined objects is required, extend `_check_safe_permissions()` accordingly (treat declined like private).

## Actions and conditions

Source: `get_object_policy()` and `UserCreatedObjectPermission` helpers. Conditions below describe who can see/use actions in the UI and who will pass backend checks.

| Action | Who | Conditions |
|-------|-----|------------|
| Create | Staff | Always |
| Create | Authenticated user | Must have `add_<model>` permission on the model |
| Edit | Owner | Not archived AND not published |
| Edit | Staff | Not archived |
| Edit | Moderator | Only allowed to change `publication_status` via PUT/PATCH; cannot modify other fields; cannot edit private objects when not owner |
| Delete | Owner | Object is not archived AND not published OR is declined/review/private, and a delete URL is provided |
| Delete | Staff | Any state (published and archived included), if a delete URL is provided |
| Archive | Owner, Moderator, or Staff | Object is published and not archived |
| Duplicate | Authenticated user | Must have `add_<model>` permission |
| New version | Owner or Staff | Requires Duplicate permission AND object is published AND not archived |
| Manage samples | Owner or Staff | Not published AND not archived |
| Add property | Owner or Staff | Not published AND not archived |
| Export | Anyone | Public objects always exportable; private export requires authenticated owner or staff |
| Submit for review | Owner or Staff | State is `private` or `declined`; not archived |
| Withdraw from review | Owner or Staff | State is `review` or `declined`; not archived |
| Approve | Moderator (not owner) | Four‑eyes principle; state is `review` |
| Reject | Moderator (not owner) | Four‑eyes principle; state is `review` |
| View review feedback | Owner | `declined` state and not in review_mode (handled by `can_view_review_feedback`) |

Notes:

- Moderator = per‑model `can_moderate_<model>` permission or staff, see `_is_moderator()`.
- Four‑eyes principle: Approvers must not be the object owner.
- Archive nuances: The UI policy (`get_object_policy`) and the CBV modal (`UserCreatedObjectModalArchiveView`) allow owners to archive published objects. The DRF `archive` action enforces `UserCreatedObjectPermission`, which currently denies owners modifying published objects; moderators/staff should use the API for archival.

## Publication dependency checks

Source: `utils/object_management/publication.py`.

- **Registry** — Declare dependencies for `UserCreatedObject` subclasses via `REGISTRY`. For example, `Sample` lists `material`, `series`, `timestep`, and `sources` as published requirements; `Composition` cascades the status of its `shares`.
- **`prepublish_check(obj, target_status=None)`** — Returns a report containing blocking dependencies (items that must be published) and `needs_sync` children (objects that will be adjusted to the new status). `UserCreatedObject.submit_for_review()` and `.approve()` invoke this and raise `ValidationError` when the report has blocking items.
- **`cascade_publication_status(obj, target_status, acting_user=None)`** — Applies a new status to related objects listed in the registry's `follows_parent` rules whenever workflow transitions occur (submit, approve, reject, withdraw, archive).

### Adding dependencies for a model

Register a new model in `REGISTRY` with `DependencyConfig`:

```python
REGISTRY[("materials", "sample")] = DependencyConfig(
    requires_published=(
        RelationRule("material"),
        RelationRule("sources"),
    ),
    follows_parent=(RelationRule("properties"),),
)
```

- Use `optional=True` for nullable relations (`series`, `timestep`).
- `requires_published` items must expose `publication_status` or be inherently safe.
- `follows_parent` items will be cascaded to the parent's new status.

## Publication checklist UI

Source: `utils/object_management/views.py:PublicationChecklistView` and template `utils/object_management/templates/object_management/publication_checklist.html`.

- Triggered automatically when `submit_for_review()` or `approve()` raises a `ValidationError` due to unresolved dependencies.
- Accessible at `object_management:publication_checklist` with the target object; permissions mirror `get_object_policy` (owner, staff, moderators).
- Shows:
  - **Blocking dependencies** — items the user must publish/replace before continuing.
  - **Sync issues** — children that will be auto-aligned via `cascade_publication_status()`.
- Provides action buttons posting directly to the review workflow endpoints with a `next` parameter back to the source page.

### Rendering safe related data

- Use the helpers on model instances when serializing or rendering public pages:
  - `Sample.visible_sources`, `Sample.visible_properties`, `Sample.visible_compositions`
  - `Composition.visible_shares`
- The logic returns all related objects while the parent is unpublished, and filters to published ones once the parent is public, preventing data leakage.

### Testing

- Run the publication checklist by attempting to submit or approve objects with missing dependencies to ensure blocking messages appear.
- Ensure public detail views (e.g., `materials/templates/materials/sample_detail.html`) render only visible related data.

## Review UI access

Source: `utils/object_management/views.py:ReviewItemDetailView`.

- Staff and per‑model moderators (`can_moderate_<model>`) can access any item’s review detail page.
- Owners can access the review detail page only while the item is in `review` (to comment) or `declined` (to read feedback).
- Others are not allowed.

## DRF viewsets and actions

Source: `utils/object_management/viewsets.py`.

- `UserCreatedObjectViewSet` uses `UserCreatedObjectPermission` as its base `permission_classes`.
- Actions provided: `register_for_review` (same policy as submit), `withdraw_from_review`, `approve`, `reject`, `archive`.
- Object creation assigns `owner=self.request.user` and requires `add_<model>` permission per `UserCreatedObjectPermission.has_permission`.

All API endpoints are expected to mirror the rules above; if you add new endpoints, delegate checks to `UserCreatedObjectPermission` or the specific helper methods.

## Per‑model moderator permission

Moderation rights are granted via `can_moderate_<model>` permissions created and distributed automatically (post‑migrate) to the configured moderators group. See `utils/object_management/signals.py` and `settings.REVIEW_MODERATORS_GROUP_NAME` (defaults to `moderators`). Staff users always qualify as moderators.

## Using the policy in templates

Example:

```django
{% object_policy object as policy %}

{% if policy.can_submit_review %}
  <a href="{{ object.submit_for_review_url }}" class="btn btn-primary">Submit for review</a>
{% endif %}

{% if user|can_moderate:object and policy.can_approve %}
  <a href="{{ object.approve_url }}" class="btn btn-success">Approve</a>
{% endif %}
```

## Best practices

- Always consult `get_object_policy()` for UI decisions and button visibility.
- In views, rely on `UserCreatedObjectPermission` and dedicated helpers (`has_submit_permission`, `has_withdraw_permission`, `has_approve_permission`, `has_reject_permission`).
- Do not duplicate permission logic in templates or views.
