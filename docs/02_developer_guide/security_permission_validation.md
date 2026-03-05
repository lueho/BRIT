# Permission and Visibility Policy

This page is the canonical, implementation-aligned overview of permission logic
for `UserCreatedObject` data in BRIT.

## Source of truth in code

- `utils/object_management/permissions.py`
  - `UserCreatedObjectPermission`
  - `get_object_policy(...)`
  - `filter_queryset_for_user(...)`
  - `apply_scope_filter(...)`
  - `build_scope_filter_params(...)`
- `utils/object_management/viewsets.py`
  - review transition API actions delegate to permission helpers
- `utils/object_management/views.py`
  - `UserCreatedObjectAutocompleteView` uses visibility filtering + fail-closed filter handling
- `utils/forms.py`
  - `UserCreatedObjectFormMixin.clean()` enforces backend validation of referenced objects

If this page conflicts with implementation, update this page together with code.

## Roles and states

### Roles

- **Anonymous**: not authenticated
- **Authenticated user**: authenticated, but not owner/moderator/staff
- **Owner**: `obj.owner == user`
- **Moderator**: has per-model permission `can_moderate_<model>`
- **Staff**: `is_staff=True` (treated as moderator for moderation checks)

### Publication states

- `private`
- `review`
- `published`
- `declined`
- `archived`

## Defense-in-depth flow

```text
User input (UI or API)
    |
    +--> Autocomplete / list filtering (UX + early restriction)
    |      - filter_queryset_for_user(...)
    |      - apply_scope_filter(...)
    |      - invalid autocomplete filters fail closed (queryset.none())
    |
    +--> Form/API backend validation (authoritative)
           - UserCreatedObjectFormMixin.clean()
           - UserCreatedObjectPermission.has_permission()/has_object_permission()
           - action-specific helpers (submit/withdraw/approve/reject/archive)
                    |
                    +--> DB mutation / response
```

## Read visibility policy

### General read filter (`filter_queryset_for_user`)

| User type | Visible records |
|---|---|
| Staff | All |
| Anonymous | `published` only |
| Authenticated regular | Own + `published` |
| Authenticated moderator | Own + `published` + `review` |

### Scope filter (`apply_scope_filter`)

| Scope | Anonymous | Authenticated regular | Moderator | Staff |
|---|---|---|---|---|
| `published` | published | published | published | published |
| `private` | none | own (all statuses) | own (all statuses) | all |
| `review` | none | own `review` | all `review` | all `review` |
| `declined` | none | own `declined` | own `declined` | all `declined` |
| `archived` | none | own `archived` | own `archived` | all `archived` |

Notes:

- Unknown scopes currently return the queryset unchanged.
- Scope filtering requires a model with `publication_status`; owner-restricted scopes also require an `owner` field.

### Object-level safe-method reads (`_check_safe_permissions`)

| State | Anonymous | Authenticated regular | Owner | Moderator/Staff |
|---|---|---|---|---|
| `published` | ✅ | ✅ | ✅ | ✅ |
| `review` | ❌ | ❌ | ✅ | ✅ |
| `private` | ❌ | ❌ | ✅ | ✅ |
| `archived` | ❌ | ❌ | ✅ | ✅ |
| `declined` | ❌ | ❌ | ✅ | ✅ |

## Action policy (UI + backend)

This table summarizes effective policy from `get_object_policy(...)` and
`UserCreatedObjectPermission` helper methods.

| Action | Allowed actors | Required state/condition |
|---|---|---|
| Create (`create` and configured create-like actions) | Authenticated users with `add_<model>`; staff | Model add permission required |
| Edit (owner path) | Owner | Not `published`, not `archived` |
| Edit (moderator path, non-owner) | Moderator/Staff | Not private of another owner; for PATCH/PUT only `publication_status` may change |
| Delete | Owner/Staff | Owner: non-published non-archived states with delete URL. Staff: can delete across states (incl. archived) with delete URL |
| Archive | Owner/Moderator/Staff | `published` and not `archived` |
| Submit for review | Owner/Staff | `private` or `declined`, and not `archived` |
| Withdraw from review | Owner/Staff | `review` or `declined`, and not `archived` |
| Approve | Moderator/Staff, not owner | State is `review` (four-eyes) |
| Reject | Moderator/Staff, not owner | State is `review` (four-eyes) |
| Add review comment | Owner/Moderator/Staff | Authenticated |
| Duplicate | Authenticated user with `add_<model>` | Model add permission required |
| New version | Authenticated user with `add_<model>` | Not `archived` and (`published` or owner) |
| Manage samples | Owner/Staff | Not `published`, not `archived` |
| Add property | Owner/Staff | Not `archived` |
| Export | Public + owner/staff private export | `published`/`archived` are public-exportable; otherwise authenticated owner/staff |
| View review feedback | Owner | `declined` and not in `review_mode` |

## Review workflow transitions

```text
private --(owner/staff submit)--> review
declined --(owner/staff submit)--> review

review --(owner/staff withdraw)--> private
review --(moderator/staff, not owner approve)--> published
review --(moderator/staff, not owner reject)--> declined

published --(owner/moderator/staff archive)--> archived
```

## Autocomplete and export hardening

- Autocomplete visibility starts with `filter_queryset_for_user(...)` and excludes archived objects where supported.
- `scope__name` in autocomplete is handled via `apply_scope_filter(...)`.
- Invalid autocomplete filters (e.g., malformed numeric IDs, incompatible values) fail closed with `queryset.none()`.
- Async export for user-created objects applies the same centralized visibility/scope helpers to prevent scope leakage.

## Maintenance rules

- Do not duplicate permission logic in templates or views.
- UI visibility should use `get_object_policy(...)`.
- Backend checks should delegate to `UserCreatedObjectPermission` and helper methods.
- When policy changes, update:
  1. code,
  2. regression tests,
  3. this page.
