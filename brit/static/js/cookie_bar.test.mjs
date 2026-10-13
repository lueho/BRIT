// Dependency-free unit tests for startCookieBar: a rate-limited (HTTP 429)
// cookie status request is retried after Retry-After; other failures are not.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("./cookie_bar.js", import.meta.url), "utf8");
const STATUS_URL = "/cookies/status/";

function response(status, headers = {}) {
    return {
        ok: status >= 200 && status < 300,
        status,
        headers: { get: (name) => headers[name] ?? null },
        json: async () => {
            if (status !== 200) throw new SyntaxError("Unexpected token 'T'");
            return { notAcceptedOrDeclinedCookieGroups: [] };
        },
    };
}

function setup(responses) {
    const scheduled = [];
    const warnings = [];
    const errors = [];
    const fetched = [];
    const console = {
        warn(...args) { warnings.push(args); },
        error(...args) { errors.push(args); },
    };
    const window = {
        setTimeout(callback, delay) { scheduled.push({ callback, delay }); },
        async fetch(url) {
            fetched.push(url);
            const next = responses.shift();
            if (next instanceof Error) throw next;
            return next;
        },
    };
    vm.runInNewContext(source, { window, console });
    return { window, scheduled, warnings, errors, fetched };
}

// Mirrors cookiebar.module.js: fetch the status URL, then parse it as JSON.
function makeShowCookieBar(window) {
    const calls = [];
    const show = async (options) => {
        calls.push(options);
        const statusResponse = await window.fetch(options.statusUrl, { method: "GET" });
        await statusResponse.json();
    };
    return { show, calls };
}

const tick = () => new Promise((resolve) => setImmediate(resolve));

test("passes options through to showCookieBar", async () => {
    const { window, warnings, errors } = setup([response(200)]);
    const { show, calls } = makeShowCookieBar(window);
    const options = { statusUrl: STATUS_URL };

    await window.startCookieBar(show, options);

    assert.deepEqual(calls, [options]);
    assert.equal(warnings.length + errors.length, 0);
});

test("retries 429 responses after their Retry-After window", async () => {
    const { window, scheduled, warnings, errors } = setup([
        response(429, { "Retry-After": "5" }),
        response(429, { "Retry-After": "60" }),
        response(200),
    ]);
    const { show, calls } = makeShowCookieBar(window);

    const done = window.startCookieBar(show, { statusUrl: STATUS_URL });
    await tick();
    assert.equal(calls.length, 1);
    assert.equal(scheduled[0].delay, 6000);

    scheduled[0].callback();
    await tick();
    assert.equal(calls.length, 2);
    assert.equal(scheduled[1].delay, 61000);

    scheduled[1].callback();
    await done;

    assert.equal(calls.length, 3);
    assert.equal(scheduled.length, 2);
    assert.equal(warnings.length + errors.length, 0);
});

test("gives up on persistent 429 with a warning instead of an uncaught rejection", async () => {
    const { window, scheduled, warnings, errors } = setup([
        response(429, { "Retry-After": "60" }),
        response(429, { "Retry-After": "60" }),
        response(429, { "Retry-After": "60" }),
    ]);
    const { show, calls } = makeShowCookieBar(window);

    const done = window.startCookieBar(show, { statusUrl: STATUS_URL });
    for (let i = 0; i < 2; i++) {
        await tick();
        scheduled[i].callback();
    }
    await done;

    assert.equal(calls.length, 3);
    assert.equal(scheduled.length, 2);
    assert.equal(warnings.length, 1);
    assert.equal(errors.length, 0);
});

test("does not retry server errors", async () => {
    const { window, scheduled, errors } = setup([response(500)]);
    const { show, calls } = makeShowCookieBar(window);

    await window.startCookieBar(show, { statusUrl: STATUS_URL });

    assert.equal(calls.length, 1);
    assert.equal(scheduled.length, 0);
    assert.equal(errors.length, 1);
});

test("does not retry network failures", async () => {
    const { window, scheduled, errors } = setup([new TypeError("Failed to fetch")]);
    const { show, calls } = makeShowCookieBar(window);

    await window.startCookieBar(show, { statusUrl: STATUS_URL });

    assert.equal(calls.length, 1);
    assert.equal(scheduled.length, 0);
    assert.equal(errors.length, 1);
});

test("does not retry setup failures", async () => {
    const { window, scheduled, errors } = setup([]);
    const show = async () => { throw new Error("No cookie groups (script) tag found"); };

    await window.startCookieBar(show, { statusUrl: STATUS_URL });

    assert.equal(scheduled.length, 0);
    assert.equal(errors.length, 1);
});

test("leaves other fetches untouched", async () => {
    const { window } = setup([response(429)]);
    window.startCookieBar(async () => {}, { statusUrl: STATUS_URL });

    const other = await window.fetch("/cookies/accept/");

    assert.equal(other.status, 429);
});
