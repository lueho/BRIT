"use strict";

// The cookie status request counts towards the anonymous rate limit, and
// cookiebar.module.js parses every status response as JSON without checking
// the HTTP status. Fail status responses early with their status code so only
// rate-limited (429) loads are retried, after the Retry-After window.
const COOKIE_BAR_MAX_RETRIES = 2;
const COOKIE_BAR_DEFAULT_RETRY_AFTER_SECONDS = 5;
const COOKIE_BAR_RETRY_MARGIN_MS = 1000;

class CookieStatusError extends Error {
    constructor(status, retryAfterSeconds) {
        super(`Cookie consent status request failed with HTTP ${status}.`);
        this.name = "CookieStatusError";
        this.status = status;
        this.retryAfterSeconds = retryAfterSeconds;
    }
}

function parseRetryAfter(value) {
    const seconds = Number.parseInt(value, 10);
    return Number.isFinite(seconds) && seconds >= 0
        ? seconds
        : COOKIE_BAR_DEFAULT_RETRY_AFTER_SECONDS;
}

function guardCookieStatusFetch(statusUrl) {
    const originalFetch = window.fetch;
    window.fetch = async (input, init) => {
        const response = await originalFetch(input, init);
        if (input === statusUrl && !response.ok) {
            throw new CookieStatusError(
                response.status,
                parseRetryAfter(response.headers.get("Retry-After")),
            );
        }
        return response;
    };
}

function startCookieBar(showCookieBar, options) {
    guardCookieStatusFetch(options.statusUrl);
    let retries = 0;
    const attempt = () => Promise.resolve()
        .then(() => showCookieBar(options))
        .catch((error) => {
            const rateLimited = error instanceof CookieStatusError && error.status === 429;
            if (rateLimited && retries < COOKIE_BAR_MAX_RETRIES) {
                retries += 1;
                const delay = error.retryAfterSeconds * 1000 + COOKIE_BAR_RETRY_MARGIN_MS;
                return new Promise((resolve) => {
                    window.setTimeout(() => resolve(attempt()), delay);
                });
            }
            if (rateLimited) {
                console.warn("Cookie consent status could not be loaded.", error);
            } else {
                console.error("Cookie consent bar could not be shown.", error);
            }
            return undefined;
        });
    return attempt();
}

window.startCookieBar = startCookieBar;
