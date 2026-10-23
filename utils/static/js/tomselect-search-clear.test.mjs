import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("./tomselect-search-clear.js", import.meta.url), "utf8");

function selectElement({ multiple = true, tomselect = null, tomselected = true } = {}) {
    const classes = new Set(tomselected ? ["tomselected"] : []);
    return {
        multiple,
        tomselect,
        dataset: {},
        classList: {
            contains(name) { return classes.has(name); },
            add(name) { classes.add(name); },
        },
        matches(selector) {
            return selector === "select.tomselected" && classes.has("tomselected");
        },
        querySelectorAll() { return []; },
    };
}

function tomselectInstance() {
    return {
        handlers: {},
        onCalls: 0,
        cleared: undefined,
        on(event, fn) { this.onCalls += 1; this.handlers[event] = fn; },
        setTextboxValue(value) { this.cleared = value; },
    };
}

function setup({ readyState = "loading", existing = [] } = {}) {
    const registered = {};
    const observer = { callback: null, observed: null };
    class MutationObserverMock {
        constructor(callback) { observer.callback = callback; }
        observe(target, options) { observer.observed = { target, options }; }
        disconnect() {}
    }
    const documentElement = {
        matches() { return false; },
        querySelectorAll(selector) {
            return existing.filter((el) => el.matches(selector));
        },
    };
    const document = {
        readyState,
        documentElement,
        addEventListener(type, fn) { (registered[type] ??= []).push(fn); },
    };
    const sandbox = { document, MutationObserver: MutationObserverMock, console };
    vm.runInNewContext(source, sandbox);
    const init = () => (registered.DOMContentLoaded || []).forEach((fn) => fn());
    return { sandbox, registered, observer, documentElement, init };
}

test("multi-select TomSelect clears the search textbox after an item is added", () => {
    const instance = tomselectInstance();
    const select = selectElement({ multiple: true, tomselect: instance });
    const { init } = setup({ existing: [select] });
    init();
    assert.equal(typeof instance.handlers.item_add, "function");
    instance.handlers.item_add();
    assert.equal(instance.cleared, "");
});

test("single selects are not wired", () => {
    const instance = tomselectInstance();
    const select = selectElement({ multiple: false, tomselect: instance });
    const { init } = setup({ existing: [select] });
    init();
    assert.equal(instance.handlers.item_add, undefined);
});

test("elements without a TomSelect instance are not wired", () => {
    const select = selectElement({ multiple: true, tomselect: null });
    const { init } = setup({ existing: [select] });
    init();
    assert.notEqual(select.dataset.searchClearWired, "true");
});

test("non-tomselected selects are not wired", () => {
    const instance = tomselectInstance();
    const select = selectElement({ multiple: true, tomselect: instance, tomselected: false });
    const { init } = setup({ existing: [select] });
    init();
    assert.equal(instance.handlers.item_add, undefined);
});

test("an instance is wired only once", () => {
    const instance = tomselectInstance();
    const select = selectElement({ multiple: true, tomselect: instance });
    const { init, observer } = setup({ existing: [select] });
    init();
    assert.equal(instance.onCalls, 1);
    observer.callback([{ type: "attributes", target: select }]);
    assert.equal(instance.onCalls, 1);
});

test("dynamically enhanced selects are wired through the observer", () => {
    const { init, observer } = setup();
    init();
    const instance = tomselectInstance();
    const select = selectElement({ multiple: true, tomselect: instance });
    observer.callback([{ type: "attributes", target: select }]);
    assert.equal(typeof instance.handlers.item_add, "function");
});

test("selects injected later are wired through childList mutations", () => {
    const { init, observer } = setup();
    init();
    const instance = tomselectInstance();
    const select = selectElement({ multiple: true, tomselect: instance });
    const wrapper = {
        matches() { return false; },
        querySelectorAll(selector) { return select.matches(selector) ? [select] : []; },
    };
    observer.callback([{ type: "childList", addedNodes: [wrapper] }]);
    assert.equal(typeof instance.handlers.item_add, "function");
});

test("init runs immediately when the document is already parsed", () => {
    const instance = tomselectInstance();
    const select = selectElement({ multiple: true, tomselect: instance });
    const { observer } = setup({ readyState: "complete", existing: [select] });
    assert.equal(typeof instance.handlers.item_add, "function");
    assert.notEqual(observer.observed, null);
});
