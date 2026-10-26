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

## Version-chain approval and predecessor archival

*Part 9a draft runtime checkpoint — not a deployment claim.*

A governed ``approve`` on a versioned record acquires any declared
transition dependencies through the ``_lock_review_dependencies(action)``
hook — inside the governing transaction and **before** the fresh-actor and
authorization checks — so dependent rows are locked while authority is
still established, never read from a stale decision afterwards.
``Collection`` locks its predecessors through that hook for approval.

Archival on approval is restricted to predecessors whose freshly locked
status is ``published``: unpublished predecessors are never forced into the
public historical archive. Predecessors are archived through
``perform_transition(..., "archive")`` with the approving user, producing an
actor- and revision-bound audit event in the same transaction; ``approve()``
without a user is rejected.

Because unpublished predecessors stay unpublished, approval also rejects a
record when any later version in its chain is already published, so an
older version can never be published alongside its successor.

A pre-existing ``archived`` status alone does NOT prove prior publication —
legacy rows may carry that state without a matching ``archived`` audit event.
Ambiguous legacy archives require an approved audit before any public-archive
rollout can rely on them.

Remaining gaps: Atlas read scopes, domain-specific writer surfaces,
generated-value activation, and broader version-graph lock ordering are
outside this slice; the legacy cascade helpers are retained for a future
migration.

## Atlas scope and cache adapters

*Part 9b draft runtime checkpoint - not a deployment claim.*

Atlas collection, supporting-evidence and boundary-revision membership delegates to the shared authorization core. The Django staff flag alone grants neither private-data visibility nor maintainer access.

The Atlas-specific `historical` purpose filter is the authorized union of published and archived collections. Every actor defaults to that public historical view, including administrators. Explicit `published` remains active-only; explicit `archived` selects historical archives. Workspace and lifecycle scopes refine authorized membership, `mine` remains a compatibility alias for the owned/shared `private` workspace, and `all` requires explicit administration. Unknown and blank scopes return no records instead of falling back to public data. Scope-free map permalinks retain the public historical default.

CPVs, ACPVs and CatchmentRevisions retain their own ownership, grants, moderation and lifecycle rules. Collection rights alone do not expose another model's non-public evidence. Public historical evidence remains usable for selected collections and their readable version siblings; a public value attached to an unreadable collection does not enter CPV chain metrics. Generated-projection activation remains Part 10.

Authenticated change-overlay requests bypass cache reads and writes so grant and membership changes take effect on the next request. Anonymous overlays use a separate authorization-prefixed cache namespace. The client preserves explicit scopes, including invalid or blank input, through requests and selector/change-map navigation.

Map-configuration pages require explicit application administration; conflict aids and their overview require administration or collection moderation. These are coarse request/UI gates for ordinary configuration models, not completion of their specialized locked persistence and fresh-write authorization.

Live-browser verification with representative snapshot data, legacy archive provenance, geography fallbacks and cross-reference visibility, wider version-graph locking, remaining domain/HTML/formset/importer writers, generated values and rollout hardening remain open. This checkpoint does not close those objectives or establish deployment readiness.

## Governed programmatic collection updates

*Part 9c draft runtime checkpoint - not a deployment claim.*

The programmatic collection update route and its legacy alias use `content_mutation` on the freshly locked collection. Expected identity values are conflict guards, never authorization inputs; mismatches return 409 without a write. Authorized owner, direct/group editor and administrator edits use the same capability/lifecycle policy, retain review state/history, and record one meaningful root revision/audit across scalar and M2M changes.

Shared reference validation governs submitted related records. Existing flyer reuse requires its own read access but not add capability; new flyers require their own create capability before persistence, are private and owned by the acting user, and have a creation audit. Compound failures roll back root, relations, new flyers and new events.

The shared flyer helper also serves collection create/version reference attachment. The 9c note that root persistence and frequency creation remained un-migrated is historical; the Part 9d checkpoint below now covers those write boundaries. HTML/formset/importer writers, generated profiles/evidence extraction, browser/runtime and rollout gates remain open.

## Governed programmatic collection creation

*Part 9d draft runtime checkpoint - not a deployment claim.*

The collection create and new-version routes authorize inside their write boundary: creation requires the fresh `add_collection` capability, and shared reference validation runs against references resolved on the locked predecessor, not prefetched or pre-transaction state. New versions decide `read` and `new_version` on the locked predecessor: an unreadable predecessor answers 404, an archived predecessor or missing capability answers 403, and every inherited scalar and material default comes from the locked record. Unreadable inherited sources and flyers are dropped; explicit unreadable references are denied.

Submission helpers refresh the record after the transition, so responses report the persisted publication status. Creation plus submission records exactly one created and one submitted event, both bound to the content revision.

Frequency creation authorizes each independent model inside the transaction: a new frequency, each count-options row and each new season require their own add capability, are private, are owned by the acting user and receive one creation audit each. The frequency-create endpoint itself always requires a fresh `add_collectionfrequency` capability, including on reuse; the reused frequency needs read access to be locked and inspected, while reusing an existing season needs read access only and adds no row or season capability requirements. Seeded calendar distributions and timesteps currently default to private - a rollout/data gap, not an authorization bypass. `access_control_bp` and `access_control_pap` now persist, inherit and can be overridden on create and new-version payloads.

HTML/formset/importer writers, generated profiles/evidence extraction, the trusted `CollectionImporter`, CPV/ACPV endpoints, browser/runtime and rollout gates remain open. In particular `bulk_import` still exposes trusted writes - including frozen predecessor modification, evidence reownership and history deletion - behind merely `add_collection`; that remains a known high-priority hardening blocker, not a completed path.

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
