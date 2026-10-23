import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const uiUtilsSource = readFileSync(
    new URL("../../../utils/static/js/ui_utils.js", import.meta.url),
    "utf8"
);
const sdv2Source = readFileSync(new URL("./sample_detail_v2.js", import.meta.url), "utf8");

function element(tag = "div", className = "") {
    return {
        tagName: tag.toUpperCase(),
        className,
        children: [],
        listeners: {},
        attributes: {},
        dataset: {},
        textContent: "",
        innerHTML: "",
        disabled: false,
        hidden: false,
        setAttribute(name, value) { this.attributes[name] = value; },
        removeAttribute(name) { delete this.attributes[name]; },
        addEventListener(type, cb) { this.listeners[type] = cb; },
        appendChild(child) {
            this.children.push(child);
            child.parentElement = this;
        },
        insertAdjacentElement(position, el) {
            assert.equal(position, "afterend");
            this.parentElement.appendChild(el);
        },
        closest(selector) {
            const cls = selector.replace(/^\./, "");
            let node = this;
            while (node) {
                if (node.className && node.className.split(" ").includes(cls)) return node;
                node = node.parentElement;
            }
            return null;
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

function isInside(ancestor, node) {
    let current = node;
    while (current) {
        if (current === ancestor) return true;
        current = current.parentElement;
    }
    return false;
}

function setup(replies) {
    const root = element("div", "sdv2");
    const actionsRow = element("div", "sdv2-rail-actions");
    const actionsMenu = element("div", "dropdown sdv2-actions-menu");
    const menu = element("ul", "dropdown-menu");
    const item = element("li");
    const trigger = element("button", "dropdown-item");
    trigger.dataset.exportUrl = "/samples/1/export/";
    trigger.dataset.progressTemplate = "/export/progress/TASK_ID/";

    root.appendChild(actionsRow);
    actionsRow.appendChild(actionsMenu);
    actionsMenu.appendChild(menu);
    menu.appendChild(item);
    item.appendChild(trigger);

    const scheduled = [];
    const document = {
        listeners: {},
        head: element("head"),
        body: element("body"),
        querySelector: (sel) => (sel === ".sdv2" ? root : null),
        querySelectorAll: (sel) => {
            if (sel === "[data-sdv2-export-sample]") return [trigger];
            return [];
        },
        getElementById: () => null,
        createElement: (tag) => element(tag),
        addEventListener(type, cb) { this.listeners[type] = cb; },
    };

    const context = vm.createContext({
        console,
        document,
        navigator: {},
        fetch: async () => ({
            ok: true,
            json: async () => replies.shift(),
        }),
        setTimeout: (cb, ms) => scheduled.push({ cb, ms }),
        window: {
            setTimeout: (cb, ms) => scheduled.push({ cb, ms }),
            location: { href: "http://test/sample/1/" },
        },
    });
    vm.runInContext(uiUtilsSource, context);
    vm.runInContext(sdv2Source, context);
    return { trigger, menu, actionsRow, scheduled };
}

const flush = async (times = 10) => {
    for (let i = 0; i < times; i += 1) {
        await new Promise((resolve) => setImmediate(resolve));
    }
};

test("task failure renders the error outside the closed actions dropdown", async () => {
    const { trigger, menu, actionsRow } = setup([
        { task_id: "abc" },
        { state: "FAILURE", details: { error: "Server exploded" } },
    ]);

    // Bootstrap closes the dropdown once the export item is clicked.
    trigger.listeners.click({ preventDefault() {} });
    menu.hidden = true;
    await flush();

    const alerts = actionsRow.querySelectorAll(".ui-utils-inline-alert");
    assert.equal(alerts.length, 1);
    assert.equal(alerts[0].children[0].textContent, "Server exploded");
    assert.equal(isInside(menu, alerts[0]), false);
    assert.equal(trigger.disabled, false);
});

test("export start failure renders the error outside the closed actions dropdown", async () => {
    const { trigger, menu, actionsRow } = setup([
        { state: "not-a-task-response" },
    ]);

    trigger.listeners.click({ preventDefault() {} });
    menu.hidden = true;
    await flush();

    const alerts = actionsRow.querySelectorAll(".ui-utils-inline-alert");
    assert.equal(alerts.length, 1);
    assert.equal(
        alerts[0].children[0].textContent,
        "Failed to start export. See console for details."
    );
    assert.equal(isInside(menu, alerts[0]), false);
    assert.equal(trigger.disabled, false);
});
