import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("./tomselect-required-feedback.js", import.meta.url), "utf8");

function classList(initial = []) {
    const classes = new Set(initial);
    return {
        contains(name) { return classes.has(name); },
        add(...names) { names.forEach((name) => classes.add(name)); },
        remove(name) { classes.delete(name); },
    };
}

function element(className = "") {
    return {
        className,
        classList: classList(className.split(" ").filter(Boolean)),
        attributes: {},
        textContent: "",
        previousElementSibling: null,
        removed: false,
        scrolled: 0,
        setAttribute(name, value) { this.attributes[name] = value; },
        removeAttribute(name) { delete this.attributes[name]; },
        insertAdjacentElement(position, node) {
            assert.equal(position, "beforebegin");
            node.next = this;
            this.previousElementSibling = node;
        },
        remove() {
            this.removed = true;
            if (this.next) this.next.previousElementSibling = null;
        },
        scrollIntoView() { this.scrolled += 1; },
    };
}

function field({ tomselect = true, valid = false, message = "Please select an item in the list." } = {}) {
    const el = {
        ...element(),
        classList: classList(tomselect ? ["tomselected"] : []),
        dataset: {},
        willValidate: true,
        validity: { valid },
        validationMessage: message,
        form: null,
    };
    if (tomselect) {
        el.tomselect = {
            wrapper: element("ts-wrapper"),
            control_input: element(),
            focused: 0,
            focus() { this.focused += 1; },
        };
    }
    return el;
}

function setup() {
    const listeners = {};
    const timers = [];
    const document = {
        addEventListener(type, fn, capture) { listeners[type] = { fn, capture }; },
        createElement: () => element(),
    };
    const sandbox = { document, setTimeout: (fn) => timers.push(fn) };
    vm.runInNewContext(source, sandbox);
    const dispatch = (type, target) => {
        const event = { target, prevented: false, preventDefault() { this.prevented = true; } };
        listeners[type].fn(event);
        return event;
    };
    const runTimers = () => timers.splice(0).forEach((fn) => fn());
    return { listeners, dispatch, runTimers, timers };
}

function form(...fields) {
    const el = { elements: fields };
    fields.forEach((f) => { f.form = el; });
    return el;
}

test("invalid events are observed in the capture phase because they do not bubble", () => {
    const { listeners } = setup();
    assert.equal(listeners.invalid.capture, true);
});

test("an invalid TomSelect field marks its visible control and prints the message", () => {
    const { dispatch } = setup();
    const select = field();
    form(select);

    const event = dispatch("invalid", select);

    const { wrapper, control_input } = select.tomselect;
    assert.equal(event.prevented, true);
    assert.equal(wrapper.classList.contains("is-invalid"), true);
    assert.equal(control_input.attributes["aria-invalid"], "true");
    // Above the control, so the dropdown that opens on focus cannot cover it.
    const feedback = select.previousElementSibling;
    assert.equal(feedback.classList.contains("invalid-feedback"), true);
    assert.equal(feedback.classList.contains("d-block"), true);
    assert.equal(feedback.textContent, "Please select an item in the list.");
});

test("repeated invalid events reuse the feedback element", () => {
    const { dispatch } = setup();
    const select = field();
    form(select);

    dispatch("invalid", select);
    const feedback = select.previousElementSibling;
    dispatch("invalid", select);

    assert.equal(select.previousElementSibling, feedback);
});

test("fields without TomSelect keep the browser's native validation", () => {
    const { dispatch, timers } = setup();
    const input = field({ tomselect: false });
    form(input);

    const event = dispatch("invalid", input);

    assert.equal(event.prevented, false);
    assert.equal(timers.length, 0);
});

test("the first invalid field is focused through its TomSelect control", () => {
    const { dispatch, runTimers } = setup();
    const first = field();
    const second = field();
    form(field({ tomselect: false, valid: true }), first, second);

    dispatch("invalid", first);
    dispatch("invalid", second);
    runTimers();

    assert.equal(first.tomselect.focused, 1);
    assert.equal(first.tomselect.wrapper.scrolled, 1);
    assert.equal(second.tomselect.focused, 0);
});

test("focus stays with the browser when a native field is the first invalid one", () => {
    const { dispatch, runTimers } = setup();
    const select = field();
    form(field({ tomselect: false }), select);

    dispatch("invalid", select);
    runTimers();

    assert.equal(select.tomselect.focused, 0);
    assert.equal(select.tomselect.wrapper.classList.contains("is-invalid"), true);
});

test("choosing a value clears the feedback", () => {
    const { dispatch } = setup();
    const select = field();
    form(select);
    dispatch("invalid", select);
    const { wrapper, control_input } = select.tomselect;
    const feedback = select.previousElementSibling;

    select.validity.valid = true;
    dispatch("change", select);

    assert.equal(wrapper.classList.contains("is-invalid"), false);
    assert.equal("aria-invalid" in control_input.attributes, false);
    assert.equal(feedback.removed, true);
});

test("a change that leaves the field invalid keeps the feedback", () => {
    const { dispatch } = setup();
    const select = field();
    form(select);
    dispatch("invalid", select);

    dispatch("change", select);

    assert.equal(select.tomselect.wrapper.classList.contains("is-invalid"), true);
});

test("server-side errors on a TomSelect field are not cleared", () => {
    const { dispatch } = setup();
    const select = field({ valid: true });
    select.tomselect.wrapper.classList.add("is-invalid");

    dispatch("change", select);

    assert.equal(select.tomselect.wrapper.classList.contains("is-invalid"), true);
});
