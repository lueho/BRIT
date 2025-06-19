---
# Configuration for the Jekyll template "Just the Docs"  
parent: Decisions
nav_order: 101
title: Bibliography Circular Import Fix

status: accepted
date: 2025-06-15
decision-makers: [LLM Agent, User]
---

# Fix Bibliography Circular Import Using Lazy Loading

## Context and Problem Statement

The bibliography app tests were failing with a circular import error: `cannot import name 'SourceAuthorForm' from partially initialized module 'bibliography.forms'`. This occurred during Django's test initialization sequence when `bibliography.inlines.py` directly imported form classes at module level, creating a dependency cycle during app loading.

The import chain was:
- `bibliography.forms` → defines `SourceAuthorForm`
- `bibliography.inlines` → imports `SourceAuthorForm` from `.forms`  
- `bibliography.views` → imports `SourceAuthorInline` from `.inlines`
- Circular dependency during Django test/app loading

## Decision Drivers

* **Test suite must pass**: Blocking development workflow
* **Minimal code changes**: Avoid major refactoring of working functionality
* **Django best practices**: Follow recommended patterns for avoiding circular imports
* **Maintainability**: Solution should be clear and not introduce complexity

## Considered Options

* **Option 1**: Use string references instead of direct imports in inlines.py
* **Option 2**: Move inline definitions to different module to avoid early import
* **Option 3**: Implement lazy imports using property methods in inline classes
* **Option 4**: Refactor form/inline architecture to eliminate dependencies

## Decision Outcome

Chosen option: "**Option 3: Implement lazy imports using property methods**", because it provides the cleanest solution with minimal code changes, follows Django patterns for avoiding circular imports, and maintains the existing architecture.

### Implementation

Modified `bibliography/inlines.py` to:
- Remove direct imports of `SourceAuthorForm` and `SourceAuthorFormSet` at module level
- Add `@property` methods for `form_class` and `formset_class` that import forms when accessed
- This defers imports until after Django app initialization is complete

```python
@property
def form_class(self):
    """Lazy import to avoid circular dependency during Django app initialization."""
    from .forms import SourceAuthorForm
    return SourceAuthorForm

@property  
def formset_class(self):
    """Lazy import to avoid circular dependency during Django app initialization."""
    from .forms import SourceAuthorFormSet
    return SourceAuthorFormSet
```

### Consequences

* **Good**: Eliminates circular import during test initialization
* **Good**: Minimal code changes - only affects one file
* **Good**: Maintains existing functionality and API
* **Good**: Follows Django lazy loading patterns
* **Neutral**: Slight performance overhead from property access (negligible)
* **Good**: Easier to debug import issues in the future

### Confirmation

- All bibliography tests now pass with exit code 0
- No functional changes to form behavior or UI
- Import chain verified to work in both test and runtime environments
- Code review confirms pattern follows Django best practices
