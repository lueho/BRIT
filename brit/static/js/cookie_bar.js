"use strict";

// The cookie status request counts towards the anonymous rate limit. A 429
// answer is plain text, so the cookie-consent module fails parsing it as JSON.
// Retry after the 5 s burst window, then after the 60 s minute window, instead
// of leaving an uncaught rejection.
const COOKIE_BAR_RETRY_DELAYS_MS = [6000, 61000];

function startCookieBar(showCookieBar, options) {
    let retries = 0;
    const attempt = () => Promise.resolve()
        .then(() => showCookieBar(options))
        .catch((error) => {
            if (retries < COOKIE_BAR_RETRY_DELAYS_MS.length) {
                const delay = COOKIE_BAR_RETRY_DELAYS_MS[retries];
                retries += 1;
                return new Promise((resolve) => {
                    window.setTimeout(() => resolve(attempt()), delay);
                });
            }
            console.warn("Cookie consent status could not be loaded.", error);
            return undefined;
        });
    return attempt();
}

window.startCookieBar = startCookieBar;
