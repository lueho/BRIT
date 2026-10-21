# UserCreatedObject Permission System

This page is an implementation map for developers working on
`UserCreatedObject` flows.

> **Migration status — legacy runtime reference:** This page describes the pre-migration implementation at the start of the authorization review stack. It is not a second policy specification and may lag later migration parts. The [canonical authorization contract](security_permission_validation.md) defines the target rules; in particular, staff status alone must not grant application moderation. Update the corresponding runtime notes as their adapters migrate.

The **authoritative policy tables and state diagrams** live in:

- [`security_permission_validation.md`](security_permission_validation.md)

To avoid drift, keep policy details in that one canonical page.

## Django admin migration (Part 8 draft)

Governed registrations now use `PolicyAdminMixin` in
`utils/object_management/admin.py`. Reads delegate to `visible_queryset`;
writes use the shared decisions and atomic mutation/creation services.
The adapter refreshes actor/site eligibility after blocking locks and again
at persistence hooks. Model, M2M and owned-inline changes share the root's
revision and roll back together if authorization or audit persistence fails.

`PolicyOwnedInlineMixin` resolves the registry's declared parent path.
It does not grant independent child permissions or support independent
evidence as an owned inline. Existing child IDs must belong to the declared
parent; structural reparenting is not an ordinary form edit. Governed FK/M2M
choices and submitted references use current read authorization.

The standard `delete_selected` action identifier is retained, but invokes the
policy implementation. Confirmation previews use the service's cascade check
before related objects are formatted; confirmed deletes reauthorize each
record and report actual results. `ReviewActionAdmin` is read-only and
participant-scoped, with full history available to application administrators.
Review approvals remain in the revision-bound application workspace.

This is an adapter checkpoint, not deployment readiness. Domain-specific
validation, generated-projection activation, browser verification, the earlier
bibliography layering issue and coordinated release hardening remain open in
[#614](https://github.com/lueho/BRIT/pull/614). Legacy notes below are not an
alternative policy. User instructions: [admin workflows](../01_user_guide/admin_workflows.md).

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

## Legacy moderator checks (pre-migration)

- Per-model moderation rights use `can_moderate_<model>`.
- Permissions are created/maintained via `post_migrate` signal logic in
  `utils/object_management/signals.py`.
- At the pre-migration baseline, moderation checks treat staff users as moderators. This describes legacy runtime behavior to remove; it is not the target contract, where `is_staff` supplies Django-admin eligibility only.

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
