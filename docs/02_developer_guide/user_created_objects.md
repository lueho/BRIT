# UserCreatedObject Permission System

This page is an implementation map for developers working on
`UserCreatedObject` flows.

The **authoritative policy tables and state diagrams** live in:

- [`security_permission_validation.md`](security_permission_validation.md)

To avoid drift, keep policy details in that one canonical page.

## Permission architecture at a glance

| Concern | Primary helper/component | File |
|---|---|---|
| API action & object permissions | `UserCreatedObjectPermission` | `utils/object_management/permissions.py` |
| Template/UI action visibility | `get_object_policy(...)` | `utils/object_management/permissions.py` |
| Base read visibility (list/autocomplete/export seed) | `filter_queryset_for_user(...)` | `utils/object_management/permissions.py` |
| Scope-based filtering (`published/private/review/...`) | `apply_scope_filter(...)` | `utils/object_management/permissions.py` |
| Export filter payload normalization | `build_scope_filter_params(...)` | `utils/object_management/permissions.py` |
| Review transition API actions | `register_for_review`, `withdraw_from_review`, `approve`, `reject`, `archive` | `utils/object_management/viewsets.py` |
| Review transition HTML actions | `BaseReviewActionView` and subclasses | `utils/object_management/views.py` |
| Autocomplete hardening (fail-closed invalid filters) | `UserCreatedObjectAutocompleteView.apply_filters(...)` | `utils/object_management/views.py` |
| Form-level reference validation | `UserCreatedObjectFormMixin.clean()` | `utils/forms.py` |

## Request-path overview

```text
UI/API request
    |
    +--> Early visibility filter
    |      - filter_queryset_for_user(...)
    |      - apply_scope_filter(...)
    |
    +--> Authoritative backend check
           - UserCreatedObjectPermission (API)
           - UserCreatedObjectFormMixin.clean() (forms)
           - action-specific permission helpers
    |
    +--> UI rendering
           - get_object_policy(...) for button visibility
```

## Review workflow integration points

```text
private|declined -- submit --> review -- approve --> published -- archive --> archived
                                  |\
                                  | reject
                                  v
                               declined
```

- Four-eyes rule is enforced in permission helpers for approve/reject.
- API and HTML review actions must delegate to the same helper methods.

## Moderator permissions

- Per-model moderation rights use `can_moderate_<model>`.
- Permissions are created/maintained via `post_migrate` signal logic in
  `utils/object_management/signals.py`.
- Staff users are always treated as moderators for moderation checks.

Testing tip:

```python
# Fetch auto-created permission (do not create duplicates)
permission = Permission.objects.get(
    codename="can_moderate_mymodel",
    content_type=content_type,
)
```

## Template usage

```django
{% load moderation_tags %}
{% object_policy object as policy %}

{% if policy.can_submit_review %}
  <a href="{{ object.submit_for_review_url }}">Submit for review</a>
{% endif %}
```

## Maintenance rule

When permission behavior changes, update all three together:

1. Implementation (`permissions.py` and call sites)
2. Regression tests
3. Canonical doc: `security_permission_validation.md`
