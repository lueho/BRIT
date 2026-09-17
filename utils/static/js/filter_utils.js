"use strict";

// Parameters that must never leak into shareable filter URLs.
const NON_FILTER_PARAMETERS = new Set(['csrfmiddlewaretoken', 'page']);

function findFilterForm() {
    const submitButton = document.querySelector('.submit-filter');
    if (submitButton) {
        return submitButton.form || submitButton.closest('form');
    }
    return document.querySelector('form');
}

function isUnsetSelect(element) {
    // Django's NullBooleanSelect uses 'unknown' as the value of its unset default option.
    return element.tagName === 'SELECT' && !element.multiple && element.value === 'unknown';
}

function isNonFilterControl(element) {
    return NON_FILTER_PARAMETERS.has(element.name) || element.value === '' || isUnsetSelect(element);
}

function filterControlEntries(form) {
    const entries = [];
    for (const element of form.elements) {
        if (!element.name || element.disabled) {
            continue;
        }
        if (element.type === 'submit' || element.type === 'button' || element.type === 'reset') {
            continue;
        }
        if (element.tagName === 'SELECT' && element.multiple) {
            for (const option of element.selectedOptions) {
                if (option.value !== '') {
                    entries.push([element.name, option.value]);
                }
            }
            continue;
        }
        if (element.type === 'checkbox' || element.type === 'radio') {
            if (element.checked) {
                entries.push([element.name, element.value]);
            }
            continue;
        }
        if (isNonFilterControl(element)) {
            continue;
        }
        entries.push([element.name, element.value]);
    }
    return entries;
}

function parseFilterParameters() {
    const form = findFilterForm();
    if (!form) {
        console.warn('No form found on the page. Returning an empty URLSearchParams object.');
        return new URLSearchParams();
    }
    return new URLSearchParams(filterControlEntries(form));
}

function initFilterFormCleanup() {
    document.querySelectorAll('.submit-filter').forEach(button => {
        const form = button.form || button.closest('form');
        if (form && form.method === 'get') {
            form.addEventListener('submit', event => {
                event.preventDefault();
                const query = new URLSearchParams(filterControlEntries(form)).toString();
                const action = form.getAttribute('action') || window.location.pathname;
                window.location.href = query ? `${action}?${query}` : action;
            });
        }
    });
}

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