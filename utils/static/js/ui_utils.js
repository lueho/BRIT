"use strict";

/*
 * Shared UI helpers: fetch error handling, Celery-style task polling and
 * non-blocking user feedback. Loaded via the base templates and widget media
 * so plain script bundles can rely on these globals.
 */

/**
 * Fetches a URL and parses the response body as JSON.
 *
 * Rejects with an Error carrying the server-provided message (`error` or
 * `detail` field) when the response is not ok. A non-JSON body resolves to
 * `null` data instead of masking the HTTP status; the thrown error exposes
 * `status` and `payload` for callers that need them.
 *
 * @param {string} url - The request URL.
 * @param {object} [options] - Options passed through to fetch().
 * @returns {Promise<object|null>} The parsed JSON body.
 */
async function fetchJson(url, options) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => null);
    if (!response.ok) {
        const detail = data && (data.error || data.detail);
        const error = new Error(detail || `Request failed with status ${response.status}`);
        error.status = response.status;
        error.payload = data;
        throw error;
    }
    return data;
}

/**
 * Polls a Celery task progress endpoint until it reaches a terminal state.
 *
 * PENDING, STARTED, PROGRESS and unknown states keep polling via `onActive`;
 * SUCCESS and FAILURE end polling via `onSuccess`/`onFailure`. Fetch or
 * response errors go to `onError`.
 *
 * @param {string} url - The progress endpoint URL.
 * @param {object} [handlers]
 * @param {object} [handlers.fetchOptions] - Options passed to fetch().
 * @param {number} [handlers.intervalMs=500] - Default delay between polls.
 * @param {function} [handlers.onActive] - Called with (data, pollCount) for
 *     non-terminal states; may return a custom delay in milliseconds.
 * @param {function} [handlers.onSuccess] - Called with the final response data.
 * @param {function} [handlers.onFailure] - Called with the final response data.
 * @param {function} [handlers.onError] - Called with the fetch/parse error.
 */
function pollTaskProgress(url, handlers = {}) {
    const {
        fetchOptions,
        intervalMs = 500,
        onActive,
        onSuccess,
        onFailure,
        onError,
    } = handlers;

    let pollCount = 0;

    async function tick() {
        pollCount += 1;
        try {
            const data = await fetchJson(url, fetchOptions);
            if (!data) {
                throw new Error("Empty response while polling task progress.");
            }
            if (data.state === "SUCCESS") {
                if (onSuccess) onSuccess(data);
                return;
            }
            if (data.state === "FAILURE") {
                if (onFailure) onFailure(data);
                return;
            }
            let delay = intervalMs;
            if (onActive) {
                const customDelay = onActive(data, pollCount);
                if (typeof customDelay === "number" && customDelay >= 0) {
                    delay = customDelay;
                }
            }
            window.setTimeout(tick, delay);
        } catch (error) {
            if (onError) {
                onError(error);
            } else {
                console.error("Task polling failed:", error);
            }
        }
    }

    tick();
}

/**
 * Shows a dismissible, non-blocking Bootstrap alert next to an element.
 * Replaces blocking window.alert() calls; a previous alert anchored to the
 * same parent is removed first to avoid stacking.
 *
 * @param {HTMLElement} anchor - Element after which the alert is inserted.
 * @param {string} message - The message to display.
 * @param {object} [options]
 * @param {string} [options.context="danger"] - Bootstrap alert context.
 * @param {number} [options.dismissAfterMs=8000] - Auto-dismiss delay; 0 keeps it.
 */
function showInlineAlert(anchor, message, options = {}) {
    if (!anchor) {
        console.error(message);
        return;
    }
    const { context = "danger", dismissAfterMs = 8000 } = options;
    const parent = anchor.parentElement || document.body;

    parent.querySelectorAll(".ui-utils-inline-alert").forEach(el => el.remove());

    const alert = document.createElement("div");
    alert.className = `alert alert-${context} alert-dismissible ui-utils-inline-alert mt-2`;
    alert.setAttribute("role", "alert");

    const text = document.createElement("span");
    text.textContent = message;

    const dismiss = document.createElement("button");
    dismiss.type = "button";
    dismiss.className = "btn-close";
    dismiss.setAttribute("aria-label", "Dismiss");
    dismiss.addEventListener("click", () => alert.remove());

    alert.appendChild(text);
    alert.appendChild(dismiss);
    anchor.insertAdjacentElement("afterend", alert);

    if (dismissAfterMs > 0) {
        window.setTimeout(() => alert.remove(), dismissAfterMs);
    }
}
