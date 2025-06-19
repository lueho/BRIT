---
# Configuration for the Jekyll template "Just the Docs"
parent: Decisions
nav_order: 100
title: Dynamic Formset TomSelect Integration
status: "accepted"
date: 2025-06-09
---

# Single Script Approach for Dynamic Formsets with TomSelect Integration

## Context and Problem Statement

We faced multiple issues with dynamic Django formsets containing TomSelect widgets:
1. Clicking the "Add" button added two identical form rows instead of one
2. TomSelect widgets in dynamically added rows were either not initialized or showing errors
3. JavaScript errors appeared related to missing `resetVarName` variables
4. Redundant form labels were present in the UI
5. Multiple TomSelect wrappers were created for the same select element

These issues were affecting usability and causing JavaScript errors across multiple forms in the application.

## Decision Drivers

* Avoid duplicate event handlers causing multiple form additions
* Ensure proper TomSelect initialization in dynamically added form rows
* Prevent JavaScript errors during form manipulation
* Maintain consistent UI with proper form labels
* Follow project's code quality guidelines and DRY principles

## Considered Options

* **Option 1**: Create a new standalone JS module that handles all formset functionality
* **Option 2**: Patch the existing dynamic-formset.js to handle TomSelect
* **Option 3**: Use a third-party library for dynamic formsets
* **Option 4**: Create a Django widget that handles both formset and TomSelect functionality

## Decision Outcome

Chosen option: "Option 1: Create a new standalone JS module", because:

1. It provides a clean modern ES6 approach without jQuery dependencies
2. It allows for better separation of concerns and maintainability
3. It avoids compatibility issues with the existing implementation
4. It enables proper handling of TomSelect configurations with functions

### Implementation Details

Our solution addresses the issues by:

1. **Single Script Approach**: Consolidated all formset logic into `tomselect-formset.js` and removed all references to the old `dynamic-formset.js` script to prevent duplicate event handlers

2. **Clean Initialization**: Implemented a robust initialization mechanism that:
   - Tracks which formsets have already been initialized using a global Set
   - Removes any existing TomSelect wrappers before initializing new ones
   - Directly calls Django's TomSelect initialization function on each element

3. **Preventing Event Duplication**: Added event handler cleanup by cloning and replacing the "Add" button to remove any existing handlers

4. **Error Handling**: Added comprehensive error handling and logging for TomSelect initialization

### Consequences

**Positive:**
- Single form row now added when clicking the "Add" button
- TomSelect widgets fully functional in dynamically added rows
- No JavaScript errors during form manipulation
- Consistent UI with proper form labels
- Reusable solution across multiple forms

**Negative:**
- Required updates to multiple templates to remove old script references
- Added complexity in widget initialization logic
