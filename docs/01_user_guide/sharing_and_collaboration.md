# Sharing and collaboration

> **Staging note:** This guide describes the target contract during the draft
> authorization migration tracked in #614. Workspace/sharing surfaces are
> implemented in Part 7a, and the shared review workspace in Part 7b.
> Domain/admin adapters, generated provenance and browser/release verification
> remain tracked separately. Do not treat this guide as deployment approval.

The normative rules behind this page are defined in
[Security & Permission Validation](../02_developer_guide/security_permission_validation.md).
This page explains what they mean for your day-to-day work.

## Your workspace

Migrated shared list/detail views offer three workspace scopes:

- **All workspace records** — records you own plus records shared with you.
- **Owned by me** — records where you are the owner.
- **Shared with me** — records where a direct or group grant gives you
  access. Records you own are never listed here, even when a redundant grant
  exists.

Only records you may actually see appear in these lists; the scopes filter
your authorized view, they never widen it.

## Sharing a record you own

From **Manage access** (visible to owners and application administrators) you
can:

- **Transfer ownership** to another active user. Existing editor grants stay
  in place, so a former owner keeps any direct or group access route they
  already had.
- **Add or remove a direct editor grant** for a user.
- **Add or remove a group editor grant** for a team.

A grant is scoped to that one record. Whether the recipient can actually edit
it still depends on their own permissions and the record's lifecycle state —
a grant alone never confers model-level permission, and group membership
alone does not guarantee that every member can edit. Current and future group
members inherit a group grant, but sharing never changes anyone's group
membership or model permissions. Removing one access route (for example a
direct grant) may still leave another route (such as a group grant or
ownership) in place. Published and archived content stays frozen regardless
of grants.

## Seeing your own access

Readers who cannot manage sharing get a **Your access** link instead. It
shows who owns the record and through which routes (ownership, direct grant,
group grant, or public visibility) you can access it, plus whether you may
edit — never other users' grants or memberships.

## Sharing and review

Owners (and application administrators) decide when a record is submitted for
review. Editor grants let recipients edit the record while it is editable;
review transitions are separately authorized and a record's lifecycle is
never changed by sharing actions.

### Review workspace

Moderators — users holding a model's moderation permission, or application
administrators — work from the review dashboard, which shows **pending
review** items by default. A separate **Declined** review-state filter exposes
declined follow-up history. A declined record cannot be approved until its
owner or an application administrator resubmits it to review. Your own
submissions never appear in either queue. The owner and recorded content
contributors cannot approve the candidate; non-owner contributors with
moderation rights may still reject it.

- Meaningful edits while a record is in review keep it in review and bump
  its content revision; prior comments and review history survive.
- The review page always shows the current content revision, and the Approve
  control binds the revision it was rendered for. If the record changed
  after the page loaded, the stale approval fails safely — reload the review
  page to approve the current candidate.
- From list rows, **Review for approval** opens the review page for
  inspection before any decision; there is no one-click list approval.
- Withdrawal to private removes moderator-only access, without deleting
  history for the owner and other authorized participants.
- Application administrator access requires the explicit administration
  capability or active superuser status. Staff status alone grants no review
  or sharing powers.

Domain-specific review integration, admin adapters, generated-provenance
surfaces, and final browser/release verification remain separate work.
