# BRIT authorization and collaboration policy

This is the normative authorization contract for BRIT. Application behavior, role provisioning, user help, tests, and agent workflows must agree with it. A discrepancy is a defect, not an undocumented exception. During the staged migration, incomplete adapters are tracked explicitly; old behavior is not a second specification.

## Migration status and linked guidance

This page defines the target authorization rules, not a guarantee that every runtime path has already migrated. The [implementation map](user_created_objects.md) and [package guide](../../utils/object_management/README.md) explicitly label pre-migration runtime notes. Any staff bypass described there is legacy behavior to remove, not authority granted by this contract. Use the migration acceptance tracker in [#614](https://github.com/lueho/BRIT/pull/614) to distinguish implementation progress from rollout readiness.

## Architecture

Authorization is capability AND object access AND lifecycle eligibility. Django model permissions express capabilities. Ownership and individual/group editor grants express object access. Publication states constrain actions. Neither ownership nor a model permission alone gives unrestricted write access.

One request-independent decision core supplies action decisions, UI capabilities, and visibility restrictions. HTML views, modal/quick-create endpoints, DRF, reference validation, exports, and background business actions must delegate to it. Adapters may narrow a decision but may not broaden it. Routes and templates describe available presentations; the existence of a URL is never an authorization condition. Unknown models/actions fail closed and configuration checks report missing classifications.

Decision responses expose a boolean and a stable reason code. UI explanations use those codes without disclosing inaccessible objects or unrelated group membership. Public endpoints enforce the decision at mutation time; hiding a button is not a security boundary. Raw ORM utilities are trusted internals, not public authorization APIs.

## Actors and roles

An active authenticated actor is required for all non-public access and mutations. Inactive users receive no privileged access. Published and archived domain records may be read anonymously. Archived means retained, previously published content, not a privacy or withdrawal state.

- Owner: the record's current owner.
- Object editor: an active user holding an individual grant or belonging to a group with an editor grant on this record. This is not the model-wide group named `editors`.
- Contributor: a role with explicit add/change/delete/view capabilities for the supported user-content models and the reusable records needed by their workflows.
- Curator/librarian: explicitly scoped shared-reference management capabilities.
- Moderator: `can_moderate_<model>` for specified models; moderation does not imply ordinary content editing.
- Administrator: an explicit application role, using `object_management.administer_objects`; active superusers have administrative object access. Administration does not bypass immutable states, revision checks, or four-eyes review.
- Staff: `is_staff` means Django-admin eligibility only. It supplies no application bypass or moderation capability by itself.
- Service/specialized roles: narrowly scoped capabilities. Existing importers with custom write permissions retain their explicitly documented service boundaries.

Groups are permission bundles, not conditionals embedded in views. Direct user permissions remain effective. The version-controlled role manifest declares supported bundles and model classifications; new models never receive permissions by discovery alone. Role inspection is read-only by default. Reconciliation requires an explicit apply mode, reports additions and removals, and does not silently revoke unmanaged production grants. Creation of permission rows after migration is separate from deliberate role reconciliation.

## Read policy

For independently reviewable user-created records:


## Architecture

Authorization is capability AND object access AND lifecycle eligibility. Django model permissions express capabilities. Ownership and individual/group editor grants express object access. Publication states constrain actions. Neither ownership nor a model permission alone gives unrestricted write access.

One request-independent decision core supplies action decisions, UI capabilities, and visibility restrictions. HTML views, modal/quick-create endpoints, DRF, reference validation, exports, and background business actions must delegate to it. Adapters may narrow a decision but may not broaden it. Routes and templates describe available presentations; the existence of a URL is never an authorization condition. Unknown models/actions fail closed and configuration checks report missing classifications.

Decision responses expose a boolean and a stable reason code. UI explanations use those codes without disclosing inaccessible objects or unrelated group membership. Public endpoints enforce the decision at mutation time; hiding a button is not a security boundary. Raw ORM utilities are trusted internals, not public authorization APIs.

## Actors and roles

An active authenticated actor is required for all non-public access and mutations. Inactive users receive no privileged access. Published and archived domain records may be read anonymously. Archived means retained, previously published content, not a privacy or withdrawal state.

- Owner: the record's current owner.
- Object editor: an active user holding an individual grant or belonging to a group with an editor grant on this record. This is not the model-wide group named `editors`.
- Contributor: a role with explicit add/change/delete/view capabilities for the supported user-content models and the reusable records needed by their workflows.
- Curator/librarian: explicitly scoped shared-reference management capabilities.
- Moderator: `can_moderate_<model>` for specified models; moderation does not imply ordinary content editing.
- Administrator: an explicit application role, using `object_management.administer_objects`; active superusers have administrative object access. Administration does not bypass immutable states, revision checks, or four-eyes review.
- Staff: `is_staff` means Django-admin eligibility only. It supplies no application bypass or moderation capability by itself.
- Service/specialized roles: narrowly scoped capabilities. Existing importers with custom write permissions retain their explicitly documented service boundaries.

Groups are permission bundles, not conditionals embedded in views. Direct user permissions remain effective. The version-controlled role manifest declares supported bundles and model classifications; new models never receive permissions by discovery alone. Role inspection is read-only by default. Reconciliation requires an explicit apply mode, reports additions and removals, and does not silently revoke unmanaged production grants. Creation of permission rows after migration is separate from deliberate role reconciliation.

## Read policy

For independently reviewable user-created records:

| Actor | Visible records |
|---|---|
| Anonymous/inactive | Published and archived |
| Owner/editor | Published and archived plus owned/granted records in all states |
| Model moderator | The above plus review and declined records |
| Administrator | All records |

A moderator may also inspect the review history of published and archived records. Moderator status alone does not expose another user's withdrawn private records. Retention of history does not imply continued authorization to view it.

List, detail, map, autocomplete, options, reference validation, counts, and export must agree on read authorization. Purpose-specific filters may narrow results, such as excluding archived choices from new references. Archived records remain publicly readable and exportable as retained, previously published content; archiving does not make them private or erase review history. Active-only listings exclude archives, while explicit archived scopes and historical-year maps include them.

Scopes are refinements of authorized visibility:

- `published`: active published records only (excludes archived).
- `private`: compatibility name for the owned/shared workspace across states, not owner-only privacy.
- `owned`: records owned by the actor.
- `shared`: granted records not owned by the actor.
- `review`, `declined`, `archived`: visible records in that state.
- Unspecified scope: general authorized visibility.
- Unknown scope: no records, never an unfiltered queryset.

## Action rules

| Action | Capability and object access | Lifecycle/other condition |
|---|---|---|
| Create | `add_<model>` | Active actor; private initial state; owner assigned by server |
| Edit content | `change_<model>` and owner/editor/administrator | Private, review, or declined |
| Delete | `delete_<model>` and owner/administrator | Private or declined; protected references and cascade boundaries respected |
| Duplicate | Read original and `add_<model>` | Separate private record owned by actor |
| New version | Read original and `add_<model>` | Non-archived original; separate private record |
| Submit | Owner/administrator | Private or declined |
| Withdraw | Owner/administrator | Review or declined; retain history |
| Approve | Model moderator/administrator; not owner or content contributor | Review; expected revision matches atomically |
| Decline | Model moderator/administrator; not owner | Review; retain history |
| Archive | Owner/model moderator/administrator | Published; retains public read access |
| View review activity | Owner/editor/administrator, or model moderator with current read access | Never made public by publication |
| Comment on review | Same participants as review activity | Active actor; append-only activity |
| Manage sharing/transfer ownership | Owner/administrator | Active target owner; no implicit changes to group membership/model permissions |
| Export | Read authorization | Same visibility as corresponding records |

Owner and publication status are protected fields. Normal content-update payloads cannot set them, including mixed content/status PATCH requests. Use named ownership and lifecycle actions instead. Creating a record cannot accept a forged owner or a published initial state.

Published and archived content is immutable through normal editing, including administrators and owned child rows. Exceptional override actions, if introduced later, require separate explicit authorization and audit; none is implied by this policy. New independent evidence attached to a published or archived record is not an edit of its frozen content; each supported evidence relation must declare its attachment rule explicitly. The evidence has its own model capability, ownership/grants, revision, and review. Public read access alone does not authorize evidence creation, and this exception never permits changes to archived metadata or owned child rows.

## Review is collaborative and revision-bound

Private, review, and declined records are editable by authorized owners/editors. Editing during review keeps the record in review. Routine correction uses comments and edits, not forced decline/withdraw/resubmit.

Each independently reviewable root has a monotonically increasing content revision. An authorized meaningful content change increments it and appends an audit event with actor and changed fields in the same transaction. Owned child/relation changes that form part of reviewed content participate in the root revision. No-op saves, comments, and sharing changes do not increment the content revision.

The review page/context identifies the revision inspected. Approval must supply that expected revision. Missing or stale revision evidence cannot approve. Approval locks/reloads the root, rechecks current actor access, state, contributors, and revision, then publishes and appends the approval event atomically. Content writes use the same root lock and recheck lifecycle eligibility; an edit cannot slip through after approval.

Four-eyes approval excludes the owner and recorded contributors to the candidate being approved, not just its last modifier. Holding a grant or membership alone does not make a user a contributor. Legacy content without contribution events still excludes its owner; migration does not fabricate historic authorship.

Review history is append-only across decline, withdrawal, and resubmission. Current-cycle feedback may be highlighted, but previous cycles remain accessible and labelled. Declined records remain discoverable to current authorized reviewers through a separate filter. Withdrawal to private removes moderator-only access without deleting comments. Review activity must use the same capabilities through ordinary detail pages, review pages, APIs, notification links, and agent context.

## Sharing and discovery

An individual or group editor grant supplies object-scoped read/edit access, not model-wide add/change/delete/moderate permissions. Editing still requires the model change capability and an editable lifecycle state. Sharing never creates a group, changes membership, or assigns model permissions.

Current/future members inherit a group grant while they belong to the group. Removing one grant does not remove other routes to access. Authorization is refreshed on subsequent requests, not cached as a permanent grant. Ownership transfer preserves existing editor grants.

My workspace offers Owned by me, Shared with me, and All workspace records. Shared records identify the owner and the actor's direct/group access route. Recipients can inspect their own effective access without obtaining permission to enumerate or manage everyone else's grants. Owners manage sharing and receive a warning when a proposed edit grant is currently ineffective; the interface must not promise unrestricted control over frozen records.

## Owned children and independent references

Classification is explicit, not inferred from the presence of a foreign key.

Owned child rows, such as bibliography source-author ordering and process author/source/material/parameter/link/resource rows, inherit authorization and lifecycle from their parent. Parent edit permits adding/editing/removing these rows without a separate child-model grant. All standalone child endpoints resolve the parent and enforce the same rule. Forged row IDs, reparenting, and old/new parent checks cannot bypass access. Changes form part of the parent's reviewed revision.

Reusable objects such as Author, Source, Licence, Material, and AnalyticalMethod are independent. Selecting an existing object requires reference/read authorization. Creating it requires its own add capability. Permission to edit a parent never implicitly creates an Author or another independent object.

Compound workflows authorize and validate every required write/reference before mutation, then persist atomically. Source creation with existing authors remains available without author-creation capability. Optional new-author controls are gated independently. Failure leaves no newly created authors, source, or association rows. Modal option refresh uses authorized read visibility, not a second unrelated view-permission gate.

GeoDataset runtime relation/column configuration is an administrator-only specialization of the parent policy: it additionally requires explicit application administration, and never bypasses parent lifecycle or audit.

## Generated projections

Automatically calculated collection values are read-only generated projections of their explicitly linked raw source evidence, not independently approvable records. Source permissions, ownership/editor grants, lifecycle, and review revision govern access; copied projection metadata or grants cannot widen it. Change or review the source instead. Normal users and administrators cannot mutate or approve a projection directly. Legacy generated values without verified source linkage fail closed until an explicitly approved provenance audit/backfill; do not guess links or fabricate history. Conversion formulas are unchanged.

## Maintenance and regression contract

The canonical specification is this document. `user_created_objects.md` is an implementation map, not another policy table. User documentation explains the same rules in practical terms. BRIT-ops authored skills and generated harness rules require consulting this document and running relevant contract tests; installed copies are generated/distributed, never independently patched.

Policy changes update implementation, independently asserted tests, this document, relevant UI/user help, and the affected BRIT-ops workflow references together. Superseded policy branches, conflicting documentation, and misleading policy docstrings are removed/replaced when their callers migrate. Do not work around a denial by adding model permissions to test fixtures unless that fixture intentionally represents a different role.

Required regression coverage:

1. Equivalent actor/action/record decisions across HTML, API, modal, quick-create, and UI capabilities.
2. List/detail/map/reference/autocomplete/export visibility equivalence, unknown scopes, and inactive users.
3. Supported contributor workflows using provisioned roles rather than hand-added allow-path permissions.
4. Direct/group editor grants, membership changes, overlapping grants, transfer, revocation, recipient access explanations, and shared discovery.
5. In-review owner/editor edits retain state/history and root/child revisions; comments/no-op/access changes do not bump content.
6. Stale/missing approval revisions, contributors, and approval/write races fail without partial publication or mutation.
7. Review history survives decline/withdraw/resubmit while current access controls remain effective.
8. Owned children cannot bypass parent policy through standalone endpoints or reassignment.
9. Compound creation rejects inaccessible references and rolls back all partial writes.
10. Explicit model classification/role drift checks; no new model inherits a contributor grant automatically.

## Rollout

Before public-archive rollout, audit legacy archived records: older collection-version approval could archive unpublished predecessors. Archived status alone is not proof that such a legacy record was previously published. Resolve ambiguous records through the explicitly approved data-management workflow before deployment; do not fabricate approval history or silently change production records.

Implement in complete slices: decision core and roles; shared adapters; revision-safe review and collaboration; bibliography/inline creation; remaining domains; final architectural and runtime gates. Keep incomplete domains explicit in task tracking. Do not mutate production roles or deploy migrations as part of local implementation. Review production drift separately before explicit role reconciliation; no silently destructive grant removal or fabricated historical review events.
