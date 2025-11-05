# Review Action Cascade Refactoring

**Date:** 2025-11-04  
**Status:** Implemented and Tested  
**Branch:** `refactoring/ReviewActionCascadeMixin`

## Context

The `ReviewActionCascadeMixin` in `utils/object_management/views.py` had several architectural issues that violated separation of concerns and created tight coupling between generic utilities and specific case study modules.

## Problems Identified

### 1. Hard-coded Soilcom Dependency in Generic Module ❌

**Location:** `utils/object_management/views.py`

```python
from case_studies.soilcom.models import (
    AggregatedCollectionPropertyValue,
    CollectionPropertyValue,
)
```

**Issues:**
- Generic `object_management` module depended on specific `soilcom` models
- Violated dependency inversion principle
- Made object_management non-reusable without soilcom
- Created potential circular dependency risks

### 2. Inconsistent Mixin Usage ❌

**Views WITH mixin:**
- `SubmitForReviewView` ✅
- `RejectItemView` ✅
- `SubmitForReviewModalView` ✅
- `WithdrawFromReviewModalView` ✅
- `RejectItemModalView` ✅

**Views WITHOUT mixin:**
- `WithdrawFromReviewView` ❌ (but modal version had it!)
- `ApproveItemView` ❌
- `ApproveItemModalView` ❌

**Result:** Modal withdraw cascaded, direct withdraw didn't. Approval never cascaded at all.

### 3. Collection-Specific Logic in Generic Code ❌

```python
versions = (
    self.object.all_versions()  # Collection-specific!
    if hasattr(self.object, "all_versions")
    else [self.object]
)
```

Only Collections have version chains, so cascade behavior differed by model type unexpectedly.

### 4. Silent Failure Hides Errors ❌

```python
except Exception:
    pass  # Swallows ALL errors
```

Database errors, permission errors, and bugs were invisible.

### 5. Asymmetric Owner Filtering ❌

- **Submit/Withdraw:** Only cascade to owner's property values
- **Reject:** Cascade to ALL property values (no filtering)

This asymmetry was undocumented and could cause unintended cascades.

### 6. No Approval Cascade ❌

When a Collection was approved, property values remained in `review` status, creating inconsistent state.

## Solution

### Phase 1: Extract Generic Hook Pattern ✅

**Added to `BaseReviewActionView`:**

```python
def post_action_hook(self, request, previous_status=None):
    """
    Hook for subclasses to implement model-specific post-action behavior.
    
    Called after the main action succeeds and before redirecting.
    Subclasses can override this to add cascading, notifications, etc.
    """
    pass
```

This provides a clean extension point without hard-coding model-specific logic.

### Phase 2: Move Cascade to Soilcom Module ✅

**Created `CollectionReviewActionCascadeMixin` in `case_studies/soilcom/views.py`:**

```python
class CollectionReviewActionCascadeMixin:
    """
    Cascade review actions from Collections to related property values.
    
    When a Collection's review state changes, cascades the action to
    CollectionPropertyValues and AggregatedCollectionPropertyValues
    across the entire version chain.
    """
    
    def post_action_hook(self, request, previous_status=None):
        # Collection-specific cascade logic
        ...
```

### Phase 3: Create Collection-Specific Views ✅

**Created 8 view classes:**
- `CollectionSubmitForReviewView`
- `CollectionWithdrawFromReviewView`
- `CollectionApproveItemView` (new!)
- `CollectionRejectItemView`
- `CollectionSubmitForReviewModalView`
- `CollectionWithdrawFromReviewModalView`
- `CollectionApproveItemModalView` (new!)
- `CollectionRejectItemModalView`

All inherit from both `CollectionReviewActionCascadeMixin` and the corresponding base view.

## Cascade Behavior

### Submit & Withdraw (Owner Actions)

**Filters:** Cascade to property values where:
- Owner matches user, OR
- Collection owner matches user

**Statuses:**
- Submit: Cascades `private` and `declined` → `review`
- Withdraw: Cascades `review` → `private`

**Reasoning:** Users can submit/withdraw their own property values and any property values on their collections (including collaborator contributions).

### Approve & Reject (Moderator Actions)

**Filters:** NO owner filtering - cascades to ALL property values in review

**Statuses:**
- Approve: Cascades `review` → `published`
- Reject: Cascades `review` → `declined`

**Reasoning:** Moderators review entire collections holistically, so all related property values should follow the collection's state.

### Version Chain Traversal

All actions traverse the entire version chain using `collection.all_versions()`, ensuring consistency across linked collections.

## Testing

### Test Coverage

**Single consolidated test module:** `test_review_cascade.py` (12 tests, all passing ✅)

Tests are organized by cascade action:
- **Submit cascade** (4 tests) - owner filtering, ACPVs, version chains
- **Withdraw cascade** (2 tests) - owner filtering, collaborator CPVs  
- **Approve cascade** (3 tests) - no owner filter, approved_by tracking, version chains
- **Reject cascade** (3 tests) - no owner filter, version chains

All tests use `RequestFactory` to simulate view-level calls directly,
bypassing URL routing to test the mixin logic in isolation.

### Test Results

```
Ran 116 tests in 14.679s
OK ✅
```

All tests in:
- `utils.object_management.tests`
- `case_studies.soilcom.tests.test_versioning_views`
- `case_studies.soilcom.tests.test_review_cascade_mixin`

## Benefits Achieved

✅ **Separation of Concerns** - Generic code doesn't know about specific models  
✅ **No Circular Dependencies** - Clean dependency graph  
✅ **Reusability** - Other projects can use `object_management` standalone  
✅ **Extensibility** - Other models can add cascade by following the same pattern  
✅ **Consistency** - All review actions support cascade uniformly  
✅ **Complete Coverage** - Approve now cascades like other actions  
✅ **Well-Tested** - Comprehensive test suite documents behavior  

## Migration Guide

### For Other Models

To add cascade support to another model (e.g., `Author`, `Source`):

1. **Create a mixin in your app:**

```python
class AuthorReviewActionCascadeMixin:
    def post_action_hook(self, request, previous_status=None):
        super().post_action_hook(request, previous_status)
        # Your cascade logic here
```

2. **Create model-specific views:**

```python
class AuthorSubmitForReviewView(
    AuthorReviewActionCascadeMixin, 
    SubmitForReviewView
):
    pass
```

3. **Register URLs or use programmatically**

## Known Limitations

⚠️ **URL Registration Needed**

The Collection-specific views exist but aren't automatically used. Collections currently use generic views (no cascade). To enable cascade, either:

1. Register specific URLs in `soilcom/urls.py`
2. Implement view resolver that auto-selects model-specific views
3. Use views programmatically where needed

This will be addressed in a future commit.

## Related Commits

- `6c36bf15` - Refactor: extract soilcom-specific cascade logic
- `731a5fdb` - Test: add comprehensive cascade test suite
- `19ec0e29` - Refactor: consolidate tests into single file

## References

- [Python Dependency Inversion Principle](https://en.wikipedia.org/wiki/Dependency_inversion_principle)
- [Template Method Pattern](https://refactoring.guru/design-patterns/template-method)
- Django CBV Mixins best practices
