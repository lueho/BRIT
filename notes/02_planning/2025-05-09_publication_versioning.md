---
created: 2025-05-09
summary: Proposal to align publication workflow with versioning of UserCreatedObjects (e.g. Collection)
---

# Problem statement
*   `UserCreatedObject` introduces a **publication workflow** (`private → review → published`) to control visibility.
*   Versioned domain models (e.g. `Collection`) manage temporal validity via `valid_from`, `valid_until`, and self-referencing `predecessors`.
*   Current implementation **invalidates** the predecessor (`predecessor.valid_until = successor.valid_from - 1`) **immediately** when a successor object is created via `add_predecessor()`, **regardless of publication state** of the successor.
*   If the successor is still *private* or *in review*, the predecessor is already filtered out from *public* queries (which look only at `valid_from/valid_until`), producing a visibility gap.  
  → Users see *no* active collection although the predecessor should remain valid until the successor is effectively *published*.

# Requirements
1. Keep the editing & review UX unchanged: users may clone a predecessor, adjust data, and submit for review.
2. Ensure the **public audience** always sees an uninterrupted, time-continuous published version.
3. Avoid complex duplication; stay within Django ORM if possible.
4. Provide a clear mental model for developers: *publication* controls **visibility**, *versioning* controls **temporal validity**.

# Design options
## A. Post-publish predecessor update (recommended)
* Defer setting `predecessor.valid_until` until the successor changes `publication_status` → `published`.
* Implementation:
  1. Move the date-adjustment logic out of `add_predecessor()` into `approve()` of the successor.
  2. On `approve()`, in a single DB transaction:
     * Set `self.publication_status = "published"`.
     * For each `predecessor`:
       * If `predecessor.valid_until` is `NULL` **or** later than `self.valid_from - 1`, update it to `self.valid_from - 1`.
       * (Optional) mark predecessor as `archived` or retain publication state.
* Pros:  
  – Minimal changes, preserves current data model.  
  – Clear chronological switch aligned with visibility.  
  – Works for chains of successors.
* Cons:  
  – Need to guard against manual edits that bypass `approve()`.

## B. Separate *draft* validity fields
* Add `draft_valid_from`, `draft_valid_until` used while object is `private/review`.  
  `valid_from/valid_until` remain unchanged until publish.
* On publish, copy draft fields into the canonical ones and close predecessor.
* Pros: explicit; predecessor logic untouched.
* Cons: field bloat, duplicated logic, migration effort.

## C. Dual query sets (visibility-aware)
* Keep current predecessor closing behaviour but change all public queries to add: `publication_status='published'`.  
  Provide helper manager: `Collection.objects.publicly_valid(date=today)`.
* Pros: no model change.
* Cons: easy to forget filter, still removes predecessor for *internal* users relying only on dates.

# Proposed solution
Adopt **Option A (post-publish predecessor update)**:
1. **Policy**: A predecessor remains valid until *all* of its successors that start before its open interval are **published**.
2. **Implementation tasks**
   - [ ] Refactor `add_predecessor()` to *link* objects only.
   - [ ] Extend `UserCreatedObject.approve()` (or a mixin) to:  
     ```python
     @transaction.atomic
     def approve(self):
         super().approve()  # sets publication_status & saves
         for pred in self.predecessors.all():
             cutoff = self.valid_from - timedelta(days=1)
             if not pred.valid_until or pred.valid_until > cutoff:
                 pred.valid_until = cutoff
                 pred.save(update_fields=["valid_until"])
     ```
   - [ ] Add model test cases covering:  
     * gap prevention
     * multi-successor chains
   - [ ] Review admin/UI to ensure users cannot alter `valid_until` manually on predecessors after publish.
3. **Query helpers**
   - Provide managers:
     ```python
     class PublishedValidQuerySet(models.QuerySet):
         def valid(self, at=None):
             at = at or date.today()
             return self.filter(publication_status='published')\
                        .filter(valid_from__lte=at)\
                        .filter(Q(valid_until__gte=at) | Q(valid_until__isnull=True))
     ```

# Checklist
- [ ] Confirm no existing notes/designs conflict with this plan.
- [ ] Draft migrations & refactor code.
- [ ] Implement unit tests.
- [ ] Update docs/ADR.
- [ ] Run full test suite.

# Open questions
* Do we need a separate `archived` publication state for predecessors after succession?  
* How to handle deletion of unpublished successors?
