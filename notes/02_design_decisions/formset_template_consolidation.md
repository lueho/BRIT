---
# Configuration for the Jekyll template "Just the Docs"
parent: Decisions
nav_order: 300
title: Formset Template Consolidation

status: "accepted"
date: 2025-06-09
---

# Consolidate Dynamic Formset Templates

## Context and Problem Statement

Two very similar formset templates existed in the codebase (`dynamic_table_inline_formset.html` and `tomselect_dynamic_formset.html`) with significant code duplication. Both templates performed essentially the same function - rendering dynamic formsets with add/remove functionality - with the only difference being TomSelect integration in one of them.

This led to several issues:
- Template changes had to be made in multiple places
- Bug fixes like the duplicate label issue needed to be implemented twice
- Styling inconsistencies between the templates
- Violated DRY principles from our coding ethos

## Decision Drivers

* Eliminate code duplication between templates
* Ensure consistent behavior between regular and TomSelect formsets
* Improve maintainability by having a single source of truth
* Provide clear, consistent naming conventions
* Fix the duplicate label issue across all formsets

## Considered Options

* **Option 1**: Keep separate templates but create shared includes
* **Option 2**: Refactor into a base template with extensions
* **Option 3**: Consolidate into a single template with conditional logic

## Decision Outcome

Chosen option: "**Option 2: Refactor into a base template with extensions**", because it provides the best balance between code reuse and separation of concerns while adhering to Django template inheritance patterns.

### Implementation Details

1. Created a new template hierarchy:
   - `formset_base.html`: Core formset functionality
   - `formset_tomselect.html`: TomSelect-specific extensions

2. Created a unified FormHelper hierarchy:
   - `BaseFormsetHelper`: Abstract base class with shared functionality
   - `DynamicFormsetHelper`: For standard formsets
   - `DynamicTableInlineFormSetHelper`: Maintained for backward compatibility
   - `TomSelectFormsetHelper`: For formsets with TomSelect integration

3. Created a unified JavaScript file `formset.js` that handles both regular and TomSelect formsets

4. Added external CSS to handle common styling concerns like duplicate label hiding

### Consequences

* **Good**, because we eliminated template code duplication
* **Good**, because label duplication issue is fixed consistently across all formsets
* **Good**, because adding new formset features only requires changes in one place
* **Good**, because we maintain backward compatibility with existing code
* **Bad**, because legacy templates and helpers are kept for backward compatibility until a future cleanup

### Migration Plan

1. Maintain backward compatibility with existing formsets
2. Update documentation to recommend the new helpers for new code
3. Gradually migrate existing formsets to the new system in future PRs
