# Sharing and collaboration

> **Staging note:** This guide describes the target contract during the draft
> authorization migration tracked in #614. Workspace/sharing surfaces are
> implemented in Part 7a; remaining review navigation, domain/admin adapters,
> generated provenance and release verification are tracked separately. Do
> not treat this guide as deployment approval.

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
