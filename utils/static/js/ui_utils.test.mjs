import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("./ui_utils.js", import.meta.url), "utf8");

function element(tag = "div") {
    return {
        tagName: tag.toUpperCase(),
        children: [],
        listeners: {},
        attributes: {},
        className: "",
        textContent: "",
        type: "",
        removed: false,
        setAttribute(name, value) { this.attributes[name] = value; },
        addEventListener(type, cb) { this.listeners[type] = cb; },
        appendChild(child) {
            this.children.push(child);
            child.parentElement = this;
        },
        insertAdjacentElement(position, el) {
            assert.equal(position, "afterend");
            this.parentElement.appendChild(el);
        },
        querySelectorAll(selector) {
            const cls = selector.replace(/^\./, "");
            const out = [];
            const walk = (node) => node.children.forEach((c) => {
                if (c.className && c.className.split(" ").includes(cls)) out.push(c);
                walk(c);
            });
            walk(this);
            return out;
        },
        remove() {
            this.removed = true;
            if (this.parentElement) {
                this.parentElement.children = this.parentElement.children.filter((c) => c !== this);
            }
        },
    };
}

function setup({ fetchImpl, timers } = {}) {
    const scheduled = timers || [];
    const body = element("body");
    const context = vm.createContext({
        console,
        fetch: fetchImpl,
        window: {
            setTimeout: (cb, ms) => scheduled.push({ cb, ms }),
        },
        document: {
            body,
            createElement: (tag) => element(tag),
        },
    });
    vm.runInContext(source, context);
    return { ...context, scheduled, body };
}

const okJson = (data) => ({ ok: true, json: async () => data });
const flush = () => new Promise((resolve) => setImmediate(resolve));

test("fetchJson returns the parsed body for ok responses", async () => {
    const { fetchJson } = setup({ fetchImpl: async () => okJson({ a: 1 }) });
    assert.deepEqual(await fetchJson("/x/"), { a: 1 });
});

test("fetchJson throws the server-provided error message on failure", async () => {
    const { fetchJson } = setup({
        fetchImpl: async () => ({ ok: false, status: 400, json: async () => ({ error: "nope" }) }),
    });
    await assert.rejects(fetchJson("/x/"), (err) => {
        assert.equal(err.message, "nope");
        assert.equal(err.status, 400);
        assert.deepEqual(err.payload, { error: "nope" });
        return true;
    });
});

test("fetchJson reports the HTTP status when the body is not JSON", async () => {
    const { fetchJson } = setup({
        fetchImpl: async () => ({ ok: false, status: 502, json: async () => { throw new Error("bad"); } }),
    });
    await assert.rejects(fetchJson("/x/"), /status 502/);
});

test("pollTaskProgress stops on SUCCESS and reports the data", async () => {
    const timers = [];
    const calls = { active: 0, success: null };
    const { pollTaskProgress } = setup({
        timers,
        fetchImpl: async () => okJson({ state: "SUCCESS", details: { url: "/f.xlsx" } }),
    });

    pollTaskProgress("/progress/", {
        onActive: () => { calls.active += 1; },
        onSuccess: (data) => { calls.success = data; },
    });
    await flush();

    assert.equal(calls.active, 0);
    assert.equal(calls.success.details.url, "/f.xlsx");
    assert.equal(timers.length, 0);
});

test("pollTaskProgress keeps polling through PENDING and PROGRESS", async () => {
    const timers = [];
    const replies = [
        { state: "PENDING" },
        { state: "PROGRESS", details: { percent: 40 } },
        { state: "SUCCESS" },
    ];
    const calls = { active: [], failure: false, success: false };
    const { pollTaskProgress } = setup({
        timers,
        fetchImpl: async () => okJson(replies.shift()),
    });

    pollTaskProgress("/progress/", {
        onActive: (data, count) => { calls.active.push([data.state, count]); },
        onFailure: () => { calls.failure = true; },
        onSuccess: () => { calls.success = true; },
    });
    await flush();
    timers.shift().cb();
    await flush();
    timers.shift().cb();
    await flush();

    assert.deepEqual(calls.active, [["PENDING", 1], ["PROGRESS", 2]]);
    assert.equal(calls.failure, false);
    assert.equal(calls.success, true);
});

test("pollTaskProgress uses the delay returned by onActive", async () => {
    const timers = [];
    const replies = [{ state: "PENDING" }, { state: "SUCCESS" }];
    const { pollTaskProgress } = setup({
        timers,
        fetchImpl: async () => okJson(replies.shift()),
    });

    pollTaskProgress("/progress/", { intervalMs: 500, onActive: () => 1200 });
    await flush();

    assert.equal(timers[0].ms, 1200);
});

test("pollTaskProgress routes fetch errors to onError and stops", async () => {
    const timers = [];
    const calls = { error: null, success: false };
    const { pollTaskProgress } = setup({
        timers,
        fetchImpl: async () => { throw new Error("network down"); },
    });

    pollTaskProgress("/progress/", {
        onSuccess: () => { calls.success = true; },
        onError: (err) => { calls.error = err; },
    });
    await flush();

    assert.equal(calls.error.message, "network down");
    assert.equal(calls.success, false);
    assert.equal(timers.length, 0);
});

test("pollTaskProgress treats an empty body as an error", async () => {
    const calls = { error: null };
    const { pollTaskProgress } = setup({
        fetchImpl: async () => okJson(null),
    });

    pollTaskProgress("/progress/", { onError: (err) => { calls.error = err; } });
    await flush();

    assert.match(calls.error.message, /Empty response/);
});

test("showInlineAlert inserts a dismissible alert after the anchor", () => {
    const { showInlineAlert, body } = setup();
    const anchor = element("button");
    body.appendChild(anchor);

    showInlineAlert(anchor, "Export failed");

    const alertEl = body.children.find((c) => c.className.includes("ui-utils-inline-alert"));
    assert.ok(alertEl);
    assert.equal(alertEl.attributes.role, "alert");
    assert.equal(alertEl.children[0].textContent, "Export failed");
    const [dismiss] = alertEl.children.filter((c) => c.tagName === "BUTTON");
    assert.ok(dismiss);
    dismiss.listeners.click();
    assert.ok(alertEl.removed);
});

test("showInlineAlert replaces a previous alert anchored to the same parent", () => {
    const { showInlineAlert, body } = setup();
    const anchor = element("button");
    body.appendChild(anchor);

    showInlineAlert(anchor, "first");
    showInlineAlert(anchor, "second");

    const alerts = body.querySelectorAll(".ui-utils-inline-alert");
    assert.equal(alerts.length, 1);
    assert.equal(alerts[0].children[0].textContent, "second");
});
