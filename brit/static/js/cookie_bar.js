"use strict";

// The cookie status request counts towards the anonymous rate limit. A 429
// answer is plain text, so the cookie-consent module fails parsing it as JSON;
// retry once after the burst window instead of leaving an uncaught rejection.
const COOKIE_BAR_RETRY_DELAY_MS = 6000;

function startCookieBar(showCookieBar, options) {
    let attempts = 0;
    const attempt = () => {
        attempts += 1;
        return Promise.resolve()
            .then(() => showCookieBar(options))
            .catch((error) => {
                if (attempts < 2) {
                    return new Promise((resolve) => {
                        window.setTimeout(() => resolve(attempt()), COOKIE_BAR_RETRY_DELAY_MS);
                    });
                }
                console.warn("Cookie consent status could not be loaded.", error);
                return undefined;
            });
    };
    return attempt();
}

window.startCookieBar = startCookieBar;
