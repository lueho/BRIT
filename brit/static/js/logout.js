"use strict";

document.addEventListener("DOMContentLoaded", function () {
    const logoutLink = document.getElementById('logoutLink');

    if (logoutLink) {
        logoutLink.addEventListener('click', function (event) {
            event.preventDefault(); // Prevent the default link behavior

            // Make an AJAX POST request to log the user out
            fetch("{% url 'auth_logout' %}", {
                method: "POST",
                headers: {
                    'X-CSRFToken': '{{ csrf_token }}',
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