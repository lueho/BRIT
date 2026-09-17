import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("./filter_utils.js", import.meta.url), "utf8");

function control(extra = {}) {
    return {
        name: "", disabled: false, tagName: "INPUT", type: "text", value: "",
        checked: false, multiple: false, selectedOptions: [],
        ...extra,
    };
}

function filterForm(elements = [], extra = {}) {
    return {
        method: "get", elements, listeners: {}, attributes: {},
        addEventListener(type, cb) { this.listeners[type] = cb; },
        getAttribute(name) { return this.attributes[name] || null; },
        ...extra,
    };
}

function setup(forms = []) {
    const submitButton = { form: forms.length ? forms[forms.length - 1] : null, closest: () => forms[forms.length - 1] || null };
    const document = {
        listeners: {},
        querySelector(selector) {
            if (selector === ".submit-filter") { return submitButton; }
            if (selector === "form") { return forms[0] || null; }
            return null;
        },
        querySelectorAll(selector) {
            if (selector === ".submit-filter") { return forms.length ? [submitButton] : []; }
            return [];
        },
        addEventListener(type, cb) { this.listeners[type] = cb; },
    };
    const window = { location: { pathname: "/processes/list/", href: "" } };
    const sandbox = { document, window, console, URLSearchParams };
    vm.runInNewContext(source, sandbox);
    return { sandbox, document, window, submitButton };
}

function submitEvent() {
    return { prevented: false, preventDefault() { this.prevented = true; } };
}

test("parseFilterParameters omits csrf tokens and empty controls", () => {
    const form = filterForm([
        control({ name: "csrfmiddlewaretoken", type: "hidden", value: "secret-token" }),
        control({ name: "scope", type: "hidden", value: "published" }),
        control({ name: "name", value: "compost" }),
        control({ name: "mechanism", value: "" }),
        control({ name: "publication_status", type: "hidden", value: "" }),
        control({ name: "page", type: "hidden", value: "3" }),
        control({ name: "filter", tagName: "BUTTON", type: "submit", value: "Filter" }),
    ]);
    const { sandbox } = setup([form]);
    const params = sandbox.parseFilterParameters();
    assert.equal(params.get("csrfmiddlewaretoken"), null);
    assert.equal(params.get("page"), null);
    assert.equal(params.get("mechanism"), null);
    assert.equal(params.get("publication_status"), null);
    assert.equal(params.get("filter"), null);
    assert.equal(params.get("scope"), "published");
    assert.equal(params.get("name"), "compost");
});

test("parseFilterParameters drops the unset NullBooleanSelect sentinel", () => {
    const form = filterForm([
        control({ name: "has_parent", tagName: "SELECT", type: "select-one", value: "unknown" }),
        control({ name: "active", tagName: "SELECT", type: "select-one", value: "true" }),
    ]);
    const { sandbox } = setup([form]);
    const params = sandbox.parseFilterParameters();
    assert.equal(params.get("has_parent"), null);
    assert.equal(params.get("active"), "true");
});

test("parseFilterParameters keeps checked and multi-select values", () => {
    const multiSelect = control({
        name: "categories", tagName: "SELECT", type: "select-multiple", multiple: true,
        selectedOptions: [{ value: "1" }, { value: "4" }],
    });
    const form = filterForm([
        multiSelect,
        control({ name: "featured", type: "checkbox", value: "on", checked: true }),
        control({ name: "archived", type: "checkbox", value: "on", checked: false }),
    ]);
    const { sandbox } = setup([form]);
    const params = sandbox.parseFilterParameters();
    assert.deepEqual(params.getAll("categories"), ["1", "4"]);
    assert.equal(params.get("featured"), "on");
    assert.equal(params.get("archived"), null);
});

test("parseFilterParameters uses the filter form instead of the first form", () => {
    const postForm = filterForm([
        control({ name: "csrfmiddlewaretoken", type: "hidden", value: "post-token" }),
    ], { method: "post" });
    const getForm = filterForm([control({ name: "name", value: "compost" })]);
    const { sandbox } = setup([postForm, getForm]);
    const params = sandbox.parseFilterParameters();
    assert.equal(params.get("name"), "compost");
    assert.equal(params.get("csrfmiddlewaretoken"), null);
});

test("submitting a GET filter form navigates to a clean URL", () => {
    const form = filterForm([
        control({ name: "csrfmiddlewaretoken", type: "hidden", value: "secret" }),
        control({ name: "mechanism", value: "" }),
        control({ name: "has_parent", tagName: "SELECT", type: "select-one", value: "unknown" }),
        control({ name: "scope", type: "hidden", value: "published" }),
        control({ name: "name", value: "compost" }),
    ]);
    const { document, window } = setup([form]);
    document.listeners.DOMContentLoaded();
    const event = submitEvent();
    form.listeners.submit(event);
    assert.equal(event.prevented, true);
    assert.equal(window.location.href, "/processes/list/?scope=published&name=compost");
});

test("the submit cleanup never touches POST forms", () => {
    const form = filterForm(
        [control({ name: "csrfmiddlewaretoken", type: "hidden", value: "secret" })],
        { method: "post" },
    );
    const { document } = setup([form]);
    document.listeners.DOMContentLoaded();
    assert.equal(form.listeners.submit, undefined);
});

test("parseFilterParameters warns and returns empty params without a form", () => {
    const warnings = [];
    const document = {
        listeners: {},
        querySelector: () => null,
        querySelectorAll: () => [],
        addEventListener(type, cb) { this.listeners[type] = cb; },
    };
    const sandbox = {
        document,
        window: { location: { pathname: "/", href: "" } },
        console: { warn: (msg) => warnings.push(msg) },
        URLSearchParams,
    };
    vm.runInNewContext(source, sandbox);
    const params = sandbox.parseFilterParameters();
    assert.equal(params.toString(), "");
    assert.equal(warnings.length, 1);
});
