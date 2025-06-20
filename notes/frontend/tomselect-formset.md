# TomSelect Formset JS Component

## Overview

The TomSelect Formset component provides a reusable solution for handling Django formsets with TomSelect integration. It solves the problem of properly initializing TomSelect widgets in dynamically added formset rows.

## Features

- Properly handles TomSelect initialization in dynamically added formset rows
- Provides form row addition and removal functionality
- Preserves all TomSelect configurations and data attributes
- Works with both table-based and div-based layouts
- Automatic renumbering of form indices on removal
- Support for Django's DELETE field for soft deletion
- No jQuery dependencies (ES6 pure JavaScript)

## Usage

### 1. Basic Usage with Data Attributes

Add the `data-tomselect-formset` attribute to your formset container:

```html
<div data-tomselect-formset="myformset">
    <!-- Formset content -->
</div>
```

Include the JS file in your template:

```html
<script src="{% static 'js/tomselect-formset.js' %}"></script>
```

### 2. Manual Initialization

For more control, initialize the formset manually:

```javascript
document.addEventListener('DOMContentLoaded', function() {
    window.initTomSelectFormset({
        formPrefix: "myformset",
        formId: "custom-form-id",  // Optional
        containerSelector: "#custom-container", // Optional
        emptyFormSelector: "#custom-empty-form", // Optional
        addButtonSelector: "#custom-add-button" // Optional
    });
});
```

## Required HTML Structure

The component expects the following HTML structure:

```html
<!-- Management form -->
<div>{{ formset.management_form }}</div>

<!-- Container (table or div) -->
<div id="[formId_]formset-container">
    <!-- Empty form template (hidden) -->
    <div id="[formId_]empty-form-row" class="d-none formset-form-row">
        <!-- Form fields -->
        <!-- Include a remove button with class "remove-form" -->
    </div>
    
    <!-- Existing form rows -->
    <div class="formset-form-row">
        <!-- Form fields -->
        <!-- Include a remove button with class "remove-form" -->
    </div>
</div>

<!-- Add button -->
<button id="[formId_]add-form">Add</button>
```

## Implementation Details

The implementation uses ES6 class-based structure and follows the project's standards for frontend code:
- Pure JavaScript with no jQuery dependencies
- Uses delegation for event handling
- Carefully preserves TomSelect configuration and functionality
- Well-documented for maintainability

## Integration with Django-TomSelect

This component works with the `djangoTomSelect.reinitialize()` method, ensuring that dynamically added TomSelect widgets function correctly.

## Future Improvements

- Add support for sorting/reordering formset rows
- Enhance animation options for adding/removing rows
- Improve error handling for form validation
