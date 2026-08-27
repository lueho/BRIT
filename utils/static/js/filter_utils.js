"use strict";

function parseFilterParameters() {
    const form = document.querySelector('form');
    if (!form) {
        console.warn('No form found on the page. Returning an empty URLSearchParams object.');
        return new URLSearchParams();
    }
    const formData = new FormData(form);
    const params = new URLSearchParams(formData);
    
    // Remove CSRF token (not needed for GET requests)
    params.delete('csrfmiddlewaretoken');
    
    // Remove empty parameters
    for (const [key, value] of params.entries()) {
        if (value.trim() === '') {
            params.delete(key);
        }
    }
    
    return params;
}

function cleanAndSubmitForm(form) {
    const params = parseFilterParameters();
    const action = form.action || window.location.pathname;
    const cleanUrl = action + (params.toString() ? '?' + params.toString() : '');
    window.location.href = cleanUrl;
    return false;
}

function initFilterFormCleanup() {
    const form = document.querySelector('form[method="get"]');
    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            cleanAndSubmitForm(this);
        });
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', initFilterFormCleanup);

function lockFilter() {
    const submitButtons = document.querySelectorAll('.submit-filter');
    submitButtons.forEach(btn => {
        btn.value = 'Loading...';
        btn.textContent = 'Loading...';
        btn.disabled = true;
    });
}

function lockCustomElements() {
    // This is a hook to override if there are any other elements to lock that are specific to the page.
}

function unlockFilter() {
    const submitButtons = document.querySelectorAll('.submit-filter');
    submitButtons.forEach(btn => {
        btn.value = 'Filter';
        btn.textContent = 'Filter';
        btn.disabled = false;
    });
}

function unlockCustomElements() {
    // This is a hook to override if there are any other elements to lock that are specific to the page.
}


/**
 * This function is meant to be triggered when the filter button is clicked.
 * The used lockFilter function assumes the presence of a filter button with CSS class 'submit-filter'.
 * It locks the filter and any custom elements on the page.
 *
 * The locking process involves disabling the filter button and changing its text to 'Loading...'.
 * If there are any other elements on the page that need to be locked, they should be handled in the `lockCustomElements` function.
 *
 * In normal FilterViews, the filter process will load a new page, so there is no moment in which the elements need to
 * be unlocked again. Override this function if filter results are loaded through Ajax request and any unlocking or
 * custom behaviour is required.
 *
 * This function does not take any parameters and does not return any value.
 */
function clickedFilterButton() {
    lockFilter();
    lockCustomElements();
}