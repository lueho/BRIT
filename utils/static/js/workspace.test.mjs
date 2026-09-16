import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("./workspace.js", import.meta.url), "utf8");

function element(extra = {}) {
    return {
        dataset: {}, hidden: false, innerHTML: "", textContent: "", disabled: false,
        attributes: {}, listeners: {},
        setAttribute(key, value) { this.attributes[key] = value; },
        removeAttribute(key) { delete this.attributes[key]; },
        addEventListener(key, callback) { this.listeners[key] = callback; },
        querySelector() { return null; }, querySelectorAll() { return []; },
        focus() { this.focused = true; },
        ...extra,
    };
}

function setup(fetch = async () => { throw new Error("offline"); }) {
    const status = element();
    const root = element({
        dataset: { staticUrl: "/static/" },
        querySelector(selector) { return selector === "[data-workspace-status]" ? status : null; },
    });
    const window = element({ confirm: () => true, location: { href: "https://brit.test/objects/1/?mode=edit", origin: "https://brit.test" } });
    const document = element({ readyState: "loading", title: "BRIT · Original" });
    const sandbox = { window, document, fetch, URL, console, FormData: class { constructor(form) { this.form = form; } } };
    vm.runInNewContext(source, sandbox);
    const workspace = new window.MaintenanceWorkspace(root);
    const summary = element({ innerHTML: "Original summary" });
    const editor = element({ hidden: true });
    const heading = element();
    const link = element({ href: "https://brit.test/objects/1/update/?section=overview" });
    const card = element({
        dataset: { workspaceSection: "overview" },
        querySelector(selector) {
            return { "[data-workspace-summary]": summary, "[data-workspace-editor]": editor, "[data-workspace-heading]": heading }[selector] || null;
        },
    });
    link.closest = () => card;
    return { workspace, window, document, root, status, card, summary, editor, heading, link };
}

function activate(fixture) {
    const fields = element();
    const file = element({ name: "image", files: ["chosen.png"] });
    const form = element({
        action: fixture.link.href,
        querySelector(selector) { return selector === "[data-workspace-fields]" ? fields : null; },
        querySelectorAll(selector) { return selector === 'input[type="file"]' ? [file] : []; },
    });
    fixture.workspace.active = { ...fixture, key: "overview", form, dirty: true, busy: false };
    fixture.editor.hidden = false;
    fixture.summary.hidden = true;
    return { form, fields, file };
}

test("initializing the workspace never fetches editors or widget media", () => {
    let requests = 0;
    const { workspace } = setup(() => { requests += 1; });
    assert.equal(requests, 0);
    assert.equal(workspace.active, null);
});

test("opening fetches only the selected fallback URL with the fragment header", async () => {
    const requests = [];
    const fixture = setup(async (url, options) => {
        requests.push({ url, options });
        return { ok: true, status: 200, json: async () => ({ section: "overview", saved: false, html: "Editor" }) };
    });
    fixture.workspace.mountEditor = async (active, html) => { active.editor.innerHTML = html; active.form = element(); };
    await fixture.workspace.open(fixture.link);
    assert.equal(requests.length, 1);
    assert.equal(requests[0].url, fixture.link.href);
    assert.equal(requests[0].options.headers["X-Requested-With"], "XMLHttpRequest");
    assert.equal(fixture.editor.innerHTML, "Editor");
    assert.equal(fixture.summary.hidden, true);
    assert.equal(fixture.link.attributes["aria-expanded"], "true");
});

test("the hero title action opens the overview editor outside its card", async () => {
    const fixture = setup(async () => ({ ok: true, status: 200, json: async () => ({ section: "overview", saved: false, html: "Title editor" }) }));
    fixture.link.closest = () => null;
    fixture.link.dataset = { workspaceEdit: "overview", workspaceFocus: "name" };
    fixture.root.querySelector = (selector) => selector === '[data-workspace-section="overview"]' ? fixture.card : fixture.status;
    fixture.workspace.mountEditor = async (active, html) => { active.editor.innerHTML = html; active.form = element(); };
    await fixture.workspace.open(fixture.link);
    assert.equal(fixture.workspace.active.key, "overview");
    assert.equal(fixture.editor.innerHTML, "Title editor");
    assert.equal(fixture.editor.hidden, false);
});

test("all title and overview controls reflect the same editor state", async () => {
    const fixture = setup(async () => ({ ok: true, status: 200, json: async () => ({ section: "overview", saved: false, html: "Editor" }) }));
    const titleLink = element();
    fixture.root.querySelectorAll = () => [fixture.link, titleLink];
    fixture.workspace.mountEditor = async (active) => { active.form = element(); };
    await fixture.workspace.open(fixture.link);
    assert.equal(titleLink.attributes["aria-expanded"], "true");
    fixture.workspace.cancel();
    assert.equal(titleLink.attributes["aria-expanded"], "false");
});

test("title saves update the hero and browser title", async () => {
    const fixture = setup(async () => ({ ok: true, status: 200, json: async () => ({ section: "overview", saved: true, html: "New title summary", title: "Renamed process" }) }));
    const title = element();
    fixture.root.querySelectorAll = (selector) => selector === "[data-workspace-title]" ? [title] : [];
    activate(fixture);
    fixture.workspace.replaceSummary = () => {};
    await fixture.workspace.save();
    assert.equal(title.textContent, "Renamed process");
    assert.equal(fixture.document.title, "BRIT · Renamed process");
});

test("failed opening retains the summary and offers a normal page fallback", async () => {
    const fixture = setup();
    await fixture.workspace.open(fixture.link);
    assert.equal(fixture.summary.hidden, false);
    assert.equal(fixture.summary.innerHTML, "Original summary");
    assert.equal(fixture.workspace.active, null);
    assert.match(fixture.status.textContent, /could not.*open|could not.*load/i);
});

test("network save failure keeps the same form, selected files and dirty state", async () => {
    const fixture = setup();
    const { form, file, fields } = activate(fixture);
    await fixture.workspace.save();
    assert.equal(fixture.workspace.active.form, form);
    assert.deepEqual(file.files, ["chosen.png"]);
    assert.equal(fixture.workspace.active.dirty, true);
    assert.equal(fields.disabled, false);
    assert.equal(fixture.summary.innerHTML, "Original summary");
    assert.match(fixture.status.textContent, /not saved/i);
});

test("422 validation merges only errors and retains file inputs and entered values", async () => {
    const fixture = setup(async () => ({ ok: false, status: 422, json: async () => ({ section: "overview", saved: false, html: "Bound errors" }) }));
    const { form, file } = activate(fixture);
    let merged;
    fixture.workspace.mergeErrors = (active, html) => { merged = html; };
    await fixture.workspace.save();
    assert.equal(merged, "Bound errors");
    assert.equal(fixture.workspace.active.form, form);
    assert.deepEqual(file.files, ["chosen.png"]);
    assert.equal(fixture.workspace.active.dirty, true);
    assert.match(fixture.status.textContent, /correct/i);
});

test("successful save updates only this summary, title and live message and returns focus", async () => {
    const fixture = setup(async () => ({ ok: true, status: 200, json: async () => ({ section: "overview", saved: true, html: "New summary", title: "New title", message: "Saved privately." }) }));
    activate(fixture);
    fixture.workspace.replaceSummary = (active, html) => { active.summary.innerHTML = html; };
    await fixture.workspace.save();
    assert.equal(fixture.summary.innerHTML, "New summary");
    assert.equal(fixture.status.textContent, "Saved privately.");
    assert.equal(fixture.document.title, "BRIT · New title");
    assert.equal(fixture.workspace.active, null);
    assert.equal(fixture.link.focused, true);
    assert.equal(fixture.summary.hidden, false);
});

test("workspaces that repeat section data elsewhere reload the page after a successful save", async () => {
    const fixture = setup(async () => ({ ok: true, status: 200, json: async () => ({ section: "overview", saved: true, html: "New summary", title: "New title" }) }));
    fixture.root.dataset.workspaceReload = "";
    let reloaded = 0;
    fixture.window.location.reload = () => { reloaded += 1; };
    const { fields } = activate(fixture);
    fixture.workspace.replaceSummary = () => { throw new Error("must not patch the summary in place"); };
    await fixture.workspace.save();
    assert.equal(reloaded, 1);
    assert.equal(fixture.workspace.active.dirty, false);
    assert.equal(fields.disabled, true);
    const event = { preventDefault() { this.prevented = true; } };
    fixture.window.listeners.beforeunload(event);
    assert.equal(event.prevented, undefined);
});

test("the sample detail workspace opts into reloading while the process detail workspace does not", () => {
    const sample = readFileSync(new URL("../../../materials/templates/materials/sample_detail_v2.html", import.meta.url), "utf8");
    assert.match(sample, /data-workspace data-workspace-reload/);
    const process = readFileSync(new URL("../../../processes/templates/processes/process_detail.html", import.meta.url), "utf8");
    assert.doesNotMatch(process, /data-workspace-reload/);
});

test("cancel and switching sections cannot silently discard unsaved changes", () => {
    const fixture = setup();
    activate(fixture);
    fixture.window.confirm = () => false;
    assert.equal(fixture.workspace.cancel(), false);
    assert.ok(fixture.workspace.active);
    fixture.window.confirm = () => true;
    assert.equal(fixture.workspace.cancel(), true);
    assert.equal(fixture.workspace.active, null);
    assert.equal(fixture.link.focused, true);
});

test("beforeunload warns only while changes are unsaved", () => {
    const fixture = setup();
    const event = { preventDefault() { this.prevented = true; } };
    fixture.window.listeners.beforeunload(event);
    assert.equal(event.prevented, undefined);
    activate(fixture);
    fixture.window.listeners.beforeunload(event);
    assert.equal(event.prevented, true);
    assert.equal(event.returnValue, "");
});

test("a response for another section cannot overwrite the current editor", async () => {
    const fixture = setup(async () => ({ ok: true, status: 200, json: async () => ({ section: "resources", saved: true, html: "Wrong summary" }) }));
    const { form } = activate(fixture);
    await fixture.workspace.save();
    assert.equal(fixture.workspace.active.form, form);
    assert.equal(fixture.summary.innerHTML, "Original summary");
    assert.match(fixture.status.textContent, /not saved/i);
});

test("quick create delegates to a small section form rather than eagerly rendering all formsets", () => {
    const template = readFileSync(new URL("../../../processes/templates/processes/process_form.html", import.meta.url), "utf8");
    assert.match(template, /process_section_form\.html/);
    assert.doesNotMatch(template, /inlines\.\d|formset_base\.html/);
});

test("detail edit mode includes a summary-only workspace and read-only mode remains available", () => {
    const template = readFileSync(new URL("../../../processes/templates/processes/process_detail.html", import.meta.url), "utf8");
    assert.match(template, /edit_mode_enabled/);
    assert.match(template, /workspace\.html/);
    assert.match(template, /Done editing/);
});

test("initial summaries use each maintenance section's role-filtered material links", () => {
    const template = readFileSync(new URL("../../../utils/templates/utils/includes/workspace_sections.html", import.meta.url), "utf8");
    assert.match(template, /material_links=section\.material_links/);
    assert.doesNotMatch(template, /input_materials|output_materials/);
});

test("standalone form submits normally instead of being intercepted by the workspace", () => {
    const fixture = setup();
    fixture.root.dataset.workspaceStandalone = "";
    fixture.workspace = new fixture.window.MaintenanceWorkspace(fixture.root);
    const { form } = activate(fixture);
    let saved = false;
    fixture.workspace.save = () => { saved = true; };
    const event = { target: form, preventDefault() { this.prevented = true; } };
    fixture.root.listeners.submit(event);
    assert.equal(saved, false);
    assert.equal(event.prevented, undefined);
});

test("validation merges messages, opens optional details and focuses the actual invalid field", () => {
    const fixture = setup();
    const { form } = activate(fixture);
    const details = element();
    const field = element({ type: "text", value: "Keep my notes" });
    const error = element({ dataset: { workspaceErrors: "process_materials-0-notes" }, textContent: "Error", closest: () => details });
    const incoming = element({ dataset: error.dataset, innerHTML: "Invalid notes" });
    fixture.workspace.fragment = () => element({ querySelectorAll: () => [incoming] });
    fixture.workspace.stripScripts = () => { };
    form.querySelectorAll = () => [error];
    form.elements = { namedItem: () => field };
    fixture.workspace.mergeErrors(fixture.workspace.active, "Bound error HTML");
    assert.equal(error.innerHTML, "Invalid notes");
    assert.equal(field.value, "Keep my notes");
    assert.equal(field.attributes["aria-invalid"], "true");
    assert.equal(details.open, true);
    assert.equal(field.focused, true);
});

test("adding an empty Django row replaces all prefix tokens and increments the management count", async () => {
    const fixture = setup();
    activate(fixture);
    const total = element({ value: "2" });
    const max = element({ value: "1000" });
    const template = element({ innerHTML: '<input name="process_materials-__prefix__-material" id="id_process_materials-__prefix__-material">' });
    const row = element();
    const fragment = element({ querySelector: () => row });
    let generated;
    let appended;
    let initialized;
    fixture.workspace.fragment = (html) => { generated = html; return fragment; };
    fixture.workspace.stripScripts = () => { };
    fixture.workspace.initializeWidgets = (container) => { initialized = container; };
    const formset = element({
        querySelector(selector) {
            return {
                'input[name$="-TOTAL_FORMS"]': total,
                'input[name$="-MAX_NUM_FORMS"]': max,
                "template[data-workspace-empty]": template,
                "[data-workspace-rows]": { appendChild(node) { appended = node; } },
            }[selector];
        }
    });
    let mediaRoot;
    fixture.workspace.loadMedia = async (container) => { mediaRoot = container; };
    await fixture.workspace.addRow(formset);
    assert.equal(mediaRoot, fixture.editor);
    assert.equal(total.value, "3");
    assert.match(generated, /name="process_materials-2-material"/);
    assert.match(generated, /id="id_process_materials-2-material"/);
    assert.doesNotMatch(generated, /__prefix__/);
    assert.equal(appended, fragment);
    assert.equal(initialized, row);
    assert.equal(fixture.workspace.active.dirty, true);
});

test("errors are also visible beside the active section's save controls", () => {
    const fixture = setup();
    activate(fixture);
    const localStatus = element();
    fixture.editor.querySelector = () => localStatus;
    fixture.workspace.announce("Not saved. Try again.", true);
    assert.equal(localStatus.textContent, "Not saved. Try again.");
    assert.equal(fixture.status.textContent, "Not saved. Try again.");
});

function remoteWidget(fixture, labelField = "name", autocompleteUrl = "/materials/autocomplete/") {
    const select = element({
        dataset: { autocompleteUrl, valueField: "id", labelField },
        tagName: "SELECT", type: "select-one", id: "id_material", value: "9",
        classList: { add() { } }, closest: () => null,
        labels: [{ textContent: "Material" }],
    });
    let config;
    const instance = { loadedSearches: {} };
    fixture.window.TomSelect = class {
        constructor(node, settings) {
            config = settings;
            node.tomselect = instance;
            return instance;
        }
    };
    const container = element({ querySelectorAll: () => [select] });
    fixture.workspace.initializeWidgets(container);
    return { select, config, instance };
}

test("autocomplete markup renders only supplied selected options, never bound field choices", () => {
    const fieldTemplate = readFileSync(new URL("../../../utils/templates/utils/includes/workspace_field.html", import.meta.url), "utf8");
    assert.match(fieldTemplate, /for option in field\.field\.workspace_options/);
    assert.match(fieldTemplate, /data-autocomplete-url="{{ field\.field\.workspace_autocomplete_url }}"/);
    assert.match(fieldTemplate, /data-label-field="{{ field\.field\.workspace_label_field }}"/);
    assert.match(fieldTemplate, /data-value-field="{{ field\.field\.workspace_value_field }}"/);
    assert.match(fieldTemplate, /<option value="{{ option\.value }}" selected>{{ option\.label }}<\/option>/);
    assert.doesNotMatch(fieldTemplate, /for option in field %|field\.queryset/);
    const formTemplate = readFileSync(new URL("../../../utils/templates/utils/includes/workspace_section_form.html", import.meta.url), "utf8");
    assert.match(formTemplate, /<noscript>[\s\S]*JavaScript[\s\S]*search/);
});

test("remote widgets use a 15-result cap and do not preload or create unknown options", () => {
    let requests = 0;
    const fixture = setup(() => { requests += 1; });
    const { config, select } = remoteWidget(fixture);
    assert.equal(config.maxOptions, 15);
    assert.equal(config.loadThrottle, 300);
    assert.equal(config.preload, false);
    assert.equal(config.openOnFocus, true);
    assert.equal(config.create, false);
    assert.equal(config.valueField, "id");
    assert.equal(config.labelField, "name");
    assert.deepEqual(Array.from(config.searchField), ["name"]);
    assert.equal(requests, 0);
    assert.equal(select.value, "9");
});

test("remote search sends encoded q with same-origin credentials and handles paginated results", async () => {
    const requests = [];
    const results = Array.from({ length: 20 }, (_, i) => ({ id: i + 1, name: `Match ${i + 1}` }));
    const fixture = setup(async (url, options) => {
        requests.push({ url: new URL(url), options });
        return { ok: true, json: async () => ({ results, page: 1, has_more: true }) };
    });
    const { config, instance } = remoteWidget(fixture);
    let options;
    await config.load.call(instance, "rice & straw", (items) => { options = items; });
    assert.equal(requests.length, 1);
    assert.equal(requests[0].url.origin, "https://brit.test");
    assert.equal(requests[0].url.pathname, "/materials/autocomplete/");
    assert.equal(requests[0].url.searchParams.get("q"), "rice & straw");
    assert.equal(requests[0].options.method, "GET");
    assert.equal(requests[0].options.credentials, "same-origin");
    assert.equal(options.length, 15);
    assert.equal(options[0].id, "1");
    assert.equal(options[0].name, "Match 1");
});

test("reference searches use label fields and escape labels instead of trusting result HTML", async () => {
    const fixture = setup(async () => ({ ok: true, json: async () => ({ results: [{ id: 42, label: '<img src=x onerror="attack()">', html: "unsafe" }] }) }));
    const { config, instance } = remoteWidget(fixture, "label", "/sources/autocomplete/");
    let results;
    await config.load.call(instance, "reference", (items) => { results = items; });
    assert.equal(config.labelField, "label");
    assert.deepEqual(Array.from(config.searchField), ["label"]);
    assert.deepEqual(Object.keys(results[0]).sort(), ["id", "label"]);
    const escape = (text) => text.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
    for (const render of [config.render.option, config.render.item]) {
        const html = render(results[0], escape);
        assert.match(html, /&lt;img/);
        assert.doesNotMatch(html, /<img/);
    }
});

test("empty autocomplete results settle the callback without clearing the selected value", async () => {
    const fixture = setup(async () => ({ ok: true, json: async () => ({ results: [], has_more: false }) }));
    const { config, instance, select } = remoteWidget(fixture);
    let callbacks = 0;
    await config.load.call(instance, "no match", (items) => { callbacks += 1; assert.equal(items.length, 0); });
    assert.equal(callbacks, 1);
    assert.equal(select.value, "9");
});

test("failed searches settle callbacks, preserve selections, announce failure and permit retry", async () => {
    for (const fetch of [
        async () => { throw new Error("offline"); },
        async () => ({ ok: false, status: 403 }),
        async () => ({ ok: true, redirected: true }),
        async () => ({ ok: true, json: async () => ({ unexpected: [] }) }),
    ]) {
        const fixture = setup(fetch);
        const { config, instance, select } = remoteWidget(fixture);
        instance.loadedSearches.straw = true;
        let callbacks = 0;
        await config.load.call(instance, "straw", (items) => { callbacks += 1; assert.equal(items.length, 0); });
        assert.equal(callbacks, 1);
        assert.equal(select.value, "9");
        assert.equal(instance.loadedSearches.straw, undefined);
        assert.match(fixture.status.textContent, /could not search.*Material/i);
        assert.match(fixture.status.textContent, /selections.*kept/i);
    }
});

test("autocomplete rejects cross-origin endpoints without making a request", async () => {
    let requests = 0;
    const fixture = setup(() => { requests += 1; });
    const { config, instance } = remoteWidget(fixture, "name", "https://evil.test/search/");
    let settled = false;
    await config.load.call(instance, "straw", (items) => { settled = items.length === 0; });
    assert.equal(settled, true);
    assert.equal(requests, 0);
    assert.match(fixture.status.textContent, /could not search/i);
});

test("blank searches do not fetch first-page options automatically", async () => {
    let requests = 0;
    const fixture = setup(() => { requests += 1; });
    const { config, instance } = remoteWidget(fixture);
    assert.equal(config.shouldLoad("   "), false);
    assert.equal(config.shouldLoad("straw"), true);
    let settled = false;
    await config.load.call(instance, "", (items) => { settled = items.length === 0; });
    assert.equal(settled, true);
    assert.equal(requests, 0);
});

test("empty editors defer widget dependencies until a row actually needs a select", async () => {
    const { workspace } = setup();
    let requested = 0;
    let removed = false;
    workspace.loadAsset = async () => { requested += 1; };
    const template = element({
        content: element({ querySelectorAll: () => [element()] }),
        remove() { removed = true; },
    });
    const fragment = element({ querySelector: () => null, querySelectorAll: () => [template] });
    await workspace.loadMedia(fragment);
    assert.equal(requested, 0);
    assert.equal(removed, false);
});

test("inert media templates survive script stripping for on-demand row initialization", () => {
    const { workspace } = setup();
    let removed = false;
    const script = element({ remove() { removed = true; } });
    const template = element({
        dataset: { workspaceMedia: "" },
        content: element({ querySelectorAll: (selector) => selector === "script" ? [script] : [] }),
    });
    const fragment = element({ querySelectorAll: (selector) => selector === "template" ? [template] : [] });
    workspace.stripScripts(fragment);
    assert.equal(removed, false);
});

test("late search errors from a closed editor do not overwrite the current status", async () => {
    const fixture = setup();
    const { config, instance, select } = remoteWidget(fixture);
    select.isConnected = false;
    fixture.workspace.announce("Editing cancelled.");
    await config.load.call(instance, "straw", () => { });
    assert.equal(fixture.status.textContent, "Editing cancelled.");
});

test("media trust is restricted to the configured static TomSelect package", () => {
    const { workspace } = setup();
    assert.equal(workspace.trustedMediaURL("/static/django_tomselect/js/django-tomselect.min.js", "script").href, "https://brit.test/static/django_tomselect/js/django-tomselect.min.js");
    for (const url of ["https://evil.test/static/django_tomselect/js/x.js", "/uploads/x.js", "javascript:alert(1)", "/static/django_tomselect/../../uploads/x.js"]) {
        assert.throws(() => workspace.trustedMediaURL(url, "script"));
    }
    assert.throws(() => workspace.trustedMediaURL("/static/django_tomselect/css/x.css", "script"));
});

function pasteFixture(fixture, { text, results = {}, maxRows = Infinity, columns = "component,average" }) {
    const errors = {};
    const rowsContainer = { lastElementChild: element({ fields: {}, querySelector: () => null }) };
    const formset = element({
        querySelector(selector) { return selector === "[data-workspace-rows]" ? rowsContainer : null; },
    });
    const input = element({
        value: text,
        dataset: { pasteFormset: "component_measurements", pasteColumns: columns },
    });
    const apply = element({ disabled: false });
    const panel = element({
        querySelector(selector) {
            if (selector === "[data-workspace-paste-input]") return input;
            if (selector === "[data-workspace-paste-apply]") return apply;
            return null;
        },
    });
    let created = 0;
    fixture.workspace.addRow = async () => {
        await Promise.resolve();
        if (created >= maxRows) return null;
        created += 1;
        const rowFields = {};
        const row = element({
            querySelector(selector) {
                const byName = selector.match(/\[name\$="-(\w+)"\]/);
                if (byName) {
                    if (!rowFields[byName[1]]) {
                        const isSelect = ["component", "unit"].includes(byName[1]);
                        rowFields[byName[1]] = element({
                            name: `component_measurements-${created}-${byName[1]}`,
                            matches: (s) => isSelect && s === "select[data-workspace-select]",
                            dataset: { valueField: "id", labelField: "name", autocompleteUrl: "/components/" },
                        });
                        if (isSelect) {
                            rowFields[byName[1]].tomselect = {
                                added: [],
                                addOption(option) { this.added.push(option); },
                                addItem(value) { this.value = value; },
                            };
                        }
                    }
                    return rowFields[byName[1]];
                }
                const byError = selector.match(/\[data-workspace-errors="([^"]+)"\]/);
                if (byError) return (errors[byError[1]] ??= element());
                return null;
            },
        });
        row.fields = rowFields;
        rowsContainer.lastElementChild = row;
        return row;
    };
    fixture.workspace.active.editor = element({
        querySelector(selector) { return selector === '[data-workspace-formset="component_measurements"]' ? formset : null; },
    });
    fixture.workspace.searchOptions = async (select, query) => results[query] || [];
    return { input, panel, apply, formset, errors, rowsContainer, created: () => created };
}

test("pasted spreadsheet rows create a formset row per line and resolve names", async () => {
    const fixture = setup();
    activate(fixture);
    const mock = pasteFixture(fixture, {
        text: "Ash\t12.5\nMoisture\t4,25",
        results: { Ash: [{ id: 7, name: "Ash" }], Moisture: [{ id: 8, name: "Moisture" }] },
    });
    await fixture.workspace.applyPaste(mock.panel);
    assert.equal(mock.created(), 2);
    const row1 = mock.rowsContainer.lastElementChild.fields;
    assert.equal(row1.component.tomselect.value, "8");
    assert.equal(row1.component.tomselect.added[0].name, "Moisture");
    assert.equal(row1.average.value, "4.25");
    assert.equal(mock.input.value, "");
    assert.equal(fixture.workspace.active.dirty, true);
    assert.match(fixture.status.textContent, /Added 2 rows/);
});

test("a pasted header line is skipped and empty paste announces guidance", async () => {
    const fixture = setup();
    activate(fixture);
    const mock = pasteFixture(fixture, {
        text: "Component\tValue\nAsh\t12.5",
        results: { Ash: [{ id: 7, name: "Ash" }] },
    });
    await fixture.workspace.applyPaste(mock.panel);
    assert.equal(mock.created(), 1);

    const empty = pasteFixture(fixture, { text: "\n  \n" });
    await fixture.workspace.applyPaste(empty.panel);
    assert.equal(empty.created(), 0);
    assert.match(fixture.status.textContent, /Nothing to add/);
});

test("ambiguous or unknown pasted names are flagged on the row for manual choice", async () => {
    const fixture = setup();
    activate(fixture);
    const mock = pasteFixture(fixture, {
        text: "Lignin\t9.9",
        results: { Lignin: [{ id: 3, name: "Lignin (Klason)" }, { id: 4, name: "Lignin (ADL)" }] },
    });
    await fixture.workspace.applyPaste(mock.panel);
    assert.equal(mock.created(), 1);
    assert.match(mock.errors["component_measurements-1-component"].textContent, /No match for "Lignin"/);
    assert.match(fixture.status.textContent, /1 value needs attention/);
    assert.equal(fixture.status.className, "alert alert-danger");
});

test("paste stops at the row limit instead of overwriting the last existing row", async () => {
    const fixture = setup();
    activate(fixture);
    const mock = pasteFixture(fixture, {
        text: "Ash\t12.5\nMoisture\t4.25\nLignin\t9.9",
        results: { Ash: [{ id: 7, name: "Ash" }] },
        maxRows: 1,
    });
    const existing = mock.rowsContainer.lastElementChild;
    await fixture.workspace.applyPaste(mock.panel);
    assert.equal(mock.created(), 1);
    assert.notEqual(mock.rowsContainer.lastElementChild, existing);
    assert.equal(mock.rowsContainer.lastElementChild.fields.average.value, "12.5");
    assert.match(fixture.status.textContent, /Added 1 row.*2 lines? (was|were) not added/);
    assert.equal(fixture.status.className, "alert alert-danger");
});

test("a second paste while one is running is ignored and the apply button is re-enabled afterwards", async () => {
    const fixture = setup();
    activate(fixture);
    const mock = pasteFixture(fixture, {
        text: "Ash\t12.5\nMoisture\t4.25",
        results: { Ash: [{ id: 7, name: "Ash" }], Moisture: [{ id: 8, name: "Moisture" }] },
    });
    const first = fixture.workspace.applyPaste(mock.panel);
    assert.equal(mock.apply.disabled, true);
    await fixture.workspace.applyPaste(mock.panel);
    await first;
    assert.equal(mock.created(), 2);
    assert.equal(mock.apply.disabled, false);
    assert.equal(fixture.workspace.active.pasting, false);
});

test("the paste guard is released when a paste fails", async () => {
    const fixture = setup();
    activate(fixture);
    const mock = pasteFixture(fixture, { text: "Ash\t12.5" });
    fixture.workspace.addRow = async () => { throw new Error("boom"); };
    await assert.rejects(fixture.workspace.applyPaste(mock.panel));
    assert.equal(mock.apply.disabled, false);
    assert.equal(fixture.workspace.active.pasting, false);
});

test("only recognised header labels are skipped; a non-numeric first value is kept and flagged", async () => {
    const fixture = setup();
    activate(fixture);
    const invalid = pasteFixture(fixture, {
        text: "Ash\tbelow detection\nMoisture\t4.25",
        results: { Ash: [{ id: 7, name: "Ash" }], Moisture: [{ id: 8, name: "Moisture" }] },
    });
    await fixture.workspace.applyPaste(invalid.panel);
    assert.equal(invalid.created(), 2);
    assert.match(invalid.errors["component_measurements-1-average"].textContent, /"below detection" is not a number/);
    assert.match(fixture.status.textContent, /Added 2 rows\. 1 value needs attention/);
    assert.equal(fixture.status.className, "alert alert-danger");

    const header = pasteFixture(fixture, {
        text: "Group\tComponent\tValue\tUnit\tStandard deviation\tn\nMain\tAsh\t12.5\t%\t0.1\t3",
        results: { Ash: [{ id: 7, name: "Ash" }] },
        columns: "group,component,average,unit,standard_deviation,sample_size",
    });
    await fixture.workspace.applyPaste(header.panel);
    assert.equal(header.created(), 1);
    assert.equal(header.rowsContainer.lastElementChild.fields.average.value, "12.5");
});

test("a full formset reports how many pasted lines were not added", async () => {
    const fixture = setup();
    activate(fixture);
    const mock = pasteFixture(fixture, { text: "Ash\t12.5\nMoisture\t4.25", maxRows: 0 });
    const existing = mock.rowsContainer.lastElementChild;
    await fixture.workspace.applyPaste(mock.panel);
    assert.equal(mock.created(), 0);
    assert.equal(mock.rowsContainer.lastElementChild, existing);
    assert.equal(mock.input.value, "Ash\t12.5\nMoisture\t4.25");
    assert.match(fixture.status.textContent, /Nothing was added\. 2 lines were not added because the maximum number of rows has been reached/);
});

test("saving and cancelling are blocked while a paste is still filling rows", async () => {
    let fetched = false;
    const fixture = setup(async () => { fetched = true; throw new Error("should not save"); });
    activate(fixture);
    const mock = pasteFixture(fixture, { text: "Ash\t12.5", results: { Ash: [{ id: 7, name: "Ash" }] } });
    const pasting = fixture.workspace.applyPaste(mock.panel);
    assert.equal(fixture.workspace.active.pasting, true);
    await fixture.workspace.save();
    assert.equal(fetched, false);
    assert.match(fixture.status.textContent, /still being filled/);
    assert.equal(fixture.workspace.cancel(), false);
    await pasting;
    assert.equal(fixture.workspace.active.pasting, false);
});

test("unit search results keep the symbol so pasted symbols resolve", async () => {
    const fixture = setup(async () => ({ ok: true, json: async () => ({ results: [{ id: 5, name: "Percent", symbol: "%", html: "unsafe" }, { id: 6, name: "Gram per kilogram", symbol: 7 }] }) }));
    const { config, instance } = remoteWidget(fixture, "name", "/units/autocomplete/");
    let results;
    await config.load.call(instance, "%", (items) => { results = items; });
    assert.equal(JSON.stringify(results), JSON.stringify([{ id: "5", name: "Percent", symbol: "%" }, { id: "6", name: "Gram per kilogram" }]));
});

test("pasted unit symbols resolve against the symbol as well as the name", async () => {
    const fixture = setup();
    activate(fixture);
    const mock = pasteFixture(fixture, {
        text: "Ash\t12.5\t%",
        columns: "component,average,unit",
        results: { Ash: [{ id: 7, name: "Ash" }], "%": [{ id: 5, name: "Percent", symbol: "%" }, { id: 9, name: "Per mille", symbol: "‰" }] },
    });
    await fixture.workspace.applyPaste(mock.panel);
    assert.equal(mock.created(), 1);
    const row = mock.rowsContainer.lastElementChild.fields;
    assert.equal(row.component.tomselect.value, "7");
    assert.equal(row.unit.tomselect.value, "5");
    assert.equal(row.average.value, "12.5");
    assert.match(fixture.status.textContent, /Added 1 row\. Review them/);
});
