# Sharing and Collaboration

This guide explains how ownership, sharing, review, and visibility work for
user-created records in BRIT.

Published and archived records are publicly readable — archived means
retained, previously published content kept for historical reference, not a
privacy or withdrawal state. Active-only listings exclude archived records,
while explicit `archived` scopes and historical-year views include them.

## What controls access

Three things must all be true before you can change a record:

1. **Capability** — your account has the relevant permission for that type
   of record (for example, the "change sample" permission).
2. **Object access** — you own the record, hold an individual editor grant,
   or belong to a group that has an editor grant on it.
3. **Editable state** — the record is in `private`, `review`, or `declined`.
   `published` and `archived` records are frozen for everyone.

Membership or a grant alone is never enough — you still need the model
permission, and the record must be in an editable state.

## The workspace

The workspace listing (the scope selector on record lists) offers:

- **All workspace records** — every record you own or have a grant on.
- **Owned by me** — only the records you own.
- **Shared with me** — records where you hold an editor grant through an
  individual grant or a group, but do not own.

Additional scopes (`published`, `review`, `declined`, `archived`) filter
records by lifecycle state within what you are allowed to see.

## Sharing a record

Only the owner (or an administrator) can manage access. On the record's
manage-access dialog you can grant editor access to:

- an **individual user** — the grant applies to that account only;
- a **group** — every current and future member of the group receives the
  grant for as long as they remain a member.

Group grants apply to members *and* to the record, not to the model: a
member still needs the relevant change permission, and the record must be
in an editable state, before they can edit. The dialog warns when a
proposed grant would currently be ineffective (for example, because the
record is published or the recipient lacks the change permission).

Removing one grant does not remove access the person has through other
routes — they may still be an individual grantee, a member of another
granted group, or an administrator. Access is re-evaluated on every
request, so revoked access stops working on the next request.

You can also transfer ownership; existing editor grants are preserved.

## Seeing your own access

On any record you can read, the "Your access" dialog shows your effective
access routes — whether you reach it as owner, through an individual grant,
or through a named group — and, when editing is denied, why (missing
permission, frozen state, or no write access). It never lists other
people's grants or memberships.

## Review

Submitting a record moves it to `review`. While in review:

- owners and editors can keep editing; the record stays in `review`;
- reviewers with the model's moderation permission can see it, inspect its
  review activity, and approve or decline it — except that the owner and
  anyone who created or edited the content under review cannot approve it
  (four-eyes rule); approval also requires confirming the exact content
  revision that was inspected, so the review page must be reloaded before
  approving if the record changed meanwhile;
- declining returns it to `declined` and keeps the review history;
- the owner can withdraw it back to `private`; withdrawing removes
  reviewer-only access but never deletes the history.

Approved records become `published`. Published records are visible to
everyone, including anonymous visitors, and cannot be edited — corrections
happen through a new version or newly attached evidence where the record
type supports it.

## Independent evidence

Some data attached to a published or archived record (for example,
property values on a published sample) is stored as an independent record
with its own lifecycle and review. Attaching it does not edit the frozen
parent, and being able to edit the parent does not grant permission to
edit the evidence record — each evidence entry is governed by its own
owner, editors, and permissions. Which kinds of evidence can be attached
to a published or archived parent, and by whom, is defined per record
type.

## Generated values

Some collection values are calculated automatically. These are read-only
projections of the raw source evidence they were derived from — they are
not separate records with their own access rules and they are never
approved on their own. Who can see a generated value, its lifecycle state,
and its review thread all follow the linked source value. To correct or
review a generated value, change or review its source instead; nobody —
including administrators — can edit or approve a generated value directly.
Older generated values that have not yet been linked to their source
remain hidden until their provenance is verified; conversion formulas are
unchanged by any of this.

## What moderation is (and is not)

Moderators hold a per-model `can_moderate_*` permission. Moderation lets a
user see records in `review` (and `declined`) and act on them — it does not
make them an editor of ordinary content, and it does not expose withdrawn
private records of other users. Archived records are retained, previously
published content: they stay publicly readable, but their review thread
remains restricted to authorized participants.

Administrators are an explicit application role (the `administer_objects`
permission or an active superuser account). Being flagged as "staff" for
the Django admin site does **not** grant any application permissions.
