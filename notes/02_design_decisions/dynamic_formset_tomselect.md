# Handling TomSelect in Dynamic Formsets

* Status: accepted
* Deciders: Development team
* Date: 2025-06-09

## Context and Problem Statement

Django formsets provide a powerful way to handle multiple form instances, but integrating them with TomSelect widgets requires additional JavaScript handling for proper initialization when adding new forms dynamically. The specific problem was that TomSelect widgets in dynamically added formset rows were not being initialized properly, causing the autocomplete functionality to fail.

## Decision Drivers

* Need for consistent formset management across the project
* Complexity of properly reinitializing TomSelect in dynamically added forms
* Need to address the double form row insertion bug in previous implementation
* Support for different layout options (table-based, div-based)
* Integration with crispy-forms for consistent styling
* Preference for ES6 JavaScript without jQuery dependencies

## Considered Options

1. Fix the current `dynamic-formset.js` implementation
2. Implement the proposed comprehensive solution from `notes/02_planning/01_formset_templating.md`
3. Create a hybrid solution that combines the best of both approaches

## Decision Outcome

Chosen option: "Create a hybrid solution that combines the best of both approaches", because it provides a robust and maintainable solution while preserving existing functionality. The implementation includes:

1. A new `tomselect-formset.js` component that properly handles TomSelect initialization
2. A reusable Django template for rendering formsets with TomSelect widgets
3. Documentation in `notes/frontend/tomselect-formset.md`

### Positive Consequences

* Solves the double form insertion bug by using proper event handling
* Ensures TomSelect widgets are properly initialized in new rows
* Provides a consistent API for formset management
* Follows project coding standards (ES6, no jQuery)
* Reusable across different parts of the application
* Well-documented for future maintenance

### Negative Consequences

* Requires updating existing code to use the new component
* Adds complexity compared to the original implementation
* May require additional testing to ensure compatibility with all use cases

## Pros and Cons of the Options

### Fix the current `dynamic-formset.js` implementation

* Good, because it requires minimal changes to existing code
* Good, because it focuses only on fixing the immediate issues
* Bad, because it doesn't address the need for a more comprehensive solution
* Bad, because it may not handle all edge cases with TomSelect initialization

### Implement the proposed comprehensive solution

* Good, because it provides a complete solution with both JS and templates
* Good, because it follows Django conventions for formset handling
* Bad, because it requires significant changes to existing templates
* Bad, because it might introduce compatibility issues with existing code

### Create a hybrid solution (chosen)

* Good, because it provides the best of both approaches
* Good, because it's modular and can be adopted incrementally
* Good, because it properly addresses the TomSelect initialization issues
* Good, because it follows the project's coding standards
* Bad, because it requires maintaining additional code

## Technical Implementation Details

The implementation consists of:

1. A new `tomselect-formset.js` file with a `TomSelectFormset` class:
   - Handles form addition/removal
   - Carefully preserves TomSelect configuration
   - Properly reinitializes TomSelect on new forms

2. A `tomselect_dynamic_formset.html` template:
   - Supports both table and div layouts
   - Integrates with crispy-forms
   - Uses data attributes for configuration

3. Documentation for developers in `notes/frontend/tomselect-formset.md`

## Links

* Related to [notes/02_planning/01_formset_templating.md]
