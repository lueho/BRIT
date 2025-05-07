# Regression: Source Creation Without Author Causes IntegrityError

## Date
2025-05-07

## Summary
A production error occurred when creating a Source without specifying an author. The database raised an IntegrityError due to a null value in the `author_id` column of the `bibliography_sourceauthor` table, which violates a NOT NULL constraint.

## Correct Requirement
- It should be possible to create a Source without any authors.
- If no author is provided, no `SourceAuthor` record should be created.
- The formset/model logic should not attempt to save a `SourceAuthor` if the author field is empty.

## How it Happens
- The Source creation form or formset allows submission without an author.
- The save logic in `bibliography/forms.py` attempts to save a `SourceAuthor` even when no author is provided, resulting in a null `author_id` and a database error.

## Impact
- Users can trigger a server error (HTTP 500) by submitting a Source without an author.
- This is a regression and should be handled gracefully in the formset/model logic.

## Next Steps
- Add a regression test to ensure creating a Source without an author does not raise an error and does not create a `SourceAuthor` row.
- Update the formset/model logic to skip saving `SourceAuthor` objects when the author is not provided.
- Review for similar issues elsewhere in the codebase.

---

**This note should be updated after the test and/or fix is implemented.**
