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

## Decision core

All authorization flows through the request-independent core in
`utils/object_management/policy.py`:

| Helper | Returns |
|---|---|
| `decide(user, action, model_or_obj, parent=None)` | `Decision(allowed, reason)` |
| `capabilities(user, obj)` | `{action: Decision}` for all object actions |
| `visible_queryset(user, qs)` | Read-visible rows |
| `scope_queryset(user, qs, scope)` | `published`/`private`/`owned`/`shared`/`review`/`declined`/`archived` refinement of read visibility |
| `editable_queryset(user, qs)` | Rows the user may edit (own `change` capability required for every actor) |
| `reviewable_queryset(user, qs)` | Rows in `review` the user may moderate |
| `object_access_routes(user, obj)` | The actor's own access routes for display |

`is_admin` means an active superuser or an explicit
`object_management.administer_objects` grant; `is_staff` is informational
only. Actor helpers (`is_owner`, `is_editor`, `is_moderator`, `is_admin`)
are public API — adapters must not reimplement the rules.

The model classification registry (`utils/object_management/registry.py`)
declares every `UserCreatedObject` model as `reviewable`, `owned`
(`parent_path` to its reviewable root), or `public_catalogue`. Independent
evidence models (`MaterialPropertyValue`, `ComponentMeasurement`,
`CollectionPropertyValue`, `AggregatedCollectionPropertyValue`,
`RegionAttributeValue`, `RegionAttributeTextValue`) are reviewable roots
with a declared attachment `parent_path`; `published_attachment` scopes
whether a published or archived parent accepts new rows from any reader
(`read`) or only from parent collaborators (`collaborator`, used by
`MaterialPropertyValue`). Unregistered models fail closed, and the Django
system checks in `utils/object_management/checks.py` report missing
classifications.

Individual records can also carry a generated-projection profile:
`GENERATED_PROJECTIONS` in the registry declares
`waste_collection.collectionpropertyvalue` rows marked `is_derived` as
`generated`, governed by their `derived_from` source rather than the stored
owner/state. `record_policy(obj)` resolves that per-record classification;
the class-level policy stays `reviewable` for raw evidence. Generated rows
delegate read/export/review participation to the linked source, fail closed
on missing or invalid provenance for every actor, and are excluded from
editable and reviewable querysets.

## Runtime adapters

| Concern | Component | File |
|---|---|---|
| DRF action & object permissions | `UserCreatedObjectPermission` | `utils/object_management/permissions.py` |
| Model-permission views with extra narrowing | `HasModelPermission` (subclasses `UserCreatedObjectPermission`) | `utils/permissions.py` |
| Generic viewset scoping | `AutoPermModelViewSet` / `UserCreatedObjectViewSet` | `utils/viewsets.py`, `utils/object_management/viewsets.py` |
| Template/UI capability dictionary | `get_object_policy(...)`, `{% object_policy %}`, `{% model_creation_policy %}` | `utils/object_management/permissions.py`, `utils/object_management/templatetags/moderation_tags.py` |
| List/autocomplete/export seed visibility | `filter_queryset_for_user(...)` | `utils/object_management/permissions.py` |
| Scope filtering (`published`/`private`/`owned`/`shared`/`review`/...) | `apply_scope_filter(...)` | `utils/object_management/permissions.py` |
| HTML permission bridging | `PolicyPermissionRequiredMixin` (`policy_model`, `policy_action`, `get_policy_parent`) | `utils/object_management/views.py` |
| HTML read/write object access | `UserCreatedObjectReadAccessMixin` / `UserCreatedObjectWriteAccessMixin` | `utils/object_management/views.py` |
| Bound create persistence | `perform_policy_create` (DRF), `PolicyPermissionRequiredMixin._enforce_policy_create` (HTML) | `utils/object_management/viewsets.py`, `utils/object_management/views.py` |
| Review transitions (API + HTML) | `UserCreatedObjectViewSet` named actions; `BaseReviewActionView` subclasses | `utils/object_management/viewsets.py`, `utils/object_management/views.py` |
| Workspace filter set | `UserCreatedObjectScopedFilterSet` | `utils/filters.py` |
| Per-actor GeoJSON caching | `CachedGeoJSONMixin._audience_cache_key` | `maps/mixins.py` |

Adapters may narrow a decision but never broaden it. `PUT`/`PATCH` payloads
containing `owner` or `publication_status` are rejected; the server assigns
`owner` and the `private` initial state on create. Owned-child and evidence
creates must resolve the declared `parent_path` (via `get_policy_parent`,
the validated instance, or `resolve_create_parent`) and pass a final
`decide(create, model, parent=...)` check before persistence.

## Roles and provisioning

- Role manifest: `users/roles.py` (literal, built from registry sets).
- Provisioning: `manage.py sync_roles` (dry-run by default; `--apply` adds
  missing grants, `--check` fails on drift). The `post_migrate` signal in
  `utils/object_management/signals.py` creates `can_moderate_<model>`
  permission rows for registered reviewable models only; it never assigns
  groups or users.
- `object_management.administer_objects` is the explicit administrator
  permission (`ReviewAction.Meta.permissions`).

## Request-path overview

```text
UI/API request
    |
    +--> Early visibility filter
    |      - visible_queryset / scope_queryset (queryset adapters)
    |
    +--> Authoritative backend check
           - UserCreatedObjectPermission / HasModelPermission (API)
           - PolicyPermissionRequiredMixin + _enforce_policy_create (HTML)
           - decide() object action checks
    |
    +--> UI rendering
           - get_object_policy(...) / object_policy / model_creation_policy
```

## Sharing, workspace, and review activity

- `manage_access` actions (add/remove editor, group grants, transfer
  ownership) require the object's own `manage_editors`/`transfer_ownership`
  decision — owner or administrator only.
- `YourAccessModalView` (`object_management:your_access_modal`) shows the
  requesting user's own access routes and edit-decision reason only.
- Review detail/comment paths use `view_review_activity` /
  `comment_on_review` capabilities; review history is retained on
  decline/withdraw.

## Known pending boundaries

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
public historical archive. Governed approval archives them through
``perform_transition(..., "archive")``, producing an actor- and
revision-bound audit event in the same transaction; raw ORM
``approve()`` with no actor archives only published predecessors without
fabricating audit entries.

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

- Revision-safe review is implemented in the shared boundary
  (`utils/object_management/services.py`): `content_mutation` locks the
  reviewable root, re-checks policy against freshly persisted state, and
  audits a single `content_revision` bump; `perform_transition` binds
  approvals to the inspected revision and enforces contributor exclusion.
  The standard HTML update/create, review-action, modal, admin, and DRF
  adapter paths route through it, as do the Process/Sample workspace and
  bibliography helpers. Importer write paths, sample-series helpers, and
  custom domain mutations outside those adapters remain pending
  verification or migration and must not be treated as covered; the
  refactor is not yet verified green across the whole suite.
- Specialized collection create actions declare their model targets in
  `action_create_models` and authorize those targets through the shared
  core; the programmatic `property-value/create` and
  `aggregated-property-value/create` endpoints persist through
  `sources/waste_collection/services.py`, which locks the actor and parent
  rows, preflights source/flyer/property/unit references, and routes
  relation edits through `content_mutation`. Workbook-importer persistence
  and the HTML/formset write paths remain separately tracked pending
  boundaries.
- Generated collection property values are read-only projections of their
  linked raw source (`is_derived`/`derived_from` record profile
  `generated`); schema, source-governed authorization, generator provenance
  writes, and source-specific output identity are implemented. Manual
  measurements take precedence only within the same authorized read purpose;
  their records are never overwritten by generated outputs. Importer
  persistence, existing-record reuse, and the legacy provenance audit/backfill
  remain pending boundaries. Do not guess source links or fabricate history.
- Dataset-version fingerprints and inventory/map read guards delegate to
  the shared core; staff status is not an application access route.

## Maintenance rule

When permission behavior changes, update all together:

1. Policy core/registry and adapters
2. Independently asserted regression tests
3. Canonical doc: `security_permission_validation.md`

List, detail, map, autocomplete, options, reference validation, counts, and
export must agree on read authorization. Purpose-specific filters may narrow
results. Archived records remain publicly readable and exportable as
retained, previously published content — see
`security_permission_validation.md` for the normative contract. Active-only
listings exclude archives, while explicit `archived` scopes and
historical-year maps include them.
