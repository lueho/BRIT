"use strict";

document.addEventListener("DOMContentLoaded", function () {
    const logoutLink = document.getElementById('logoutLink');

    if (logoutLink) {
        logoutLink.addEventListener('click', function (event) {
            event.preventDefault();

            const url = logoutLink.dataset.logoutUrl;
            const csrfToken = logoutLink.dataset.csrfToken || logoutLink.dataset.csrfToken;
            fetch(url, {
                method: "POST",
                headers: {
                    'X-CSRFToken': csrfToken,
                }
            }).then(response => {
                if (response.ok) {
                    // Reload the current page if the logout was successful
                    window.location.reload();
                } else {
                    // If the reload might result in a 403, redirect to the start page
                    window.location.href = "/";
                }
            }).catch(() => {
                // Handle network or other errors
                window.location.href = "/";
            });
        });
    }
});