"use strict";
/**
 * Vanilla JS replacement for the old jQuery $(".modal-link").modalForm() recipe.
 *
 * Scans the DOM for links with the `modal-link` class that are not yet initialised
 * (no `bmf-bound` class) and binds the django-bootstrap-modal-forms helper
 * via the global `modalForm` function.
 *
 * The plugin itself attaches the click listener and prevents the default
 * navigation, so we only need to wire it once.
 */
function wireModalLinks() {
    document.querySelectorAll('.modal-link:not(.bmf-bound)').forEach(link => {
        link.classList.add('bmf-bound');
        // Prefer data-link attribute, fall back to href for compatibility
        const formURL = link.getAttribute('data-link') || link.getAttribute('href');
        modalForm(link, {
            formURL: formURL,
            modalID: '#modal',
            errorClass: '.is-invalid'
        });
        // Prevent the browser from following the href after the modal opens
        link.addEventListener('click', function (e) {
            e.preventDefault();
        });
    });
}

// Run once DOM is ready and also after each AJAX success that might inject new links.
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wireModalLinks);
} else {
    wireModalLinks();
}

// Expose for dynamic pages that load fragments later (optional)
window.wireModalLinks = wireModalLinks;
