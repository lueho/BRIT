"use strict";

window.addEventListener('DOMContentLoaded', event => {

    // Toggle the side navigation
    const sidebarToggle = document.body.querySelector('#sidebarToggle');
    if (sidebarToggle) {
        // Restore the persisted sidebar state. Use add/remove (not toggle) so a
        // page that pre-sets `sb-sidenav-toggled` (e.g. Waste Atlas) is not
        // accidentally inverted for users who previously collapsed the sidebar.
        const stored = localStorage.getItem('sb|sidebar-toggle');
        if (stored === 'true') {
            document.body.classList.add('sb-sidenav-toggled');
        } else if (stored === 'false') {
            document.body.classList.remove('sb-sidenav-toggled');
        }
        sidebarToggle.addEventListener('click', event => {
            event.preventDefault();
            document.body.classList.toggle('sb-sidenav-toggled');
            localStorage.setItem('sb|sidebar-toggle', document.body.classList.contains('sb-sidenav-toggled'));
        });
    }
});
