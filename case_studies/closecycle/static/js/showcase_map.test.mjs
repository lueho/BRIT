import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const HERE = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(HERE, "showcase_map.js"), "utf8");
const sharedSource = readFileSync(
    join(HERE, "../../../../maps/static/js/maps.js"),
    "utf8"
);

function makeElement(tagName) {
    const element = {
        tagName: tagName.toUpperCase(),
        children: [],
        listeners: {},
        attributes: {},
        style: {},
        className: "",
        classList: {
            add() {},
            remove() {},
        },
        appendChild(child) {
            this.children.push(child);
            return child;
        },
        setAttribute(name, value) {
            this.attributes[name] = String(value);
        },
        getAttribute(name) {
            return this.attributes[name];
        },
        hasChildNodes() {
            return this.children.length > 0;
        },
        addEventListener(type, callback) {
            (this.listeners[type] ||= []).push(callback);
        },
        click() {
            (this.listeners.click || []).forEach(callback =>
                callback({ preventDefault() {} })
            );
        },
        get innerHTML() {
            return this.children.map(child => child.innerHTML ?? child.textContent).join("");
        },
    };
    let text = "";
    Object.defineProperty(element, "textContent", {
        get() {
            return text;
        },
        set(value) {
            text = String(value);
            element.children.length = 0;
        },
    });
    return element;
}

function textOf(element) {
    return (
        (element.textContent || "") +
        element.children.map(textOf).join("")
    );
}

function findAll(element, predicate, found = []) {
    if (predicate(element)) {
        found.push(element);
    }
    element.children.forEach(child => findAll(child, predicate, found));
    return found;
}

function setup({ loadShared = false } = {}) {
    const calls = {
        openPopup: [],
        closePopup: 0,
        fetchSummaries: [],
        selected: [],
        resets: 0,
        summaryTabShown: 0,
        infoCardShown: 0,
    };

    class FakePolygon {}
    const L = {
        Polygon: FakePolygon,
        point: (x, y) => ({ x, y }),
    };

    const insideChecks = new Map();
    const turf = {
        inside(point, polygon) {
            return insideChecks.get(polygon) ?? true;
        },
    };

    const map = {
        openPopup(content, latlng, options) {
            calls.openPopup.push({ content, latlng, options });
        },
        closePopup() {
            calls.closePopup += 1;
        },
        // Test projection: 1 degree = 1 pixel.
        latLngToLayerPoint(latlng) {
            return { x: latlng.lng, y: latlng.lat };
        },
    };

    const elements = {
        "summary-container": makeElement("div"),
        "summary-tab": makeElement("button"),
        "info-card-body": makeElement("div"),
    };
    elements["info-card-body"].classList.add = () => {
        calls.infoCardShown += 1;
    };

    const documentListeners = {};
    const windowListeners = {};
    const document = {
        createElement: tagName => makeElement(tagName),
        getElementById: id => elements[id] || null,
        querySelector: selector =>
            selector === "#info-card-body" ? elements["info-card-body"] : null,
        querySelectorAll: () => [],
        addEventListener(type, callback) {
            (documentListeners[type] ||= []).push(callback);
        },
    };

    const window = {
        location: new URL("http://localhost/closecycle/showcases/map/"),
        addEventListener(type, callback) {
            (windowListeners[type] ||= []).push(callback);
        },
    };

    const bootstrap = {
        Tab: {
            getOrCreateInstance() {
                return {
                    show() {
                        calls.summaryTabShown += 1;
                    },
                };
            },
        },
    };

    const sandbox = {
        L,
        turf,
        map,
        window,
        document,
        bootstrap,
        console,
        URL,
        URLSearchParams,
        AbortController,
        mapConfig: { loadFeatures: false },
        fetchFeaturesLayerSummary(params) {
            calls.fetchSummaries.push(params);
            return Promise.resolve();
        },
        selectFeature(layer) {
            calls.selected.push(layer);
        },
        resetFeatureStyles() {
            calls.resets += 1;
        },
    };
    window.window = window;
    vm.createContext(sandbox);
    if (loadShared) {
        vm.runInContext(sharedSource, sandbox);
        (windowListeners["map:init"] || []).forEach(callback =>
            callback({ detail: { map } })
        );
    }
    vm.runInContext(source, sandbox);
    return { sandbox, calls, L, insideChecks, elements, documentListeners };
}

function makeLayer({ L, id, name, region }) {
    const layer = new L.Polygon();
    layer.feature = { id, properties: { name, region } };
    layer.toGeoJSON = () => ({ geometry: { id } });
    return layer;
}

function makePointLayer({ id, name, region, lat = 55, lng = 14 }) {
    return {
        feature: { id, properties: { name, region } },
        getLatLng() {
            return { lat, lng };
        },
    };
}

function makeFeatureGroup(layers) {
    return {
        eachLayer(callback) {
            layers.forEach(callback);
        },
    };
}

function makeSummary(overrides = {}) {
    return {
        id: 7,
        name: "Showcase",
        region: null,
        description: null,
        url: "/closecycle/showcases/7/",
        input_materials: [],
        involved_processes: [],
        intermediate_materials: [],
        products: [],
        ...overrides,
    };
}

const clickEvent = { latlng: { lng: 14, lat: 55 } };

test("summary renders heading, region, description and ordered sections", () => {
    const { sandbox } = setup();
    const container = makeElement("div");
    sandbox.renderSummaryContainer(
        makeSummary({
            name: "<img onerror=alert(1)> Showcase",
            region: "O'Brien Region",
            description: "First paragraph.\n\nSecond paragraph.",
            input_materials: [
                { id: 1, name: "Straw", url: "/materials/1/" },
            ],
            involved_processes: [
                { id: 3, name: "Zeta", url: "/processes/types/3/" },
                { id: 2, name: "Alpha", url: "/processes/types/2/" },
            ],
            products: [{ id: 4, name: "Biogas", url: "/materials/4/" }],
        }),
        container
    );

    assert.equal(container.className.includes("pk-holder"), true);
    assert.equal(container.getAttribute("data-pk"), "7");

    const heading = container.children[0];
    assert.equal(heading.tagName, "H5");
    assert.equal(heading.textContent, "<img onerror=alert(1)> Showcase");

    const region = container.children[1];
    assert.equal(region.textContent, "O'Brien Region");

    const description = container.children[2];
    assert.equal(description.textContent, "First paragraph.\n\nSecond paragraph.");
    assert.equal(description.style.whiteSpace, "pre-line");

    const headings = findAll(container, el => el.tagName === "H6").map(
        el => el.textContent
    );
    assert.deepEqual(headings, [
        "Input bioresources",
        "Processing chain",
        "Products",
    ]);

    assert.equal(textOf(container).includes("Intermediates"), false);

    const orderedLists = findAll(container, el => el.tagName === "OL");
    assert.equal(orderedLists.length, 1);
    const processAnchors = findAll(orderedLists[0], el => el.tagName === "A");
    assert.deepEqual(
        processAnchors.map(el => el.textContent),
        ["Zeta", "Alpha"]
    );

    const anchors = findAll(container, el => el.tagName === "A");
    anchors.forEach(anchor => {
        assert.equal(anchor.href.startsWith("/"), true);
        assert.equal(anchor.href.startsWith("//"), false);
        assert.equal(anchor.getAttribute("target"), undefined);
    });
    const detailsLink = anchors.find(
        el => el.textContent === "View showcase details"
    );
    assert.equal(detailsLink.href, "/closecycle/showcases/7/");
});

test("summary omits region and description when missing", () => {
    const { sandbox } = setup();
    const container = makeElement("div");
    sandbox.renderSummaryContainer(makeSummary({ id: 9, name: "Bare Showcase" }), container);
    const headings = findAll(container, el => el.tagName === "H6");
    assert.equal(headings.length, 0);
    assert.equal(findAll(container, el => el.tagName === "UL").length, 0);
    assert.equal(findAll(container, el => el.tagName === "OL").length, 0);
    assert.equal(container.children[0].textContent, "Bare Showcase");
});

test("markup in names is rendered as text not html", () => {
    const { sandbox } = setup();
    const container = makeElement("div");
    sandbox.renderSummaryContainer(
        makeSummary({
            input_materials: [
                { id: 1, name: "<b>Straw</b>", url: "/materials/1/" },
            ],
            involved_processes: [
                { id: 2, name: "<script>x</script>", url: "/processes/types/2/" },
            ],
        }),
        container
    );
    const anchors = findAll(container, el => el.tagName === "A");
    assert.deepEqual(
        anchors.map(el => el.textContent),
        ["<b>Straw</b>", "<script>x</script>", "View showcase details"]
    );
    assert.equal(findAll(container, el => el.tagName === "B").length, 0);
    assert.equal(findAll(container, el => el.tagName === "SCRIPT").length, 0);
});

test("unsafe urls are not rendered as links", () => {
    const { sandbox } = setup();
    const container = makeElement("div");
    const tab = String.fromCharCode(9);
    sandbox.renderSummaryContainer(
        makeSummary({
            url: "javascript:alert(1)",
            input_materials: [
                { id: 1, name: "Straw", url: "javascript:alert(2)" },
                { id: 2, name: "Feed", url: "//evil.example/x" },
                { id: 3, name: "Back", url: "/\\evil.example" },
                { id: 4, name: "Tab", url: "/" + tab + "evil" },
            ],
        }),
        container
    );
    const anchors = findAll(container, el => el.tagName === "A");
    assert.equal(anchors.length, 0);
    const items = findAll(container, el => el.tagName === "LI");
    assert.equal(items.length, 4);
    assert.equal(items[0].textContent, "Straw");
});

test("summary tab is shown on init and on render", () => {
    const { sandbox, calls, documentListeners } = setup();
    (documentListeners.DOMContentLoaded || []).forEach(callback => callback());
    assert.equal(calls.summaryTabShown >= 1, true);
    const before = calls.summaryTabShown;
    sandbox.renderSummaryContainer(makeSummary(), makeElement("div"));
    assert.equal(calls.summaryTabShown > before, true);
});

test("shared renderSummaries uses the local container override", () => {
    const { sandbox, calls, elements } = setup({ loadShared: true });
    const container = elements["summary-container"];
    sandbox.renderSummaries({
        summaries: [
            makeSummary({ id: 1, name: "First Showcase" }),
            makeSummary({ id: 2, name: "Second <b>Showcase</b>" }),
        ],
    });
    const details = container.children.filter(el => el.tagName === "DETAILS");
    assert.equal(details.length, 2);
    assert.equal(details[0].open, true);
    assert.equal(details[1].open === true, false);
    const headings = details.map(
        el => el.children.find(child => child.tagName === "SUMMARY").textContent
    );
    assert.deepEqual(headings, ["First Showcase", "Second <b>Showcase</b>"]);
    const pkHolders = findAll(container, el => el.getAttribute("data-pk"));
    assert.deepEqual(
        pkHolders.map(el => el.getAttribute("data-pk")),
        ["1", "2"]
    );
    assert.equal(calls.infoCardShown, 1);
    assert.equal(calls.summaryTabShown >= 1, true);
});

test("shared renderSummaries renders a single summary without details wrapper", () => {
    const { sandbox, elements } = setup({ loadShared: true });
    const container = elements["summary-container"];
    sandbox.renderSummaries({
        summaries: [makeSummary({ id: 5, name: "Only Showcase" })],
    });
    assert.equal(findAll(container, el => el.tagName === "DETAILS").length, 0);
    assert.equal(container.getAttribute("data-pk"), "5");
});

test("shared renderSummaries shows a message for zero summaries", () => {
    const { sandbox, elements } = setup({ loadShared: true });
    const container = elements["summary-container"];
    sandbox.renderSummaries({ summaries: [] });
    assert.equal(container.children.length, 1);
    assert.equal(container.children[0].textContent, "No showcases found.");
});

test("click on two showcases in one region opens a popup instead of autoselecting", () => {
    const { sandbox, calls, L } = setup();
    const first = makeLayer({ L, id: 1, name: "First", region: "O'Brien Region" });
    const second = makeLayer({ L, id: 2, name: "Second", region: "O'Brien Region" });
    const group = makeFeatureGroup([first, second]);

    sandbox.featureClickHandler(clickEvent, group);

    assert.equal(calls.fetchSummaries.length, 0);
    assert.equal(calls.openPopup.length, 1);
    const { content } = calls.openPopup[0];
    const regionHeadings = findAll(content, el => el.tagName === "STRONG");
    assert.deepEqual(
        regionHeadings.map(el => el.textContent),
        ["O'Brien Region"]
    );
    const links = findAll(content, el => el.tagName === "A");
    assert.deepEqual(links.map(el => el.textContent), ["First", "Second"]);
    assert.equal(Object.keys(content.attributes).length, 0);
});

test("popup link click selects every layer of the chosen showcase", () => {
    const { sandbox, calls, L } = setup();
    const firstA = makeLayer({ L, id: 1, name: "First", region: "Region A" });
    const firstB = makeLayer({ L, id: 1, name: "First", region: "Region B" });
    const second = makeLayer({ L, id: 2, name: "Second", region: "Region B" });
    const group = makeFeatureGroup([firstA, firstB, second]);

    sandbox.featureClickHandler(clickEvent, group);
    assert.equal(calls.openPopup.length, 1);
    const links = findAll(calls.openPopup[0].content, el => el.tagName === "A");
    links[0].click();

    assert.deepEqual(calls.fetchSummaries.map(params => params.id), [1]);
    assert.equal(calls.selected.slice(-2)[0], firstA);
    assert.equal(calls.selected.slice(-2)[1], firstB);
    assert.equal(calls.closePopup, 1);
});

test("duplicate polygons of one showcase autoselect without popup", () => {
    const { sandbox, calls, L } = setup();
    const firstA = makeLayer({ L, id: 1, name: "First", region: "Region A" });
    const firstB = makeLayer({ L, id: 1, name: "First", region: "Region B" });
    const group = makeFeatureGroup([firstA, firstB]);

    sandbox.featureClickHandler(clickEvent, group);

    assert.equal(calls.openPopup.length, 0);
    assert.deepEqual(calls.fetchSummaries.map(params => params.id), [1]);
    assert.equal(calls.selected[0], firstA);
    assert.equal(calls.selected[1], firstB);
});

test("click near a showcase point selects it", () => {
    const { sandbox, calls } = setup();
    const marker = makePointLayer({ id: 1, name: "Site", region: "Region A" });
    const distant = makePointLayer({ id: 2, name: "Far", region: "Region B", lat: 60, lng: 30 });
    const group = makeFeatureGroup([marker, distant]);

    sandbox.featureClickHandler(clickEvent, group);

    assert.equal(calls.openPopup.length, 0);
    assert.deepEqual(calls.fetchSummaries.map(params => params.id), [1]);
    assert.equal(calls.selected[0], marker);
});

test("click misses a far-away showcase point", () => {
    const { sandbox, calls } = setup();
    const distant = makePointLayer({ id: 2, name: "Far", region: "Region B", lat: 60, lng: 30 });
    const group = makeFeatureGroup([distant]);

    sandbox.featureClickHandler(clickEvent, group);

    assert.equal(calls.openPopup.length, 1);
    assert.equal(calls.fetchSummaries.length, 0);
});

test("co-located showcase points open a popup instead of autoselecting", () => {
    const { sandbox, calls } = setup();
    const first = makePointLayer({ id: 1, name: "First", region: "Region A" });
    const second = makePointLayer({ id: 2, name: "Second", region: "Region A" });
    const group = makeFeatureGroup([first, second]);

    sandbox.featureClickHandler(clickEvent, group);

    assert.equal(calls.openPopup.length, 1);
    const links = findAll(calls.openPopup[0].content, el => el.tagName === "A");
    assert.deepEqual(links.map(el => el.textContent), ["First", "Second"]);
});
