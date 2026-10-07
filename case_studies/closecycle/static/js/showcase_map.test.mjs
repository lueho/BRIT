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

    const geoJsonLayers = [];
    class FakePolygon {}
    const L = {
        Polygon: FakePolygon,
        GeoJSON: class {},
        point: (x, y) => ({ x, y }),
        canvas: () => ({}),
        circleMarker(latlng, style) {
            return { latlng, style, getLatLng: () => latlng };
        },
        geoJson(data, options) {
            const layer = {
                options,
                data,
                added: [],
                on() {},
                addTo() {
                    return this;
                },
                addData(d) {
                    this.added.push(d);
                },
                eachLayer(callback) {
                    (this.layers || []).forEach(callback);
                },
                resetStyle() {},
                bringToBack() {},
            };
            geoJsonLayers.push(layer);
            return layer;
        },
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
        "pilot-region-context": makeElement("div"),
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
        selectFeature() {},
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
    const pageSelectFeature = sandbox.selectFeature;
    sandbox.selectFeature = layer => {
        calls.selected.push(layer);
        return pageSelectFeature(layer);
    };
    return { sandbox, calls, L, insideChecks, elements, documentListeners, geoJsonLayers };
}

function addLayerBehaviors(layer) {
    layer._listeners = {};
    layer.on = (type, callback) => {
        (layer._listeners[type] ||= []).push(callback);
    };
    layer.fire = type => {
        (layer._listeners[type] || []).forEach(callback => callback());
    };
    layer.setStyle = style => {
        layer.style = style;
    };
    layer.bringToBack = () => {};
    layer.bringToFront = () => {};
    return layer;
}

function mountInOrder(order) {
    return layer => {
        order.push(layer);
        layer.bringToBack = () => {
            order.splice(order.indexOf(layer), 1);
            order.unshift(layer);
        };
        layer.bringToFront = () => {
            order.splice(order.indexOf(layer), 1);
            order.push(layer);
        };
        layer.fire("add");
    };
}

function makeLayer({ L, id, name, region }) {
    const layer = addLayerBehaviors(new L.Polygon());
    layer.feature = { id, properties: { name, region } };
    layer.toGeoJSON = () => ({ geometry: { id } });
    return layer;
}

function makePointLayer({ id, name, region, lat = 55, lng = 14 }) {
    return addLayerBehaviors({
        feature: { id, properties: { name, region, feature_type: "showcase" } },
        getLatLng() {
            return { lat, lng };
        },
    });
}

function makePilotLayer({ L, id, name, showcases }) {
    const layer = addLayerBehaviors(new L.Polygon());
    layer.feature = {
        id,
        properties: {
            feature_type: "pilot_region",
            name,
            region: name,
            showcases,
        },
    };
    layer.toGeoJSON = () => ({ geometry: { id } });
    return layer;
}

function makeFeatureGroup(layers) {
    return {
        resetStyle() {},
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

test("co-located points without regions use a meaningful fallback heading", () => {
    const { sandbox, calls } = setup();
    const layers = [
        makePointLayer({ id: 1, name: "No anchor" }),
        makePointLayer({ id: 2, name: "Null anchor", region: null }),
        makePointLayer({ id: 3, name: "Anchored", region: "Region A" }),
    ];
    sandbox.featureClickHandler(clickEvent, makeFeatureGroup(layers));
    const { content } = calls.openPopup[0];
    assert.deepEqual(
        findAll(content, el => el.tagName === "STRONG").map(el => el.textContent),
        ["No region", "Region A"]
    );
    const links = findAll(content, el => el.tagName === "A");
    assert.deepEqual(links.map(el => el.textContent), ["No anchor", "Null anchor", "Anchored"]);
    links[0].click();
    assert.deepEqual(calls.fetchSummaries.map(params => params.id), [1]);
});

test("features layer renders pilot polygons and showcase points together", () => {
    const { sandbox, geoJsonLayers } = setup({ loadShared: true });
    sandbox.mapConfig.regionLayerStyle = {};
    sandbox.mapConfig.catchmentLayerStyle = {};
    sandbox.mapConfig.featuresLayerStyle = { radius: 4, color: "#123456" };
    sandbox.initializeRenderers();

    const layer = sandbox.createFeaturesLayer(null, "MultiPolygon");

    assert.equal(geoJsonLayers.length, 1);
    assert.equal(typeof layer.options.pointToLayer, "function");
    assert.equal(typeof layer.options.style, "function");
    assert.equal(layer.options.style({ properties: {} }).color, "#123456");
    const marker = layer.options.pointToLayer(
        { properties: { feature_type: "showcase" } },
        { lat: 1, lng: 2 }
    );
    assert.equal(marker.style.color, "#123456");
    assert.equal(typeof marker.getLatLng, "function");
});

test("streaming batches keep polygons and points in a single mixed layer", () => {
    const { sandbox, geoJsonLayers } = setup({ loadShared: true });
    sandbox.mapConfig.regionLayerStyle = {};
    sandbox.mapConfig.catchmentLayerStyle = {};
    sandbox.mapConfig.featuresLayerStyle = { radius: 4 };
    sandbox.initializeRenderers();

    const pilot = {
        type: "Feature",
        id: "pilot-catchment-3",
        geometry: { type: "MultiPolygon", coordinates: [] },
        properties: { feature_type: "pilot_region", showcases: [] },
    };
    const point = {
        type: "Feature",
        id: 5,
        geometry: { type: "Point", coordinates: [1, 2] },
        properties: { feature_type: "showcase" },
    };

    assert.equal(sandbox.addFeatureBatch([pilot]), true);
    assert.equal(sandbox.addFeatureBatch([point]), true);

    assert.equal(geoJsonLayers.length, 1);
    assert.deepEqual(geoJsonLayers[0].added, [[pilot], [point]]);
    assert.equal(typeof geoJsonLayers[0].options.pointToLayer, "function");
    assert.equal(typeof geoJsonLayers[0].options.style, "function");
});

test("null geometry features are ignored by batch and full renders", () => {
    const { sandbox, geoJsonLayers } = setup({ loadShared: true });
    sandbox.mapConfig.regionLayerStyle = {};
    sandbox.mapConfig.catchmentLayerStyle = {};
    sandbox.mapConfig.featuresLayerStyle = { radius: 4 };
    sandbox.initializeRenderers();

    const noGeom = { type: "Feature", id: 9, geometry: null, properties: {} };
    const point = {
        type: "Feature",
        id: 5,
        geometry: { type: "Point", coordinates: [1, 2] },
        properties: {},
    };

    assert.equal(sandbox.addFeatureBatch([noGeom]), false);
    sandbox.renderFeatures({
        type: "FeatureCollection",
        features: [noGeom, point],
    });
    assert.equal(geoJsonLayers.length, 1);
    assert.deepEqual(geoJsonLayers[0].data.features, [point]);
});

test("pilot polygon click fetches numeric showcase id and highlights polygon and marker", () => {
    const { sandbox, calls, L } = setup();
    const pilot = makePilotLayer({
        L,
        id: "pilot-catchment-9",
        name: "Pilot Nine",
        showcases: [{ id: 5, name: "Site A", region: "Pilot Nine" }],
    });
    const marker = makePointLayer({ id: 5, name: "Site A", region: "Pilot Nine", lat: 80, lng: 80 });
    const group = makeFeatureGroup([pilot, marker]);

    sandbox.featureClickHandler({ latlng: { lng: 14, lat: 55 }, layer: pilot }, group);

    assert.equal(calls.openPopup.length, 0);
    assert.deepEqual(calls.fetchSummaries.map(params => params.id), [5]);
    assert.ok(calls.selected.includes(pilot));
    assert.ok(calls.selected.includes(marker));
});

test("pilot polygon with several showcases offers a choice popup with numeric ids", () => {
    const { sandbox, calls, L } = setup();
    const pilot = makePilotLayer({
        L,
        id: "pilot-catchment-9",
        name: "Pilot Nine",
        showcases: [
            { id: 5, name: "Site A", region: "Pilot Nine" },
            { id: 7, name: "Site <b>B</b>", region: "Pilot Nine" },
        ],
    });
    const group = makeFeatureGroup([pilot]);

    sandbox.featureClickHandler({ latlng: { lng: 14, lat: 55 }, layer: pilot }, group);

    assert.equal(calls.openPopup.length, 1);
    const links = findAll(calls.openPopup[0].content, el => el.tagName === "A");
    assert.deepEqual(links.map(el => el.textContent), ["Site A", "Site <b>B</b>"]);
    links[1].click();
    assert.deepEqual(calls.fetchSummaries.map(params => params.id), [7]);
});

test("overlapping pilot polygons deduplicate showcases in the choice popup", () => {
    const { sandbox, calls, L } = setup();
    const first = makePilotLayer({
        L,
        id: "pilot-catchment-1",
        name: "Pilot One",
        showcases: [
            { id: 5, name: "Site A", region: "Pilot One" },
            { id: 6, name: "Site B", region: "Pilot One" },
        ],
    });
    const second = makePilotLayer({
        L,
        id: "pilot-catchment-2",
        name: "Pilot Two",
        showcases: [{ id: 5, name: "Site A", region: "Pilot Two" }],
    });
    const group = makeFeatureGroup([first, second]);

    sandbox.featureClickHandler({ latlng: { lng: 14, lat: 55 }, layer: first }, group);

    const links = findAll(calls.openPopup[0].content, el => el.tagName === "A");
    assert.deepEqual(links.map(el => el.textContent), ["Site A", "Site B"]);
});

test("click on a point marker selects it without the containing pilot polygon", () => {
    const { sandbox, calls, L } = setup();
    const pilot = makePilotLayer({
        L,
        id: "pilot-catchment-9",
        name: "Pilot Nine",
        showcases: [
            { id: 5, name: "Site A", region: "Pilot Nine" },
            { id: 7, name: "Site B", region: "Pilot Nine" },
        ],
    });
    const marker = makePointLayer({ id: 5, name: "Site A", region: "Pilot Nine" });
    const group = makeFeatureGroup([pilot, marker]);

    sandbox.featureClickHandler({ latlng: { lng: 14, lat: 55 }, layer: marker }, group);

    assert.equal(calls.openPopup.length, 0);
    assert.deepEqual(calls.fetchSummaries.map(params => params.id), [5]);
    assert.deepEqual(calls.selected, [marker]);
});

test("click on empty map still matches nearby markers and hit polygons", () => {
    const { sandbox, calls, L } = setup();
    const pilot = makePilotLayer({
        L,
        id: "pilot-catchment-9",
        name: "Pilot Nine",
        showcases: [{ id: 5, name: "Site A", region: "Pilot Nine" }],
    });
    const marker = makePointLayer({ id: 8, name: "Site C", region: "Elsewhere" });
    const group = makeFeatureGroup([pilot, marker]);

    sandbox.featureClickHandler(clickEvent, group);

    const links = findAll(calls.openPopup[0].content, el => el.tagName === "A");
    assert.deepEqual(links.map(el => el.textContent), ["Site A", "Site C"]);
});

function initSharedStyles(sandbox) {
    sandbox.mapConfig.regionLayerStyle = {};
    sandbox.mapConfig.catchmentLayerStyle = {};
    sandbox.mapConfig.featuresLayerStyle = { radius: 4 };
    sandbox.initializeRenderers();
}

test("pilot polygons mounted after points still end up below markers", () => {
    const { sandbox, L } = setup({ loadShared: true });
    initSharedStyles(sandbox);
    const layer = sandbox.createFeaturesLayer(null, "Point");
    const order = [];
    const mount = mountInOrder(order);
    const marker = makePointLayer({ id: 5, name: "Site A", region: "Pilot" });
    const pilot = makePilotLayer({
        L,
        id: "pilot-catchment-9",
        name: "Pilot",
        showcases: [{ id: 5, name: "Site A", region: "Pilot" }],
    });
    layer.options.onEachFeature(marker.feature, marker);
    layer.options.onEachFeature(pilot.feature, pilot);
    mount(marker);
    mount(pilot);
    assert.equal(order[0], pilot);
    assert.equal(order[order.length - 1], marker);
});

test("resetFeatureStyles pushes polygons to the back without moving markers", () => {
    const { sandbox, L } = setup();
    const order = [];
    const mount = mountInOrder(order);
    const marker = makePointLayer({ id: 5, name: "Site A", region: "Pilot" });
    const pilot = makePilotLayer({
        L,
        id: "pilot-catchment-9",
        name: "Pilot",
        showcases: [{ id: 5, name: "Site A", region: "Pilot" }],
    });
    mount(marker);
    mount(pilot);
    assert.equal(order[order.length - 1], pilot);

    sandbox.resetFeatureStyles(makeFeatureGroup([pilot, marker]));

    assert.equal(order[0], pilot);
    assert.equal(order[order.length - 1], marker);
});

test("selectFeature highlights a polygon without raising it above markers", () => {
    const { sandbox, L } = setup();
    const order = [];
    const mount = mountInOrder(order);
    const pilot = makePilotLayer({
        L,
        id: "pilot-catchment-9",
        name: "Pilot",
        showcases: [{ id: 5, name: "Site A", region: "Pilot" }],
    });
    const marker = makePointLayer({ id: 5, name: "Site A", region: "Pilot" });
    mount(pilot);
    mount(marker);

    sandbox.selectFeature(pilot);
    assert.equal(pilot.style.color, "#f49a33");
    assert.equal(order[0], pilot);
    assert.equal(order[order.length - 1], marker);

    sandbox.selectFeature(marker);
    assert.equal(order[order.length - 1], marker);
});

test("pilot polygon click orders the polygon below its associated marker", () => {
    const { sandbox, calls, L } = setup();
    const order = [];
    const mount = mountInOrder(order);
    const pilot = makePilotLayer({
        L,
        id: "pilot-catchment-9",
        name: "Pilot Nine",
        showcases: [{ id: 5, name: "Site A", region: "Pilot Nine" }],
    });
    const marker = makePointLayer({ id: 5, name: "Site A", region: "Pilot Nine", lat: 80, lng: 80 });
    mount(marker);
    mount(pilot);
    const group = makeFeatureGroup([pilot, marker]);

    sandbox.featureClickHandler({ latlng: { lng: 14, lat: 55 }, layer: pilot }, group);

    assert.deepEqual(calls.fetchSummaries.map(params => params.id), [5]);
    assert.equal(order[0], pilot);
    assert.equal(order[order.length - 1], marker);
});

test("source theme colour applies to markers and lightly filled pilot polygons", () => {
    const { sandbox } = setup({ loadShared: true });
    initSharedStyles(sandbox);
    const theme = { color: "#ff4f4f" };
    const point = sandbox.showcaseFeatureStyle({ properties: { feature_type: "showcase", theme } });
    const polygon = sandbox.showcaseFeatureStyle({ properties: { feature_type: "pilot_region", theme } });
    assert.equal(point.color, "#ff4f4f");
    assert.equal(point.fillColor, "#ff4f4f");
    assert.equal(point.fillOpacity, 0.9);
    assert.equal(polygon.fillOpacity, 0.15);
    assert.equal(polygon.color, point.color);
});

test("unassigned themes and unsafe colour values use the configured default", () => {
    const { sandbox } = setup({ loadShared: true });
    initSharedStyles(sandbox);
    sandbox.mapConfig.featuresLayerStyle.color = "#123456";
    assert.equal(sandbox.showcaseFeatureStyle({ properties: {} }).color, "#123456");
    assert.equal(sandbox.showcaseFeatureStyle({ properties: { theme: { color: "url(evil)" } } }).color, "#123456");
});

test("theme explanation renders text safely and only links to local URLs", () => {
    const { sandbox } = setup();
    const container = makeElement("div");
    sandbox.appendThemeContext(container, {
        label: "<script>Apple</script>", description: "Regional circular focus", url: "//evil.test",
    });
    assert.ok(textOf(container).includes("Theme: <script>Apple</script>"));
    assert.ok(textOf(container).includes("Regional circular focus"));
    assert.equal(findAll(container, el => el.tagName === "A").length, 0);
});

test("pilot context explains stakeholders and boundary limits without duplicate cards", () => {
    const { sandbox, elements } = setup();
    const pilot = { id: 7, name: "<b>Network</b>", description: "Regional exchanges",
        role: "Territorial Biorefinery Network stakeholders", boundary_note: "Not exact flow boundaries",
        url: "/maps/catchments/7/", showcases_url: "/closecycle/showcases/map/?pilot_region=7" };
    sandbox.renderPilotRegions([pilot, pilot]);
    const container = elements["pilot-region-context"];
    assert.equal(container.hidden, false);
    assert.equal(findAll(container, el => el.tagName === "SECTION").length, 1);
    assert.ok(textOf(container).includes("<b>Network</b>"));
    assert.ok(textOf(container).includes("stakeholders"));
    assert.ok(textOf(container).includes("Not exact flow boundaries"));
    const links = findAll(container, el => el.tagName === "A");
    assert.equal(links[0].href, pilot.url);
    assert.equal(links[1].href, pilot.showcases_url);
    assert.equal(links[1].textContent, "Explore regional showcases");
    sandbox.renderPilotRegions([]);
    assert.equal(container.hidden, true);
    assert.equal(container.children.length, 0);
});

test("pilot polygon reveals network context before a showcase is chosen", () => {
    const { sandbox, calls, L, elements } = setup();
    const pilot = makePilotLayer({ L, id: "pilot-7", name: "Network",
        showcases: [{ id: 5, name: "One" }, { id: 6, name: "Two" }] });
    pilot.feature.properties.pilot_region = { id: 7, name: "Regional network", role: "Stakeholder exchanges" };
    sandbox.featureClickHandler({ ...clickEvent, layer: pilot }, makeFeatureGroup([pilot]));
    assert.equal(calls.fetchSummaries.length, 0);
    assert.equal(elements["pilot-region-context"].hidden, false);
    assert.ok(textOf(elements["pilot-region-context"]).includes("Regional network"));
});

test("marker context follows its linked pilot rather than unrelated polygons", () => {
    const { sandbox, L, elements } = setup();
    const first = makePilotLayer({ L, id: "pilot-7", name: "One", showcases: [{ id: 5, name: "Site" }] });
    first.feature.properties.pilot_region = { id: 7, name: "Selected network" };
    const other = makePilotLayer({ L, id: "pilot-8", name: "Other", showcases: [{ id: 9, name: "Other site" }] });
    other.feature.properties.pilot_region = { id: 8, name: "Unrelated network" };
    const marker = makePointLayer({ id: 5, name: "Site" });
    sandbox.featureClickHandler({ ...clickEvent, layer: marker }, makeFeatureGroup([first, other, marker]));
    const text = textOf(elements["pilot-region-context"]);
    assert.ok(text.includes("Selected network"));
    assert.equal(text.includes("Unrelated network"), false);
});

test("summary refresh clears previous pilot context when the selected showcase has none", () => {
    const { sandbox, elements } = setup();
    sandbox.renderSummaries({ summaries: [makeSummary({ pilot_region: { id: 7, name: "Network" } })] });
    assert.equal(elements["pilot-region-context"].hidden, false);
    sandbox.renderSummaries({ summaries: [makeSummary({ pilot_region: null })] });
    assert.equal(elements["pilot-region-context"].hidden, true);
});

test("showcase points carry a permanent code label", () => {
    const { sandbox } = setup({ loadShared: true });
    sandbox.mapConfig.regionLayerStyle = {};
    sandbox.mapConfig.catchmentLayerStyle = {};
    sandbox.mapConfig.featuresLayerStyle = { radius: 4 };
    sandbox.initializeRenderers();
    const layer = sandbox.createFeaturesLayer(null, "Point");
    const tooltips = [];
    const makeMarker = properties =>
        addLayerBehaviors({
            feature: { id: 1, properties },
            getLatLng: () => ({ lat: 1, lng: 2 }),
            bindPopup() {},
            bindTooltip(content, options) {
                tooltips.push({ content, options });
            },
        });

    layer.options.onEachFeature(
        { id: 1, properties: { feature_type: "showcase", code: "SC14" } },
        makeMarker({ feature_type: "showcase", code: "SC14" })
    );
    layer.options.onEachFeature(
        { id: 2, properties: { feature_type: "showcase", code: null } },
        makeMarker({ feature_type: "showcase", code: null })
    );

    assert.equal(tooltips.length, 1);
    assert.equal(tooltips[0].content, "SC14");
    assert.equal(tooltips[0].options.permanent, true);
});

test("list selection highlights the showcase marker, zooms to it and loads its summary", () => {
    const { sandbox, calls } = setup();
    const views = [];
    sandbox.map.getZoom = () => 4;
    sandbox.map.setView = (latlng, zoom) => views.push({ latlng, zoom });
    const marker = makePointLayer({ id: 12, name: "SC14", lat: 58, lng: 13 });
    const other = makePointLayer({ id: 13, name: "SC15", lat: 50, lng: 10 });
    sandbox.featuresLayer = makeFeatureGroup([marker, other]);

    sandbox.selectShowcaseFromList(12);

    assert.deepEqual(calls.selected, [marker]);
    assert.equal(views.length, 1);
    assert.deepEqual(views[0].latlng, { lat: 58, lng: 13 });
    assert.ok(views[0].zoom > 4);
    assert.deepEqual(calls.fetchSummaries.map(params => params.id), [12]);
});

test("list clicks are delegated from the showcase list", () => {
    const { sandbox, elements, documentListeners, calls } = setup();
    elements["showcase-list"] = makeElement("ul");
    sandbox.featuresLayer = makeFeatureGroup([]);
    (documentListeners.DOMContentLoaded || []).forEach(callback => callback());

    const button = { dataset: { showcaseId: "12" } };
    let prevented = false;
    elements["showcase-list"].listeners.click.forEach(callback =>
        callback({
            target: { closest: selector => (selector === "[data-showcase-id]" ? button : null) },
            preventDefault() {
                prevented = true;
            },
        })
    );

    assert.ok(prevented);
    assert.deepEqual(calls.fetchSummaries.map(params => params.id), [12]);
});

function setupListSelection() {
    const context = setup();
    const views = [];
    const pending = [];
    context.sandbox.map.getZoom = () => 4;
    context.sandbox.map.setView = (latlng, zoom) => views.push({ latlng, zoom });
    context.sandbox.fetchFeaturesLayerSummary = (params, isCurrent = () => true) => {
        pending.push({ params, isCurrent });
        return Promise.resolve();
    };
    return { ...context, views, pending };
}

test("a list selection made before the markers load is applied once they have loaded", () => {
    const { sandbox, calls, views } = setupListSelection();
    sandbox.featuresLayer = null;

    sandbox.selectShowcaseFromList(12);
    assert.equal(views.length, 0);

    const marker = makePointLayer({ id: 12, name: "SC14", lat: 58, lng: 13 });
    sandbox.featuresLayer = makeFeatureGroup([marker]);
    sandbox.layersLoaded();

    assert.deepEqual(calls.selected, [marker]);
    assert.deepEqual(views.map(view => view.latlng), [{ lat: 58, lng: 13 }]);
});

test("a map click replaces an earlier list selection that is still waiting for the markers", () => {
    const { sandbox, views } = setupListSelection();
    sandbox.featuresLayer = null;
    sandbox.selectShowcaseFromList(12);

    const other = makePointLayer({ id: 13, name: "SC15", lat: 55, lng: 14 });
    const group = makeFeatureGroup([other]);
    sandbox.featureClickHandler({ ...clickEvent, layer: other }, group);
    sandbox.featuresLayer = makeFeatureGroup([
        makePointLayer({ id: 12, name: "SC14", lat: 58, lng: 13 }),
        other,
    ]);
    sandbox.layersLoaded();

    assert.equal(views.length, 0);
});

test("only the latest showcase selection may render its summary", () => {
    const { sandbox, pending } = setupListSelection();
    sandbox.featuresLayer = makeFeatureGroup([]);

    sandbox.selectShowcaseFromList(12);
    sandbox.selectShowcaseFromList(13);

    assert.deepEqual(pending.map(request => request.params.id), [12, 13]);
    assert.equal(pending[0].isCurrent(), false);
    assert.equal(pending[1].isCurrent(), true);

    const first = makePointLayer({ id: 1, name: "A", region: "R" });
    const second = makePointLayer({ id: 2, name: "B", region: "R" });
    sandbox.featureClickHandler({ ...clickEvent, layer: first }, makeFeatureGroup([first, second]));
    assert.equal(pending[1].isCurrent(), false);
});

test("the list marks only a single selected showcase as current", () => {
    const { sandbox } = setupListSelection();
    const button = {
        dataset: { showcaseId: "12" },
        attributes: {},
        setAttribute(name, value) {
            this.attributes[name] = value;
        },
        removeAttribute(name) {
            delete this.attributes[name];
        },
    };
    sandbox.document.querySelectorAll = selector =>
        selector.includes("#showcase-list") ? [button] : [];

    sandbox.renderSummaries({ summaries: [makeSummary({ id: 12 })] });
    assert.equal(button.attributes["aria-current"], "true");

    sandbox.renderSummaries({
        summaries: [makeSummary({ id: 12 }), makeSummary({ id: 13 })],
    });
    assert.equal(button.attributes["aria-current"], undefined);
});

function makeLabelledMarker({ id, code, lat = 58, lng = 13 }) {
    const marker = makePointLayer({ id, name: code, lat, lng });
    marker.feature.properties.code = code;
    marker.tooltip = code;
    marker.getTooltip = () => marker.tooltip;
    marker.setTooltipContent = content => {
        marker.tooltip = content;
    };
    marker.unbindTooltip = () => {
        marker.tooltip = undefined;
    };
    return marker;
}

test("showcases at the same location share one label listing their codes", () => {
    const { sandbox } = setupListSelection();
    const sc15 = makeLabelledMarker({ id: 56, code: "SC15" });
    const sc14 = makeLabelledMarker({ id: 12, code: "SC14" });
    const sc16 = makeLabelledMarker({ id: 57, code: "SC16" });
    const apart = makeLabelledMarker({ id: 3, code: "SC2", lat: 50, lng: 8 });
    sandbox.featuresLayer = makeFeatureGroup([sc15, sc14, sc16, apart]);

    sandbox.layersLoaded();
    sandbox.layersLoaded();

    const labels = [sc15, sc14, sc16].map(marker => marker.tooltip).filter(Boolean);
    assert.deepEqual(labels, ["SC14 \u00b7 SC15 \u00b7 SC16"]);
    assert.equal(apart.tooltip, "SC2");
});

test("pilot members whose region is hidden are not filed under the pilot's region", () => {
    const { sandbox, calls, L } = setup();
    const pilot = makePilotLayer({
        L,
        id: "pilot-catchment-9",
        name: "Pilot Nine",
        showcases: [
            { id: 5, name: "Hidden anchor", region: null },
            { id: 7, name: "Pilot member", region: "Pilot Nine" },
        ],
    });

    sandbox.featureClickHandler({ latlng: { lng: 14, lat: 55 }, layer: pilot }, makeFeatureGroup([pilot]));

    const headings = findAll(calls.openPopup[0].content, el => el.tagName === "STRONG")
        .map(el => el.textContent);
    assert.deepEqual(headings.sort(), ["No region", "Pilot Nine"]);
});
