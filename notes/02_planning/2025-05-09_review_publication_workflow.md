# Review & Publication Workflow – Implementation Plan (2025-05-09)

This note tracks the work required to let owners request a review of their objects and let authorised reviewers approve/reject them.

## Context
* Generic parent class: `utils.models.UserCreatedObject` with `publication_status` (`private` ▸ `review` ▸ `published`)
* Collections already override `approve()` to handle predecessor validity
* `UserCreatedObjectPermission` class already exists with much of the required permission logic
* We need a complete workflow implementation with UI and specialized views

## Definition of done
- [ ] Owners can click *"Submit for review"* on their private object → status changes to `review`
- [ ] Reviewers see a list of objects "In review" for each model they moderate
- [ ] Reviewer can **approve** → status `published` (+ any model-specific hooks) OR **reject** → back to `private`
- [ ] All transitions are permission-guarded (owner/reviewer) and logged
- [ ] End-to-end tests cover both happy paths & permission denial

---

## Detailed task checklist

### 1. Model layer changes
- [ ] **Schema changes**
  - [ ] Add `approved_at` (DateTimeField, nullable) to `UserCreatedObject`
  - [ ] Add `approved_by` (ForeignKey to User, nullable, on_delete=PROTECT) to `UserCreatedObject`
  - [ ] Add `submitted_at` (DateTimeField, nullable) to `UserCreatedObject` to track when submitted for review
  - [ ] Create a new migration for these fields

- [ ] **Code & behavior changes**
  - [ ] Create named constants for publication statuses
    ```python
    STATUS_PRIVATE = 'private'
    STATUS_REVIEW = 'review'
    STATUS_PUBLISHED = 'published'
    ```
  - [ ] Refactor `register_for_review()` to:
    - Set `submitted_at` timestamp
    - Clear `approved_at` and `approved_by` if previously approved
    - Return success boolean
    - Update docstring
  - [ ] Create backward-compatibility shim to preserve old method name:
    ```python
    def register_for_review(self):
        return self.submit_for_review()
    ```
  - [ ] Enhance `approve()` method:
    - Set `approved_at` to current time
    - Set `approved_by` to the user who approved (needs user parameter)
    - Call any model-specific hooks (hook mechanism or override)
  - [ ] Add `reject()` method:
    - Set `submitted_at`, `approved_at` and `approved_by` to NULL
    - Take optional `rejection_reason` for future extension
  - [ ] Add history tracking hooks if django-simple-history is used

### 2. QuerySets & Managers
- [ ] Add `.in_review()` method to `UserCreatedObjectQuerySet`
  ```python
  def in_review(self):
      return self.filter(publication_status=STATUS_REVIEW)
  ```
- [ ] Add `.reviewable_items()` method to manager to return only objects:
  - In review status
  - That the user has permission to moderate
- [ ] Add property to `UserCreatedObject`: `is_in_review` (bool)
- [ ] Add property to `UserCreatedObject`: `is_published` (bool)
- [ ] Add property to `UserCreatedObject`: `is_private` (bool)

### 3. Views & URLs
- [ ] **Moderation actions**
  - [ ] Create base class `ModeratorRequiredMixin`:
    - Check `request.user` has moderation permission for model
    - Return 403 if not authorized
  - [ ] Create `SubmitForReviewView` (owner action):
    - POST-only, CSRF protected
    - Inherits `UserOwnsObjectMixin` to restrict to owner
    - Return to detail page with success message
  - [ ] Create `WithdrawFromReviewView` (owner action):
    - POST-only, reverse of above
    - Only allowed if object is in review
  - [ ] Create `ReviewActionView` (reviewer actions):
    - Base class for Approve/Reject
    - Inherits `ModeratorRequiredMixin`
    - logs user performing the action
  - [ ] Create `ApproveObjectView` and `RejectObjectView`
    - Validates correct status before action
    - Handles success/error messages
    - Redirects appropriately

- [ ] **Dashboards & lists**
  - [ ] Create `ReviewDashboardView`:
    - Lists models with reviewable items for moderator
    - Shows counts per model
  - [ ] Create `ReviewQueueListView`:
    - Filtered list of one model's items in review
    - Inherits existing list view mixins
    - Adds approve/reject actions
  - [ ] Update existing item detail views to show review buttons

- [ ] **URL configuration**
  - [ ] Create `urls.py` in `utils/` for review URLs
  - [ ] Create URLs for all actions:
    ```
    /review/                       # main dashboard
    /review/<app>/<model>/         # review queue for model
    /<app>/<model>/<pk>/submit/    # submit for review 
    /<app>/<model>/<pk>/withdraw/  # withdraw from review
    /<app>/<model>/<pk>/approve/   # approve action
    /<app>/<model>/<pk>/reject/    # reject action
    ```
  - [ ] Include review URLs in root `urls.py`

### 4. Templates
- [ ] **Component templates**
  - [ ] Create `review_status_badge.html` partial:
    - Different color badge per status
    - Used in lists and detail views
  - [ ] Create `review_action_buttons.html` partial:
    - Shows appropriate buttons based on permissions + status 
    - Used in detail views and item rows

- [ ] **Page templates**
  - [ ] Create `review_dashboard.html` - main review page
  - [ ] Create `review_queue.html` - model-specific queue
  - [ ] Create confirmation modals for each action:
    - `submit_for_review_modal.html`
    - `withdraw_modal.html`
    - `approve_modal.html`
    - `reject_modal.html`
  - [ ] Update existing templates with new partials

### 5. Admin integration
- [ ] Add `PublicationStatusFilter` to Django admin:
  ```python
  class PublicationStatusFilter(admin.SimpleListFilter):
      title = 'Publication status'
      parameter_name = 'publication_status'
  ```
- [ ] Add admin actions for approve/reject
- [ ] Register filter with each admin class for UCO subclasses

### 6. Tests
- [ ] **Unit tests**:
  - [ ] Test all methods on `UserCreatedObject` - transitions work
  - [ ] Test permissions logic - correct denials as expected
  - [ ] Test queryset methods return correct objects

- [ ] **Integration/view tests**:
  - [ ] Test each view: submit, withdraw, approve, reject
  - [ ] Test permissions denied for unauthorized users
  - [ ] Test model-specific hooks fire correctly (e.g. Collection)
  - [ ] Test URL routing and template rendering

- [ ] **Test utilities**:
  - [ ] Create helper methods for common test operations
  - [ ] Create test fixtures for review workflow

### 7. Documentation
- [ ] Update dev docs on review process
- [ ] Update user guide with new UI workflows
- [ ] Add JSDoc comments for any JavaScript interactions

---

## Potential side effects to address

### Data integrity
- [ ] Migration plan for existing objects:
  - Set default `approved_at=None`, `approved_by=None`, `submitted_at=None` for all objects
  - For objects with `publication_status='published'`, set `approved_at=now()` in the migration
  - Use a data migration to set `approved_by` to admin user (id=1) for published objects
  - Add validation in `clean()` to ensure `approved_at` is set when `publication_status='published'`

- [ ] Handle objects with inconsistent states:
  - Create Django management command `fix_publication_inconsistencies` that:
    - Finds published objects with missing approval metadata and adds it
    - Validates all objects in review have a `submitted_at` value
    - Reports any invalid state transitions detected
  - Run this command after the migration

### Performance
- [ ] Add database index on `publication_status`:
  ```python
  class Meta:
      abstract = True
      indexes = [
          models.Index(fields=['publication_status']),
      ]
  ```
- [ ] Optimize queries in list views:
  - Use `select_related('approved_by')` to avoid extra queries
  - Use `prefetch_related` for collections of objects
  - Add caching for review dashboards (cache for 5 minutes)

### UI/UX impacts
- [ ] Status badge design:
  - Private: Gray badge
  - In Review: Yellow badge
  - Published: Green badge
  - Add tooltips showing timestamps when available

- [ ] Error prevention:
  - All state-changing actions require confirmation modals
  - Approve/reject buttons visually distinct to prevent misclicks
  - Add timeout protection against double-submits (disable button after click)

- [ ] Feedback mechanisms:
  - Use Django messages framework for all actions
  - Add toast notifications for async actions
  - Use clear icons alongside status text
  - Provide detailed permission errors explaining why access is denied

### API compatibility
- [ ] Maintain backwards compatibility:
  - Keep existing endpoints working with same parameters
  - Add new methods rather than changing existing ones
  - Use API versioning if breaking changes needed
  - Document new statuses in API schema

- [ ] Add new review-specific endpoints:
  - POST `/api/v1/<model>/<id>/submit-for-review/`
  - POST `/api/v1/<model>/<id>/withdraw/`
  - POST `/api/v1/<model>/<id>/approve/` (moderator only)
  - POST `/api/v1/<model>/<id>/reject/` (moderator only)

### Dependencies on other systems
- [ ] Transaction handling:
  - Use `@transaction.atomic` or context managers for all status changes
  - Ensure approval hooks in subclasses run within the same transaction

- [ ] Audit logging:
  - Log all status transitions with timestamp, user, and reason
  - Use Django's built-in admin logging or django-simple-history
  - Include before/after state in logs

- [ ] Future notification system integration:
  - Add hook points in approval/rejection methods
  - Create initial stub notification methods that do nothing
  - Document notification integration points for future implementation

---

## Open questions
1. Should we add notification emails to owners when status changes? (Not in MVP)
2. Do we need a rejection reason field for tracking? (Consider for future)
3. How should versioning interact with review status for models besides Collection?

---

*(Follow the complex-refactor checklist once tasks are done)*
