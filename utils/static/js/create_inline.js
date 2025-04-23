"use strict";

(function($) {

    /**
     * Retrieves the URL for asynchronous data fetching after modal success.
     * Prefers 'data-async-url' attribute, falls back to 'data-url'.
     *
     * @param {jQuery} $element - The jQuery element (usually the button) containing data attributes.
     * @returns {string|undefined} The data URL or undefined if none is found.
     */
    function getAsyncDataUrl($element) {
        // Prioritize a specific attribute for clarity, e.g., 'data-async-url'
        let url = $element.data('async-url');
        if (url) {
            return url;
        }

        // Fallback: Check 'data-url' (common convention)
        url = $element.data('url');
        if (url) {
            return url;
        }

        // No suitable URL attribute found
        console.warn("No async data URL found ('data-async-url', 'data-url'). Async update might fail.", $element[0]);
        return undefined;
    }

    /**
     * Initializes modal form functionality for designated create buttons.
     * Looks for elements with '.modal-fk-create' class that haven't been initialized yet.
     */
    function wireCreateButtons() {
        $('.modal-fk-create').not('.bmf-bound').each(function() {
            const $btn = $(this); // Cache the jQuery object for the button

            // --- Configuration Retrieval ---
            const formUrl = $btn.data('href'); // URL for the initial modal form content
            const selectTargetSelector = $btn.data('select'); // Selector for the related <select> element
            const modalTargetId = $btn.data('modal-target') || '#modal'; // Allow overriding default modal ID
            const asyncDataUrl = getAsyncDataUrl($btn); // URL for fetching data after success
            const targetElementId = $btn.data('for-field'); // ID/Selector of element to update

            // --- Validation ---
            if (!formUrl) {
                console.warn('wireCreateButtons: Button missing required "data-href" attribute. Skipping.', $btn[0]);
                return;
            }
            if (!selectTargetSelector) {
                console.warn('wireCreateButtons: Button missing required "data-select" attribute. Skipping.', $btn[0]);
                return;
            }

            const $select = $(selectTargetSelector);
            if (!$select.length) {
                console.warn(`wireCreateButtons: Target select element "${selectTargetSelector}" not found for button. Skipping.`, $btn[0]);
                return;
            }

            // Mark the button as processed to prevent re-binding
            $btn.addClass('bmf-bound');

            // --- Initialize Modal Plugin ---
            $btn.modalForm({
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

    $(document).ready(wireCreateButtons);

}(jQuery));