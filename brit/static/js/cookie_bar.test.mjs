// Dependency-free unit tests for startCookieBar: a rate-limited (HTTP 429)
// cookie status request must not surface as an uncaught error.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("./cookie_bar.js", import.meta.url), "utf8");

function setup() {
    const scheduled = [];
    const warnings = [];
    const window = {
        setTimeout(callback, delay) { scheduled.push({ callback, delay }); },
        console: { warn(...args) { warnings.push(args); } },
    };
    vm.runInNewContext(source, { window, console: window.console, setTimeout: window.setTimeout });
    return { window, scheduled, warnings };
}

const rateLimited = () => Promise.reject(
    new SyntaxError("Unexpected token 'T', \"Too Many Requests\" is not valid JSON"),
);

test("passes options through to showCookieBar", async () => {
    const { window, warnings } = setup();
    const calls = [];
    const options = { statusUrl: "/cookies/status/" };

    await window.startCookieBar(async (opts) => { calls.push(opts); }, options);

    assert.deepEqual(calls, [options]);
    assert.equal(warnings.length, 0);
});

test("retries after the burst window, then after the minute window", async () => {
    const { window, scheduled, warnings } = setup();
    let attempts = 0;
    const show = () => { attempts += 1; return attempts < 3 ? rateLimited() : Promise.resolve(); };

    const done = window.startCookieBar(show, {});
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(attempts, 1);
    assert.ok(scheduled[0].delay > 5000, "first retry must wait past the 5 s burst window");

    scheduled[0].callback();
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(attempts, 2);
    assert.ok(scheduled[1].delay >= 60000, "second retry must wait out the minute window");

    scheduled[1].callback();
    await done;

    assert.equal(attempts, 3);
    assert.equal(scheduled.length, 2);
    assert.equal(warnings.length, 0);
});

test("gives up with a warning instead of an uncaught rejection", async () => {
    const { window, scheduled, warnings } = setup();
    let attempts = 0;
    const show = () => { attempts += 1; return rateLimited(); };

    const done = window.startCookieBar(show, {});
    for (let i = 0; i < 2; i++) {
        await new Promise((resolve) => setImmediate(resolve));
        scheduled[i].callback();
    }
    await done;

    assert.equal(attempts, 3);
    assert.equal(scheduled.length, 2);
    assert.equal(warnings.length, 1);
});
