# Reusable TomSelect Formset Template Implementation

* Status: proposed
* Deciders: Development team
* Date: 2025-06-09

## Context and Problem Statement

Django formsets provide a powerful way to handle multiple form instances, but integrating them with TomSelect widgets requires additional JavaScript handling for proper initialization when adding new forms dynamically. How can we provide a reusable solution that handles the complexity of formset management while ensuring TomSelect widgets are properly initialized?

## Decision Drivers

* Need for consistent formset management across the project
* Complexity of properly reinitializing TomSelect in dynamically added forms
* Desire for a DRY approach to formset management
* Support for different layout options (table-based, div-based)
* Integration with crispy-forms for consistent styling

## Considered Options

1. Simple add button template with JavaScript to clone existing forms
2. Comprehensive formset template that leverages Django's empty_form
3. No template, rely on project-specific implementation for each use case

## Decision Outcome

Chosen option: "Comprehensive formset template that leverages Django's empty_form", because it provides the most robust and maintainable solution. The template handles both the form structure and the JavaScript required for properly initializing TomSelect in new forms.

### Positive Consequences

* Consistent approach to formset management across the project
* Leverages Django's built-in formset features (empty_form, management form)
* Integrates well with crispy-forms for styling
* Supports multiple layout options (table and div-based)
* Handles TomSelect initialization automatically
* Provides form deletion functionality

### Negative Consequences

* Increased template complexity
* Assumes crispy-forms is being used (template dependency)
* May need future updates if TomSelect initialization logic changes

## Pros and Cons of the Options

### Simple add button template with JavaScript to clone existing forms

* Good, because it's simple to implement
* Good, because it works with any form structure
* Bad, because cloning DOM elements is less reliable than using Django's empty_form
* Bad, because it requires careful cleanup of TomSelect instances

### Comprehensive formset template that leverages Django's empty_form

* Good, because it uses Django's built-in formset capabilities
* Good, because it provides a complete solution (add, delete, reinitialize)
* Good, because it's highly customizable with template parameters
* Good, because it supports different layouts
* Bad, because it's more complex
* Bad, because it has external dependencies (crispy-forms)

### No template, rely on project-specific implementation for each use case

* Good, because it offers maximum flexibility
* Good, because it has no external dependencies
* Bad, because it leads to code duplication
* Bad, because it increases the chance of bugs in formset handling
* Bad, because it requires developers to understand TomSelect initialization

## Implementation Details

The implementation consists of two template files:

1. `formset_add_button.html` - A simple button that adds new form rows
2. `tomselect_formset.html` - A complete formset solution with crispy-forms integration

The latter is the recommended approach for most use cases as it provides a more comprehensive solution.
