# Administration and Bulk Actions

> **Draft stack, not yet deployable.** These behaviours describe the shared
> policy-driven administration surface. Domain-specific validation and
> generated-data activation are still open, and browser verification remains
> outstanding.

Governed records in the administration area use the same
[authorization policy](../02_developer_guide/security_permission_validation.md)
as the rest of the application. Staff status permits entry to Django admin;
it does not grant application editing or moderation rights. Writes still
require the appropriate capability, object access and lifecycle eligibility.

## What you can see and change

- Lists show only records you may read. Each change or delete request is
  checked against the current permissions, not just the displayed controls.
- Owner, status, revision and audit metadata are read-only. Use the normal
  application's named ownership and lifecycle actions instead of editing
  these fields in an admin form.
- Choose a structural parent when creating an attached record. Its parent
  relation becomes read-only after creation; posting a different parent is
  rejected.
- Published and archived content remains frozen, even for administrators.
- Inline children (for example, authors on a source) are governed by their
  parent: you can view them when the parent is readable, and edit them only
  where you may edit the parent.
- Governed reference pickers offer only records you are allowed to read.

Source-author positions are content, not lifecycle metadata. Enter positive
positions starting at 1; changing their order requires authority over the
source, not a separate permission on the association row. Creating a new
independent Author still requires its own creation capability.

## Deleting records

Deletion is **confirmed**: selecting records and choosing *Delete selected*
first shows a preview of what will be removed — nothing is deleted at that
step. Only confirming the preview performs the deletion. Records you may not
delete — foreign private content, published or in-review records, archived
material, or rows protected by references — are skipped with a clear count of
what was actually deleted; they are never silently removed nor listed by
private detail.

Governed content changes and deletions are recorded in the **read-only review
history** of the affected root. Owned child changes share that root's revision
and history. Even administrators cannot add, edit or delete review events
through Django admin. This does not replace Django's separate admin log.

## Review in the admin

There is no bulk approval shortcut. Open the record in the normal application's
detail/review workspace to inspect its revision and approve it there. Approval
is bound to that inspected revision; later changes require re-inspection.
The admin does not provide an alternative approval path.
See [Sharing and collaboration](sharing_and_collaboration.md).

> Application administration requires the dedicated administration
> capability, not just the staff flag — the flag alone is never a second
> policy.
