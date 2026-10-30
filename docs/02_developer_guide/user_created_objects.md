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

The shared flyer helper also serves collection create/version reference attachment; their root persistence and frequency creation remain un-migrated. HTML/formset/importer writers, generated profiles/evidence extraction, browser/runtime and rollout gates remain open.

## Deliberate operator and worker paths

The following writes stay outside the per-object decision core **by design**. Each is gated by a model-level capability or role at its entry point, then executes as a system actor; none widens ordinary user rights.

- **Operator ingestion APIs** — `NutsImportView` (`maps/nuts_import`) and `PopulationImportView` (`maps/population`) bulk-import whole vintages/datasets through the versioned public contracts. They gate on the model-level `add` + `change` capability (`CanImportNutsRegions`, `CanImportPopulation`) — a generic permission check, not a named-group lookup, so the manifest already provisions who may call them. Routing each imported row through `decide`/`content_mutation` would attach owner, lifecycle and revision semantics that bulk vintage data deliberately does not carry.
- **Celery worker writes** — `check_source_url`/`check_source_urls` (bibliography) and `check_wasteflyer_url`/`check_wasteflyer_urls` (waste_collection) update only `url_valid`/`url_checked`, which are audit-exempt operational metadata that never bump a content revision. `check_stale_source_urls` is beat-scheduled (operator-driven). `cleanup_orphaned_waste_flyers`, inventory `finalize_inventory`/`layer.publish()`, and the GeoJSON cache warmers act on generated artifacts or system-owned rows. The authorization boundary sits at **scheduling**: HTTP endpoints decide first (`decide(..., "check_url", obj)` or a model `change` permission), and bulk schedulers pass the requester id so the task scopes its queryset through `filter_queryset_for_user` — forged filter parameters can never schedule writes on records the requester cannot read.
- **`UserAutocompleteView`** — enumerates active usernames for the review dashboard "Submitted by" filter. Upstream `AutocompleteModelView` defaults `allow_anonymous = False`, keeping the endpoint authenticated-only; the enumeration is deliberate for moderation workflows, not a public user directory.
- **Waste Atlas configuration** — `WasteAtlasMapConfiguration` and `WasteAtlasRenderingSettings` are plain configuration models outside the governed registry (no owner, lifecycle or content revision exist to enforce). Their HTML edit views are gated by `WasteAtlasAdminMixin` → `is_admin`, and `WasteAtlasMapConfigurationUpdateView` persists exactly once: `form.save()` is the sole write because `FormView`'s `form_valid` only redirects.

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
