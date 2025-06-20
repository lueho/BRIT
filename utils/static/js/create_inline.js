"use strict";

/**
 * Retrieves the URL for asynchronous data fetching after modal success.
 * Prefers 'data-async-url' attribute, falls back to 'data-url'.
 *
 * @param {HTMLElement} element - The DOM element (usually the button) containing data attributes.
 * @returns {string|undefined} The data URL or undefined if none is found.
 */
function getAsyncDataUrl(element) {
    // Prioritize a specific attribute for clarity, e.g., 'data-async-url'
    let url = element.dataset.asyncUrl;
    if (url) {
        return url;
    }

    // Fallback: Check 'data-url' (common convention)
    url = element.dataset.url;
    if (url) {
        return url;
    }

    // No suitable URL attribute found
    console.warn("No async data URL found ('data-async-url', 'data-url'). Async update might fail.", element);
    return undefined;
}

/**
 * Initializes modal form functionality for designated create buttons.
 * Looks for elements with '.modal-fk-create' class that haven't been initialized yet.
 */
function wireCreateButtons() {
    const buttons = document.querySelectorAll('.modal-fk-create:not(.bmf-bound)');

    buttons.forEach(btn => {
        // --- Configuration Retrieval ---
        const formUrl = btn.dataset.href; // URL for the initial modal form content
        const selectTargetSelector = btn.dataset.select; // Selector for the related <select> element
        const modalTargetId = btn.dataset.modalTarget || '#modal'; // Allow overriding default modal ID
        const asyncDataUrl = getAsyncDataUrl(btn); // URL for fetching data after success
        const targetElementId = btn.dataset.forField; // ID/Selector of element to update

        // --- Validation ---
        if (!formUrl) {
            console.warn('wireCreateButtons: Button missing required "data-href" attribute. Skipping.', btn);
            return;
        }
        if (!selectTargetSelector) {
            console.warn('wireCreateButtons: Button missing required "data-select" attribute. Skipping.', btn);
            return;
        }

        const selectElement = document.querySelector(selectTargetSelector);
        if (!selectElement) {
            console.warn(`wireCreateButtons: Target select element "${selectTargetSelector}" not found for button. Skipping.`, btn);
            return;
        }

        // Mark the button as processed to prevent re-binding
        btn.classList.add('bmf-bound');

        // --- Initialize Modal Plugin ---
        // Use the global modalForm function from django-bootstrap-modal-forms
        modalForm(btn, {
            formURL: formUrl, // URL to load the form from
            modalID: modalTargetId, // Target modal element ID
            errorClass: '.is-invalid', // Error class used by django-crispy-forms
            asyncUpdate: true,
            asyncSettings: {
                closeOnSubmit: true,
                successMessage: '<div class="alert alert-success d-none" role="alert">Operation successful.</div>', // Example success message (initially hidden)
                dataUrl: asyncDataUrl, // URL to fetch updated data (e.g., select options)
                dataElementId: targetElementId, // ID/selector of the element to update with new data
                dataKey: 'options', // Key expected in the fetched JSON response containing the data
                addModalFormFunction: wireCreateButtons // Required by the plugin, even if empty.
            },
        });
    });
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wireCreateButtons);
} else {
    wireCreateButtons();
}